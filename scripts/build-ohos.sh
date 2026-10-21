#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
PROFILE="${1:-extended}"
[[ "$PROFILE" == core || "$PROFILE" == extended ]] || exit 2
: "${OHOS_NATIVE:?Set native SDK directory}"
if [[ "${HMOS_COMMAND_TEST:-0}" == 1 && ( "$PROFILE" != extended || "${HMOS_HAR_ONLY:-0}" != 1 ) ]]; then
  echo 'Command test requires extended and HMOS_HAR_ONLY=1'; exit 2
fi
export LC_ALL=C TZ=UTC
export SOURCE_DATE_EPOCH="$(python3 -c 'import json; print(json.load(open("config/project.json"))["sourceDateEpoch"])')"
python3 scripts/fetch-sources.py
SDK=$(realpath "$OHOS_NATIVE")
ABI="${HMOS_ABI:-arm64-v8a}"
KEY="$PROFILE"
case "$ABI" in
  arm64-v8a) TARGET=aarch64-linux-ohos12.0.0; ARCH=aarch64; CPU=armv8-a; MARCH=armv8-a ;;
  x86_64) TARGET=x86_64-linux-ohos12.0.0; ARCH=x86_64; CPU=x86-64; MARCH=x86-64; KEY="$PROFILE-$ABI" ;;
  *) echo "Unsupported HarmonyOS application ABI: $ABI"; exit 2 ;;
esac
export HMOS_ABI="$ABI" FFMPEG_ARCH="$ARCH"
BUILD="$ROOT/work/build/$KEY"
PREFIX="$ROOT/work/prefix/$KEY"
test ! -e "$BUILD" && test ! -e "$PREFIX" || { echo 'Use a fresh build tree'; exit 2; }
mkdir -p "$BUILD" "$PREFIX"
export OHOS_WRAPPER_SDK="$SDK"
export OHOS_WRAPPER_TARGET="$TARGET"
cat > "$BUILD/cc-ohos" <<'SH'
#!/usr/bin/env bash
exec "$OHOS_WRAPPER_SDK/llvm/bin/clang" --target="$OHOS_WRAPPER_TARGET" --sysroot="$OHOS_WRAPPER_SDK/sysroot" "$@"
SH
cat > "$BUILD/cxx-ohos" <<'SH'
#!/usr/bin/env bash
exec "$OHOS_WRAPPER_SDK/llvm/bin/clang++" --target="$OHOS_WRAPPER_TARGET" --sysroot="$OHOS_WRAPPER_SDK/sysroot" "$@"
SH
chmod +x "$BUILD/cc-ohos" "$BUILD/cxx-ohos"
export CC="$BUILD/cc-ohos" CXX="$BUILD/cxx-ohos"
export AR="$SDK/llvm/bin/llvm-ar" RANLIB="$SDK/llvm/bin/llvm-ranlib"
unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH LIBRARY_PATH
export PKG_CONFIG_PATH=
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
unset PKG_CONFIG_SYSROOT_DIR
mkdir -p "$PKG_CONFIG_LIBDIR"
extra=()
if [[ "$PROFILE" == extended ]]; then
  if ! bash scripts/build-deps.sh "$BUILD/deps" "$PREFIX" > "$BUILD/deps.log" 2>&1; then
    tail -n 120 "$BUILD/deps.log"; exit 1
  fi
  echo "第三方依赖编译完成：$PROFILE $ABI（失败时输出日志摘要）"
  extra+=(--enable-libopus --enable-libvpx --enable-libmp3lame --enable-zlib --enable-mbedtls)
fi
SOURCE="$ROOT/work/src/ffmpeg"
if [[ "${HMOS_COMMAND_TEST:-0}" == 1 ]]; then
  SOURCE="$ROOT/work/command-src/$KEY"
  python3 scripts/prepare-command-source.py "$ROOT/work/src/ffmpeg" "$SOURCE"
