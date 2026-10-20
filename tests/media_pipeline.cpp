#include "engine.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
using namespace hmosffmpeg;
void require(bool condition, const char* message) { if(!condition) throw std::runtime_error(message); }
int main(int argc, char** argv) {
    if(argc != 2) return 2;
    std::string root = argv[1];
    try {
        Task original; original.input = root + "/input.mp4";
        require(probe(original).find("\"width\":192") != std::string::npos, "input probe mismatch");
        Task remux; remux.input = original.input; remux.output = root + "/remux.mkv"; remux.operation = "remux";
        convert(remux); Task copied; copied.input = remux.output;
        require(probe(copied).find("\"width\":192") != std::string::npos, "remux mismatch");
        Task video; video.input = original.input; video.output = root + "/scaled.mp4"; video.operation = "transcode";
        video.videoCodec = "mpeg4"; video.audioCodec = "aac"; video.videoFilter = "scale=96:64"; video.audioFilter = "volume=0.5";
        convert(video); Task scaled; scaled.input = video.output;
        require(probe(scaled).find("\"width\":96") != std::string::npos, "scale mismatch");
        Task audio; audio.input = original.input; audio.output = root + "/audio.wav"; audio.operation = "transcode";
        audio.videoCodec = "none"; audio.audioCodec = "pcm_s16le";
        convert(audio); require(std::filesystem::file_size(audio.output) > 10000, "audio empty");
        bool rejected = false;
        try { convert(video); } catch(const std::exception&) { rejected = true; }
        require(rejected && std::filesystem::exists(video.output), "existing output was overwritten or removed");
        Task cancelled; cancelled.input = original.input; cancelled.output = root + "/cancelled.mp4";
        cancelled.operation = "remux"; cancelled.cancelled = true; rejected = false;
        try { convert(cancelled); } catch(const std::exception&) { rejected = true; }
        require(rejected && !std::filesystem::exists(cancelled.output), "cancel failed to clean partial output");
        Task invalid; invalid.input = original.input; invalid.output = root + "/invalid.mp4";
        invalid.operation = "transcode"; invalid.videoCodec = "does_not_exist";
        rejected = false; try { convert(invalid); } catch(const std::exception&) { rejected = true; }
        require(rejected && !std::filesystem::exists(invalid.output), "unsupported codec failed to clean output");
        std::cout << "Public API pipeline integration tests passed\n";
    } catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
