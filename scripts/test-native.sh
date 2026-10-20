#!/usr/bin/env bash
# Host execution tests validate the public API algorithm, not OHOS runtime.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
python3 scripts/fetch-sources.py
mkdir -p work/native-test/build work/native-test/media
OUT="$ROOT/work/native-test/prefix"
( cd work/native-test/build
  bash "$ROOT/work/src/ffmpeg/configure" --prefix="$OUT" \
    --enable-shared --disable-static --disable-programs --disable-doc \
    --enable-version3 --disable-gpl --disable-nonfree --disable-autodetect \
    --disable-everything --enable-protocol=file \
    --enable-decoder=mpeg4,aac,pcm_s16le --enable-encoder=mpeg4,aac,pcm_s16le \
    --enable-demuxer=mov,matroska,wav --enable-muxer=mp4,matroska,wav \
    --enable-parser=mpeg4video,aac \
    --enable-filter=buffer,buffersink,abuffer,abuffersink,null,anull,scale,format,aformat,aresample,volume
  make -j4
  make install
)
ffmpeg -v error -f lavfi -i testsrc2=size=192x128:rate=24 -f lavfi -i sine=frequency=440:sample_rate=48000 \
  -t 2 -c:v mpeg4 -c:a aac work/native-test/media/input.mp4
g++ -std=c++17 -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer \
  -I"$OUT/include" -Inative native/engine.cpp tests/media_pipeline.cpp \
  -L"$OUT/lib" -Wl,-rpath-link,"$OUT/lib" -lavformat -lavcodec -lavfilter -lswscale -lswresample -lavutil -o work/native-test/pipeline-test
export LD_LIBRARY_PATH="$OUT/lib"
ASAN_OPTIONS=detect_leaks=1 ./work/native-test/pipeline-test "$ROOT/work/native-test/media"
unset LD_LIBRARY_PATH
for file in scaled.mp4 remux.mkv audio.wav; do
  ffmpeg -v error -i "work/native-test/media/$file" -f null -
done
python3 scripts/fetch-sources.py --verify-only