fi
mkdir "$BUILD/ffmpeg"
cd "$BUILD/ffmpeg"
args=("--prefix=$PREFIX" --target-os=linux "--arch=$ARCH" "--cpu=$CPU"
  --enable-cross-compile "--sysroot=$SDK/sysroot"
  "--cc=$CC" "--cxx=$CXX" "--ld=$CC" "--as=$CC"
  "--host-cc=$(command -v cc)" "--ar=$AR" "--ranlib=$RANLIB"
  "--nm=$SDK/llvm/bin/llvm-nm" "--strip=$SDK/llvm/bin/llvm-strip"
  --enable-shared --disable-static --enable-pic --disable-stripping
  --enable-version3 --disable-gpl --disable-nonfree --disable-autodetect
  --disable-ffplay --disable-doc
  --enable-network --enable-pthreads --disable-linux-perf
  --disable-indevs --disable-outdevs
  "--extra-cflags=-O2 -g -fPIC -march=$MARCH -I$PREFIX/include"
  "--extra-ldflags=-fuse-ld=lld -L$PREFIX/lib -Wl,-z,relro,-z,now,--build-id=sha1"
  --extra-ldexeflags=-pie "${extra[@]}")
if [[ "${HMOS_COMMAND_TEST:-0}" == 1 ]]; then
  args+=(--enable-ffmpeg --disable-ffprobe)
elif [[ "${HMOS_HAR_ONLY:-0}" == 1 ]]; then
  args+=(--disable-programs)
else
  args+=(--enable-ffmpeg --enable-ffprobe)
fi
printf '%s\n' "${args[@]}" > configure-args.txt
if ! bash "$SOURCE/configure" "${args[@]}" > configure.log 2>&1; then
  tail -n 120 configure.log; exit 1
fi
# Library naming uses make overrides. Command-test fftools adaptations are recorded separately.
# Distinct versioned basename ending .so works with HAR native packaging.
names=('SLIBNAME_WITH_MAJOR=$(SLIBPREF)$(FULLNAME)-$(LIBMAJOR)$(SLIBSUF)'
       'SLIBNAME_WITH_VERSION=$(SLIBNAME_WITH_MAJOR)'
       'SLIB_INSTALL_NAME=$(SLIBNAME_WITH_MAJOR)'
       'SLIB_INSTALL_LINKS=$(SLIBNAME)')
echo "开始 FFmpeg 编译：$PROFILE $ABI（完整命令写入临时 build.log）"
build_args=(V=1 "${names[@]}")
install_args=(install "${names[@]}")
if [[ "${HMOS_COMMAND_TEST:-0}" == 1 ]]; then
  build_args+=(-f Makefile -f "$ROOT/native/command/command.mak" "HMOS_COMMAND_DIR=$ROOT/native/command" libhmosffmpegcmd.so)
  install_args=(install-libs install-headers "${names[@]}")
fi
if ! make -j"${JOBS:-4}" "${build_args[@]}" > build.log 2>&1; then
  tail -n 120 build.log; exit 1
fi
if ! make "${install_args[@]}" > install.log 2>&1; then
  tail -n 120 install.log; exit 1
fi
if [[ "${HMOS_COMMAND_TEST:-0}" == 1 ]]; then
  cp libhmosffmpegcmd.so "$PREFIX/lib/"
fi
echo "FFmpeg 编译与安装完成：$PROFILE $ABI"
cd "$ROOT"
python3 scripts/fetch-sources.py --verify-only
python3 scripts/verify-build.py "$PROFILE"
FFMPEG_PREFIX="$PREFIX" cmake -S native -B "$BUILD/bridge" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$SDK/build/cmake/ohos.toolchain.cmake" \
  "-DOHOS_ARCH=$ABI" -DOHOS_COMPATIBLE_SDK_VERSION=12 \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build "$BUILD/bridge" --parallel "${JOBS:-4}"
python3 scripts/package.py "$PROFILE"
