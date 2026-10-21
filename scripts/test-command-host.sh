#!/usr/bin/env bash
# In-process command adapter test; does not claim HarmonyOS device execution.
set -euo pipefail
cd "$(dirname "$0")/.."
command_root="$PWD"
command_source="${1:-$PWD/work/src/ffmpeg}"
command_work="$PWD/work/command-native-test"
test -f "$command_source/RELEASE" || { echo 'Fetch the pinned sources first'; exit 2; }
test ! -e "$command_work" || { echo 'Use a fresh command test tree'; exit 2; }
mkdir -p "$command_work/build"
python3 scripts/prepare-command-source.py "$command_source" "$command_work/source"
cd "$command_work/build"
bash "$command_work/source/configure" \
  --disable-autodetect --disable-x86asm --disable-doc --disable-debug \
  --enable-version3 --disable-gpl --disable-nonfree \
  --disable-network --disable-everything --enable-ffmpeg \
  --enable-shared --disable-static --enable-pic --extra-cflags=-fPIC \
  --enable-protocol=file,pipe --enable-indev=lavfi \
  --enable-filter=sine,anull,aresample --enable-encoder=pcm_s16le \
  --enable-decoder=pcm_s16le --enable-muxer=wav,null --enable-demuxer=wav > configure.log 2>&1
if ! make -j"${JOBS:-4}" -f Makefile -f "$command_root/native/command/command.mak" \
    "HMOS_COMMAND_DIR=$command_root/native/command" libhmosffmpegcmd.so > build.log 2>&1; then
  tail -n 100 build.log; exit 1
fi
command_libs="$PWD"
for component in avutil avcodec avformat avfilter avdevice swscale swresample; do
  command_libs="$command_libs:$PWD/lib$component"
done
g++ -std=c++17 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -DHMOS_COMMAND_TEST=1 -I"$command_root/native" \
  "$command_root/native/command.cpp" "$command_root/experiments/command-execution/in-process.cpp" \
  -L"$PWD" -Wl,-rpath-link,"$command_libs" -lhmosffmpegcmd -pthread -o in-process-test
LD_LIBRARY_PATH="$command_libs" ASAN_OPTIONS=detect_leaks=1 \
  python3 "$command_root/experiments/command-execution/check-in-process.py" \
  "$PWD/in-process-test" "$command_work/result.json"
