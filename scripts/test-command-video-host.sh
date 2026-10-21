#!/usr/bin/env bash
# Actual in-process FFmpeg 9.0.2 tests; no HarmonyOS runtime claim.
set -euo pipefail
cd "$(dirname "$0")/.."
video_root="$PWD"
video_source="${VIDEO_COMMAND_SOURCE:-$PWD/work/command-src/extended}"
video_build="$PWD/work/video-host-build"
if [ "$#" -ne 2 ]; then echo 'Usage: bash scripts/test-command-video-host.sh original.mp4 compatible.mp4'; exit 2; fi
video_original="$(realpath "$1")"
video_compatible="$(realpath "$2")"
test -f "$video_source/hmos-command-adaptation.json"
mkdir -p "$video_build"
cd "$video_build"
bash "$video_source/configure" \
  --disable-autodetect --disable-x86asm --disable-doc --disable-debug --disable-network \
  --disable-everything --enable-ffmpeg --disable-ffprobe --enable-shared --disable-static \
  --enable-pic --extra-cflags=-fPIC --enable-protocol=file,pipe --enable-indev=lavfi \
  --enable-filter=sine,anull,aresample,aformat,format,null,scale,crop,transpose,fps,hue,hflip,volume,atempo \
  --enable-encoder=mpeg4,aac,pcm_s16le,png,mjpeg,wrapped_avframe \
  --enable-decoder=mpeg4,aac,av1,pcm_s16le,png,mjpeg \
  --enable-muxer=mp4,matroska,wav,null,image2,adts,ipod \
  --enable-demuxer=mov,matroska,wav,image2,png_pipe,jpeg_pipe \
  --enable-parser=av1,mpeg4video,aac --enable-zlib > configure.log 2>&1
make -j"${JOBS:-4}" -f Makefile -f "$video_root/native/command/command.mak" \
  "HMOS_COMMAND_DIR=$video_root/native/command" libhmosffmpegcmd.so > build.log 2>&1
video_libs="$video_build"
for component in avutil avcodec avformat avfilter avdevice swscale swresample; do
  video_libs="$video_libs:$video_build/lib$component"
done
# Instrument the C++ adapter and test driver. The FFmpeg libraries are not instrumented.
g++ -std=c++17 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -DHMOS_COMMAND_TEST=1 -I"$video_root/native" "$video_root/native/command.cpp" \
  "$video_root/experiments/command-execution/video-matrix.cpp" \
  -L"$video_build" -Wl,-rpath-link,"$video_libs" -lhmosffmpegcmd -pthread -o video-matrix-asan
cd "$video_root"
LD_LIBRARY_PATH="$video_libs" ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
  python3 scripts/test-command-video-host.py --executable "$video_build/video-matrix-asan" \
  --original "$video_original" --compatible "$video_compatible" --output work/video-test/asan-results
