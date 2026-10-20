#include "engine.h"
#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <vector>
#include <unistd.h>
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavfilter/avfilter.h>
#include <libavfilter/buffersrc.h>
#include <libavfilter/buffersink.h>
#include <libavutil/avstring.h>
#include <libavutil/opt.h>
#include <libavutil/pixdesc.h>
}

namespace hmosffmpeg {
namespace {
void check(int rc) {
    if (rc < 0) { char e[AV_ERROR_MAX_STRING_SIZE]; av_strerror(rc, e, sizeof(e)); throw std::runtime_error(e); }
}
std::string quote(const std::string& text) {
    std::ostringstream s; s << '"';
    static const char hex[] = "0123456789abcdef";
    for (unsigned char c : text) {
        if (c == '"' || c == '\\') s << '\\' << c;
        else if (c < 32) s << "\\u00" << hex[c >> 4] << hex[c & 15];
        else s << c;
    }
    return s.str() + '"';
}
struct Input {
    Task& task;
    AVFormatContext* ctx = nullptr;
    AVIOContext* io = nullptr;
    int fd = -1;
    std::chrono::steady_clock::time_point deadline;
    explicit Input(Task& t): task(t) { deadline = std::chrono::steady_clock::now() + std::chrono::seconds(t.timeoutSeconds); }
    static int interrupt(void* ptr) {
        auto* self = static_cast<Input*>(ptr);
        return self->task.cancelled || std::chrono::steady_clock::now() > self->deadline;
    }
    static int read(void* ptr, uint8_t* buffer, int length) {
        auto* self = static_cast<Input*>(ptr);
        if (interrupt(ptr)) return AVERROR_EXIT;
        ssize_t rc = ::read(self->fd, buffer, length);
        return rc == 0 ? AVERROR_EOF : rc < 0 ? AVERROR(errno) : static_cast<int>(rc);
    }
    static int64_t seek(void* ptr, int64_t offset, int whence) {
        auto* self = static_cast<Input*>(ptr);
        if (whence == AVSEEK_SIZE) {
            auto pos = lseek(self->fd, 0, SEEK_CUR); auto end = lseek(self->fd, 0, SEEK_END);
            if (pos >= 0) lseek(self->fd, pos, SEEK_SET);
            return end < 0 ? AVERROR(errno) : end;
        }
        auto rc = lseek(self->fd, offset, whence & ~AVSEEK_FORCE);
        return rc < 0 ? AVERROR(errno) : rc;
    }
    void resetDeadline() { deadline = std::chrono::steady_clock::now() + std::chrono::seconds(task.timeoutSeconds); }
    void open() {
        ctx = avformat_alloc_context(); if (!ctx) throw std::bad_alloc();
        ctx->interrupt_callback = {interrupt, this};
        const char* url = task.input.c_str();
        if (task.input.rfind("fd:", 0) == 0) {
            size_t used = 0; int value = std::stoi(task.input.substr(3), &used);
            if (used != task.input.size() - 3 || value < 0) throw std::runtime_error("Invalid fd");
            fd = dup(value); if (fd < 0) throw std::runtime_error("dup failed");
            auto* buffer = static_cast<unsigned char*>(av_malloc(65536));
            if (!buffer) throw std::bad_alloc();
            io = avio_alloc_context(buffer, 65536, 0, this, read, nullptr, seek);
            if (!io) { av_free(buffer); throw std::bad_alloc(); }
            ctx->pb = io; ctx->flags |= AVFMT_FLAG_CUSTOM_IO; url = nullptr;
        }
        AVDictionary* opts = nullptr;
        av_dict_set(&opts, "protocol_whitelist", "file,http,https,tcp,tls,crypto,pipe", 0);
        av_dict_set(&opts, "tls_verify", "1", 0);
        if(!task.caFile.empty()) av_dict_set(&opts, "ca_file", task.caFile.c_str(), 0);
        int rc = avformat_open_input(&ctx, url, nullptr, &opts);
        av_dict_free(&opts); check(rc);
        check(avformat_find_stream_info(ctx, nullptr));
    }
    ~Input() {
        avformat_close_input(&ctx);
        if (io) { av_freep(&io->buffer); avio_context_free(&io); }
        if (fd >= 0) close(fd);
    }
};
struct Stream {
    AVCodecContext *decoder = nullptr, *encoder = nullptr;
    AVFilterGraph* graph = nullptr;
    AVFilterContext *source = nullptr, *sink = nullptr;
    AVStream* output = nullptr;
    ~Stream() { avcodec_free_context(&decoder); avcodec_free_context(&encoder); avfilter_graph_free(&graph); }
};
struct Output {
    AVFormatContext* ctx = nullptr;
    ~Output() { if(ctx) { if (!(ctx->oformat->flags & AVFMT_NOFILE)) avio_closep(&ctx->pb); avformat_free_context(ctx); } }
};
using Frame = std::unique_ptr<AVFrame, void(*)(AVFrame*)>;
using Packet = std::unique_ptr<AVPacket, void(*)(AVPacket*)>;
Frame frame() { auto* p = av_frame_alloc(); if(!p) throw std::bad_alloc(); return Frame(p, [](AVFrame* f){av_frame_free(&f);}); }
Packet packet() { auto* p = av_packet_alloc(); if(!p) throw std::bad_alloc(); return Packet(p, [](AVPacket* f){av_packet_free(&f);}); }

void initFilter(Stream& s, AVStream* input, const std::string& filter) {
    bool video = s.decoder->codec_type == AVMEDIA_TYPE_VIDEO;
    s.graph = avfilter_graph_alloc(); if(!s.graph) throw std::bad_alloc();
    s.graph->nb_threads = 2;
    std::ostringstream args;
    if (video) args << "video_size=" << s.decoder->width << 'x' << s.decoder->height
        << ":pix_fmt=" << s.decoder->pix_fmt << ":time_base=" << input->time_base.num << '/' << input->time_base.den
        << ":pixel_aspect=" << (s.decoder->sample_aspect_ratio.num ? s.decoder->sample_aspect_ratio.num : 1)
        << '/' << (s.decoder->sample_aspect_ratio.den ? s.decoder->sample_aspect_ratio.den : 1);
    else {
        char layout[256]; check(av_channel_layout_describe(&s.decoder->ch_layout, layout, sizeof(layout)));
        args << "time_base=" << input->time_base.num << '/' << input->time_base.den
          << ":sample_rate=" << s.decoder->sample_rate << ":sample_fmt=" << av_get_sample_fmt_name(s.decoder->sample_fmt)
          << ":channel_layout=" << layout;
    }
    check(avfilter_graph_create_filter(&s.source, avfilter_get_by_name(video ? "buffer" : "abuffer"), "in", args.str().c_str(), nullptr, s.graph));
    check(avfilter_graph_create_filter(&s.sink, avfilter_get_by_name(video ? "buffersink" : "abuffersink"), "out", nullptr, nullptr, s.graph));
    std::string description = filter.empty() ? (video ? "null" : "anull") : filter;
    if (video) description += ",format=pix_fmts=" + std::string(av_get_pix_fmt_name(s.encoder->pix_fmt));
    else {
        char layout[256]; check(av_channel_layout_describe(&s.encoder->ch_layout, layout, sizeof(layout)));
        description += ",aformat=sample_fmts=" + std::string(av_get_sample_fmt_name(s.encoder->sample_fmt))
            + ":sample_rates=" + std::to_string(s.encoder->sample_rate) + ":channel_layouts=" + layout;
    }
    AVFilterInOut *ins = avfilter_inout_alloc(), *outs = avfilter_inout_alloc();
    if (!ins || !outs) { avfilter_inout_free(&ins); avfilter_inout_free(&outs); throw std::bad_alloc(); }
    outs->name = av_strdup("in"); outs->filter_ctx = s.source; outs->pad_idx = 0;
    ins->name = av_strdup("out"); ins->filter_ctx = s.sink; ins->pad_idx = 0;
    int rc = avfilter_graph_parse_ptr(s.graph, description.c_str(), &ins, &outs, nullptr);
    avfilter_inout_free(&ins); avfilter_inout_free(&outs); check(rc);
    check(avfilter_graph_config(s.graph, nullptr));
}
void writeEncoded(Stream& s, AVFormatContext* output, AVFrame* f) {
    check(avcodec_send_frame(s.encoder, f));
    auto p = packet();
    for (;;) {
        int rc = avcodec_receive_packet(s.encoder, p.get());
        if (rc == AVERROR(EAGAIN) || rc == AVERROR_EOF) break;
        check(rc); av_packet_rescale_ts(p.get(), s.encoder->time_base, s.output->time_base);
        p->stream_index = s.output->index; check(av_interleaved_write_frame(output, p.get()));
    }
}
void drainFilter(Stream& s, AVFormatContext* output) {
    auto f = frame();
    for (;;) {
        int rc = av_buffersink_get_frame(s.sink, f.get());
        if (rc == AVERROR(EAGAIN) || rc == AVERROR_EOF) break;
        check(rc);
        AVRational sourceTime = av_buffersink_get_time_base(s.sink);
        if(f->pts != AV_NOPTS_VALUE) f->pts = av_rescale_q(f->pts, sourceTime, s.encoder->time_base);
        if(f->duration > 0) f->duration = av_rescale_q(f->duration, sourceTime, s.encoder->time_base);
        f->time_base = s.encoder->time_base;
        f->pict_type = AV_PICTURE_TYPE_NONE;
        writeEncoded(s, output, f.get()); av_frame_unref(f.get());
    }
}
void decode(Stream& s, AVFormatContext* output, AVPacket* p) {
    check(avcodec_send_packet(s.decoder, p));
    auto f = frame();
    for (;;) {
        int rc = avcodec_receive_frame(s.decoder, f.get());
        if (rc == AVERROR(EAGAIN) || rc == AVERROR_EOF) break;
        check(rc); f->pts = f->best_effort_timestamp;
        check(av_buffersrc_add_frame_flags(s.source, f.get(), AV_BUFFERSRC_FLAG_KEEP_REF));
        drainFilter(s, output); av_frame_unref(f.get());
    }
}
}

std::string buildInfo() {
    return "{\"version\":" + quote(av_version_info()) + ",\"license\":" + quote(avutil_license())
        + ",\"configuration\":" + quote(avutil_configuration()) + ",\"hardwareBackend\":\"external-harmony-avcodec\"}";
}
std::string capabilities() {
    std::string result = "{\"encoders\":["; bool first = true; void* it = nullptr;
    const AVCodec* c;
    while ((c = av_codec_iterate(&it))) if(av_codec_is_encoder(c)) {
        if(!first) result += ','; first = false; result += quote(c->name);
    }
    result += "],\"decoders\":["; first = true; it = nullptr;
    while ((c = av_codec_iterate(&it))) if(av_codec_is_decoder(c)) {
        if(!first) result += ','; first = false; result += quote(c->name);
    }
    result += "],\"muxers\":["; first = true; it = nullptr; const AVOutputFormat* mux;
    while((mux = av_muxer_iterate(&it))) { if(!first) result += ','; first = false; result += quote(mux->name); }
    result += "],\"demuxers\":["; first = true; it = nullptr; const AVInputFormat* demux;
    while((demux = av_demuxer_iterate(&it))) { if(!first) result += ','; first = false; result += quote(demux->name); }
    result += "],\"inputProtocols\":["; first = true; it = nullptr; const char* protocol;
    while((protocol = avio_enum_protocols(&it, 0))) { if(!first) result += ','; first = false; result += quote(protocol); }
    result += "],\"outputProtocols\":["; first = true; it = nullptr;
    while((protocol = avio_enum_protocols(&it, 1))) { if(!first) result += ','; first = false; result += quote(protocol); }
    result += "],\"filters\":["; first = true; it = nullptr; const AVFilter* f;
    while((f = av_filter_iterate(&it))) { if(!first) result += ','; first = false; result += quote(f->name); }
    return result + "]}";
}
std::string probe(Task& task) {
    Input input(task); input.open();
    std::string out = "{\"format\":" + quote(input.ctx->iformat->name)
        + ",\"durationUs\":" + std::to_string(input.ctx->duration) + ",\"streams\":[";
    for(unsigned i = 0; i < input.ctx->nb_streams; ++i) {
        auto* p = input.ctx->streams[i]->codecpar;
        if(i) out += ',';
        out += "{\"index\":" + std::to_string(i) + ",\"codec\":" + quote(avcodec_get_name(p->codec_id))
            + ",\"type\":" + quote(av_get_media_type_string(p->codec_type) ? av_get_media_type_string(p->codec_type) : "unknown")
            + ",\"width\":" + std::to_string(p->width) + ",\"height\":" + std::to_string(p->height)
            + ",\"sampleRate\":" + std::to_string(p->sample_rate) + ",\"channels\":" + std::to_string(p->ch_layout.nb_channels) + '}';
    }
    return out + "]}";
}
void convert(Task& task) {
    if(task.input == task.output || task.output.empty() || task.output[0] != '/') throw std::runtime_error("Output must be a distinct absolute sandbox path");
    // O_EXCL ensures a failure never removes or overwrites a user's existing file.
    int reserve = ::open(task.output.c_str(), O_WRONLY|O_CREAT|O_EXCL, 0600);
    if(reserve < 0) throw std::runtime_error("Output exists or cannot be created");
    close(reserve);
    bool success = false;
    try {
        Input input(task); input.open(); Output output;
        check(avformat_alloc_output_context2(&output.ctx, nullptr, nullptr, task.output.c_str()));
        if(!output.ctx) throw std::runtime_error("Unknown output format");
        output.ctx->interrupt_callback = {Input::interrupt, &input};
        std::vector<std::unique_ptr<Stream>> streams;
        for(unsigned i = 0; i < input.ctx->nb_streams; ++i) {
            auto s = std::make_unique<Stream>(); auto* in = input.ctx->streams[i];
            auto type = in->codecpar->codec_type;
            std::string codec = type == AVMEDIA_TYPE_VIDEO ? task.videoCodec : type == AVMEDIA_TYPE_AUDIO ? task.audioCodec : "copy";
            if(codec == "none") { streams.push_back(std::move(s)); continue; }
            s->output = avformat_new_stream(output.ctx, nullptr); if(!s->output) throw std::bad_alloc();
            if(codec.empty() || codec == "copy" || task.operation == "remux") {
                check(avcodec_parameters_copy(s->output->codecpar, in->codecpar));
                s->output->codecpar->codec_tag = 0; s->output->time_base = in->time_base;
                s->output->avg_frame_rate = in->avg_frame_rate;
                s->output->r_frame_rate = in->r_frame_rate;
                s->output->sample_aspect_ratio = in->sample_aspect_ratio;
            } else {
                if(type != AVMEDIA_TYPE_VIDEO && type != AVMEDIA_TYPE_AUDIO) throw std::runtime_error("Only audio/video encoding supported");
                auto* dec = avcodec_find_decoder(in->codecpar->codec_id); auto* enc = avcodec_find_encoder_by_name(codec.c_str());
                if(!dec || !enc || enc->type != type) throw std::runtime_error("Unavailable or mismatched codec: " + codec);
                s->decoder = avcodec_alloc_context3(dec); s->encoder = avcodec_alloc_context3(enc);
                if(!s->decoder || !s->encoder) throw std::bad_alloc();
                check(avcodec_parameters_to_context(s->decoder, in->codecpar));
                s->decoder->pkt_timebase = in->time_base; s->decoder->thread_count = 2;
                check(avcodec_open2(s->decoder, dec, nullptr));
                s->encoder->thread_count = 2;
                const void* configs = nullptr; int count = 0;
                if(type == AVMEDIA_TYPE_VIDEO) {
                    s->encoder->framerate = av_guess_frame_rate(input.ctx, in, nullptr);
                    if(!s->encoder->framerate.num || !s->encoder->framerate.den) s->encoder->framerate = {30, 1};
                    s->encoder->time_base = av_inv_q(s->encoder->framerate);
                    s->encoder->pix_fmt = AV_PIX_FMT_YUV420P;
                    check(avcodec_get_supported_config(s->encoder, enc, AV_CODEC_CONFIG_PIX_FORMAT, 0, &configs, &count));
                    if(configs && count) s->encoder->pix_fmt = static_cast<const AVPixelFormat*>(configs)[0];
                    s->encoder->width = s->decoder->width; s->encoder->height = s->decoder->height;
                    s->encoder->bit_rate = 2000000;
                } else {
                    s->encoder->sample_rate = s->decoder->sample_rate;
                    s->encoder->sample_fmt = AV_SAMPLE_FMT_FLTP;
                    check(avcodec_get_supported_config(s->encoder, enc, AV_CODEC_CONFIG_SAMPLE_FORMAT, 0, &configs, &count));
                    if(configs && count) s->encoder->sample_fmt = static_cast<const AVSampleFormat*>(configs)[0];
                    check(avcodec_get_supported_config(s->encoder, enc, AV_CODEC_CONFIG_SAMPLE_RATE, 0, &configs, &count));
                    if(configs && count) {
                        auto* rates = static_cast<const int*>(configs);
                        if(std::find(rates, rates + count, s->encoder->sample_rate) == rates + count) s->encoder->sample_rate = rates[0];
                    }
                    check(av_channel_layout_copy(&s->encoder->ch_layout, &s->decoder->ch_layout));
                    s->encoder->time_base = {1, s->encoder->sample_rate}; s->encoder->bit_rate = 128000;
                }
                if(output.ctx->oformat->flags & AVFMT_GLOBALHEADER) s->encoder->flags |= AV_CODEC_FLAG_GLOBAL_HEADER;
                initFilter(*s, in, type == AVMEDIA_TYPE_VIDEO ? task.videoFilter : task.audioFilter);
                if(type == AVMEDIA_TYPE_VIDEO) {
                    s->encoder->width = av_buffersink_get_w(s->sink); s->encoder->height = av_buffersink_get_h(s->sink);
                    s->encoder->sample_aspect_ratio = av_buffersink_get_sample_aspect_ratio(s->sink);
                }
                check(avcodec_open2(s->encoder, enc, nullptr));
                if(type == AVMEDIA_TYPE_AUDIO && s->encoder->frame_size) av_buffersink_set_frame_size(s->sink, s->encoder->frame_size);
                check(avcodec_parameters_from_context(s->output->codecpar, s->encoder));
                s->output->time_base = s->encoder->time_base;
                if(type == AVMEDIA_TYPE_VIDEO) {
                    s->output->avg_frame_rate = s->encoder->framerate;
                    s->output->r_frame_rate = s->encoder->framerate;
                }
            }
            check(av_dict_copy(&s->output->metadata, in->metadata, 0));
            streams.push_back(std::move(s));
        }
        if(!(output.ctx->oformat->flags & AVFMT_NOFILE)) check(avio_open2(&output.ctx->pb, task.output.c_str(), AVIO_FLAG_WRITE, &output.ctx->interrupt_callback, nullptr));
        check(avformat_write_header(output.ctx, nullptr));
        auto p = packet();
        for (;;) {
            if(task.cancelled) throw std::runtime_error("Cancelled");
            input.resetDeadline(); int rc = av_read_frame(input.ctx, p.get());
            if(rc == AVERROR_EOF) break;
            check(rc); auto& s = *streams.at(p->stream_index); auto* in = input.ctx->streams[p->stream_index];
            if(p->pts != AV_NOPTS_VALUE) task.processedUs.store(av_rescale_q(p->pts, in->time_base, AV_TIME_BASE_Q));
            if(s.output) {
                if(s.encoder) decode(s, output.ctx, p.get());
                else { av_packet_rescale_ts(p.get(), in->time_base, s.output->time_base); p->stream_index = s.output->index; p->pos = -1; check(av_interleaved_write_frame(output.ctx, p.get())); }
            }
            av_packet_unref(p.get());
        }
        for(auto& s : streams) if(s->encoder) {
            if(task.cancelled) throw std::runtime_error("Cancelled");
            input.resetDeadline(); decode(*s, output.ctx, nullptr);
            check(av_buffersrc_add_frame_flags(s->source, nullptr, 0)); drainFilter(*s, output.ctx);
            writeEncoded(*s, output.ctx, nullptr);
        }
        check(av_write_trailer(output.ctx)); success = true;
    } catch(...) { if(!success) std::remove(task.output.c_str()); throw; }
}
}
