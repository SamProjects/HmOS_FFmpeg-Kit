#!/usr/bin/env bash
set -euo pipefail
ROOT="$PWD"
BUILD="$1"
PREFIX="$2"
mkdir -p "$BUILD"
cmake_args=(-DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=aarch64
  "-DCMAKE_C_COMPILER=$CC" "-DCMAKE_CXX_COMPILER=$CXX"
  "-DCMAKE_AR=$AR" "-DCMAKE_RANLIB=$RANLIB"
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DCMAKE_BUILD_TYPE=Release
  "-DCMAKE_INSTALL_PREFIX=$PREFIX" -DBUILD_SHARED_LIBS=OFF)
cmake -S "$ROOT/work/src/opus" -B "$BUILD/opus" -G Ninja "${cmake_args[@]}" \
  -DOPUS_BUILD_TESTING=OFF -DOPUS_BUILD_PROGRAMS=OFF
cmake --build "$BUILD/opus" --parallel "${JOBS:-4}"
cmake --install "$BUILD/opus"
cmake -S "$ROOT/work/src/mbedtls" -B "$BUILD/mbedtls" -G Ninja "${cmake_args[@]}" \
  -DENABLE_TESTING=OFF -DENABLE_PROGRAMS=OFF -DUSE_SHARED_MBEDTLS_LIBRARY=OFF
cmake --build "$BUILD/mbedtls" --parallel "${JOBS:-4}"
cmake --install "$BUILD/mbedtls"
mkdir -p "$BUILD/zlib"
( cd "$BUILD/zlib"
  CHOST=aarch64-linux-ohos CFLAGS=-fPIC "$ROOT/work/src/zlib/configure" --static --prefix="$PREFIX"
  make -j"${JOBS:-4}"
  make install
)
mkdir -p "$BUILD/lame" "$BUILD/vpx"
( cd "$BUILD/lame"
  "$ROOT/work/src/lame/configure" --host=aarch64-linux --prefix="$PREFIX" \
    --disable-shared --enable-static --disable-frontend --disable-gtktest \
    CFLAGS=-fPIC
  make -j"${JOBS:-4}"
  make install
)
( cd "$BUILD/vpx"
  AS="$CC" LD="$CC" CFLAGS=-fPIC "$ROOT/work/src/libvpx/configure" \
    --target=arm64-linux-gcc --prefix="$PREFIX" --enable-pic \
    --disable-shared --enable-static --disable-examples --disable-tools \
    --disable-docs --disable-unit-tests --enable-vp9-highbitdepth
  make -j"${JOBS:-4}"
  make install
)
# LAME does not install a pkg-config file in this release.
cat > "$PREFIX/lib/pkgconfig/lame.pc" <<PC
prefix=$PREFIX
libdir=\${prefix}/lib
includedir=\${prefix}/include
Name: lame
Description: LAME MP3 encoder
Version: 3.100
Libs: -L\${libdir} -lmp3lame -lm
Cflags: -I\${includedir}
PC
