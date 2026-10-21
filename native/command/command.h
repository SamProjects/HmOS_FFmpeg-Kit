#pragma once
#include <stdint.h>
#include <stdarg.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef int (*HmosCancel)(void *);
typedef void (*HmosProgress)(void *, int64_t);
typedef void (*HmosLog)(void *, const char *);
int hmos_ffmpeg_main(int argc, char **argv);
int hmos_command_run(int argc, char **argv, HmosCancel cancel, HmosProgress progress, HmosLog log, void *opaque);
int hmos_cmd_cancelled(void);
void hmos_cmd_progress(int64_t pts);
void hmos_cmd_avlog(void *ptr, int level, const char *fmt, va_list args);
int hmos_cmd_printf(const char *fmt, ...);
int hmos_cmd_fprintf(void *stream, const char *fmt, ...);
#ifdef __cplusplus
}
#endif
