#!/usr/bin/env bash
# Actual in-process FFmpeg 9.0.2 tests; no HarmonyOS runtime claim.
set -euo pipefail
cd "$(dirname "$0")/.."
video_root="$PWD"
video_source="${VIDEO_COMMAND_SOURCE:-$PWD/work/command-src/extended}"
video_build="${VIDEO_BUILD_DIR:-$PWD/work/expanded-host-ffmpeg}"
if [ "$#" -ne 2 ]; then echo 'Usage: bash scripts/test-command-video-host.sh original.mp4 compatible.mp4'; exit 2; fi
video_original="$(realpath "$1")"
video_compatible="$(realpath "$2")"
test -f "$video_source/hmos-command-adaptation.json"
mkdir -p "$video_build"
cd "$video_build"
video_prefix="${VIDEO_CODEC_PREFIX:-$video_root/work/codec-prefix/host}"
export PKG_CONFIG_PATH= PKG_CONFIG_LIBDIR="$video_prefix/lib/pkgconfig"
mapfile -t video_codec_flags < <(python3 -c 'import json; print("\n".join(flag for dep in json.load(open("'"$video_root"'/config/codec-dependencies.json")).values() for flag in dep["ffmpegFlags"]))')
video_encoders="$(python3 -c 'import json; print(",".join(name.removesuffix("_ENCODER").lower() for dep in json.load(open("'"$video_root"'/config/codec-dependencies.json")).values() for name in dep["requiredComponents"] if name.endswith("_ENCODER")))')"
video_decoders="$(python3 -c 'import json; print(",".join(name.removesuffix("_DECODER").lower() for dep in json.load(open("'"$video_root"'/config/codec-dependencies.json")).values() for name in dep["requiredComponents"] if name.endswith("_DECODER")))')"
bash "$video_source/configure" "--prefix=$video_prefix" \
  --disable-autodetect --disable-x86asm --disable-doc --disable-debug --disable-network --optflags=-O1 \
  --disable-everything --enable-version3 --disable-gpl --disable-nonfree \
  --enable-ffmpeg --disable-ffprobe --enable-shared --disable-static --enable-pic \
  "--extra-cflags=-fPIC -I$video_prefix/include" "--extra-ldflags=-L$video_prefix/lib" \
  '--extra-libs=-lstdc++ -lm -pthread' --pkg-config-flags=--static \
  --enable-libopus --enable-libvpx --enable-libmp3lame --enable-zlib "${video_codec_flags[@]}" \
  --enable-protocol=file,pipe --enable-indev=lavfi --enable-parsers \
  --enable-filter=sine,anull,aresample,aformat,format,null,scale,crop,transpose,fps,hue,hflip,volume,atempo \
  "--enable-encoder=mpeg4,aac,pcm_s16le,png,mjpeg,wrapped_avframe,libopus,libvpx_vp8,libvpx_vp9,libmp3lame,$video_encoders" \
  "--enable-decoder=mpeg4,aac,av1,pcm_s16le,png,mjpeg,jpeg2000,h264,hevc,vvc,apv,vp8,vp9,theora,mp3,mp2,opus,amrnb,amrwb,gsm,gsm_ms,ilbc,$video_decoders" \
  --enable-muxer=mp4,matroska,wav,null,image2,adts,ipod,webm,ogg,mp3,mp2,amr,ilbc,gsm,lc3,codec2,evc,vvc,mov,hevc \
  --enable-demuxer=mov,matroska,wav,image2,png_pipe,jpeg_pipe,jpeg2000_pipe,jpegxl_pipe,jpegxl_anim,ogg,mp3,amr,ilbc,gsm,lc3,codec2,evc,vvc,hevc \
  --enable-bsf=h264_mp4toannexb,hevc_mp4toannexb,vvc_mp4toannexb,extract_extradata,evc_frame_merge,aac_adtstoasc \
  > configure.log 2>&1
make -j"${JOBS:-4}" -f Makefile -f "$video_root/native/command/command.mak" \
  "HMOS_COMMAND_DIR=$video_root/native/command" libhmosffmpegcmd.so > build.log 2>&1
make install-headers > install-headers.log 2>&1
video_libs="$video_build"
for component in avutil avcodec avformat avfilter avdevice swscale swresample; do
  video_libs="$video_libs:$video_build/lib$component"
done
# Instrument the C++ adapter and test driver. The FFmpeg libraries are not instrumented.
g++ -std=c++17 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -DHMOS_COMMAND_TEST=1 -I"$video_root/native" -I"$video_prefix/include" "$video_root/native/command.cpp" "$video_root/native/engine.cpp" \
  "$video_root/experiments/command-execution/video-matrix.cpp" \
  -L"$video_build" -L"$video_build/libavformat" -L"$video_build/libavcodec" -L"$video_build/libavfilter" -L"$video_build/libswscale" -L"$video_build/libswresample" -L"$video_build/libavutil" -Wl,-rpath-link,"$video_libs" -lhmosffmpegcmd -lavformat -lavcodec -lavfilter -lswscale -lswresample -lavutil -pthread -o video-matrix-asan
cd "$video_root"
LD_LIBRARY_PATH="$video_libs" ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
  python3 scripts/test-command-video-host.py --executable "$video_build/video-matrix-asan" \
  --original "$video_original" --compatible "$video_compatible" --output work/video-test/asan-results
