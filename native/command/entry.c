/* Experimental serial command component; FFmpeg remains separately linked. */
#include "command.h"
#include <pthread.h>
#include <stdio.h>
#include <libavutil/log.h>

int hmos_ffmpeg_main(int argc, char **argv);
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static HmosCancel cancel_cb;
static HmosProgress progress_cb;
static HmosLog log_cb;
static void *context;

int hmos_cmd_cancelled(void) { return cancel_cb && cancel_cb(context); }
void hmos_cmd_progress(int64_t pts) { if (progress_cb) progress_cb(context, pts); }
void hmos_cmd_avlog(void *ptr, int level, const char *fmt, va_list args)
{
    char buffer[4096];
    (void)ptr;
    if (level > av_log_get_level()) return;
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    if (log_cb) log_cb(context, buffer);
}
int hmos_cmd_printf(const char *fmt, ...)
{
    char buffer[4096];
    va_list args;
    va_start(args, fmt);
    int size = vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    if (log_cb) log_cb(context, buffer);
    return size;
}
int hmos_cmd_fprintf(void *stream, const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    int size;
    if (stream == stdout || stream == stderr) {
        char buffer[4096];
        size = vsnprintf(buffer, sizeof(buffer), fmt, args);
        if (log_cb) log_cb(context, buffer);
    } else size = vfprintf((FILE *)stream, fmt, args);
    va_end(args);
    return size;
}
__attribute__((visibility("default")))
int hmos_command_run(int argc, char **argv, HmosCancel cancel, HmosProgress progress, HmosLog log, void *opaque)
{
    if (pthread_mutex_trylock(&lock)) return -16;
    int level = av_log_get_level(), flags = av_log_get_flags();
    cancel_cb = cancel; progress_cb = progress; log_cb = log; context = opaque;
    av_log_set_level(AV_LOG_INFO);
    av_log_set_callback(hmos_cmd_avlog);
    int result = hmos_ffmpeg_main(argc, argv);
    if (hmos_cmd_cancelled()) result = 255;
    av_log_set_callback(av_log_default_callback);
    av_log_set_level(level); av_log_set_flags(flags);
    cancel_cb = NULL; progress_cb = NULL; log_cb = NULL; context = NULL;
    pthread_mutex_unlock(&lock);
    return result;
}
