# 官方原版 FFmpeg 的 HarmonyOS NDK 交叉编译方案

面向 Codex 的开发任务书 · 2026-10-20 · 版本 1.0

目标仓库：`SamProjects/HmOS_FFmpeg-Kit`。本文是实施规范和构建模板，不是已经通过 HarmonyOS 编译、上架审核或真机测试的报告。

实施入口：实际可执行配方以仓库 `scripts/`、`config/` 和工作流为准，本文代码块用于解释基线。当前实现使用外置 GNU make 参数生成 `libavcodec-63.so` 等库名，不修改源码或 ELF；依赖安装到独立绝对 prefix，清空 `PKG_CONFIG_SYSROOT_DIR`，避免重复 staging 路径。对应 HAR 使用方法见 `INTEGRATION.zh-CN.md`。按用户要求，CI 不保存 Actions Artifacts，也不使用持久缓存；候选成品直接发布到标明验证边界的 Release 预发布版。

2026-10-21 用户授权的实验例外：`HMOS_COMMAND_TEST=1` 的命令执行测试版允许在隔离复制树中适配 fftools，记录完整差异并以独立动态库交付，不宣称命令组件零补丁；默认普通构建仍遵守原约束。实施和测试范围见 [命令测试版说明](COMMAND-TEST.zh-CN.md)。

## 1. 目标与不可突破的边界

使用 FFmpeg 官方最新稳定发布源码，Zero-Patch，通过 HarmonyOS Native SDK 内的 clang 交叉编译出 arm64-v8a 共享库。构建采用 LGPLv3-or-later 口径，禁止 GPL、nonfree 组件；在平台能力和许可允许的范围内尽可能保留编解码、封装、滤镜、协议和探测功能。

截至本文核查日期，官方下载页列出的最新稳定主版本为 **9.0.2**，发布于 2026-09-18。实施时再次核查官方下载页，随后把确定的版本、源码 SHA-256、签名、签名密钥指纹锁定；不能让普通 CI 每次追踪 latest/master。[官方下载页](https://ffmpeg.org/download.html)

必须同时交付：共享库 SDK、官方 ffmpeg/ffprobe 命令行构建产物、闭源 Engine 集成设计、功能清单、构建与许可证据。命令行在开发设备 shell 中运行，和在商用 App 沙箱内运行，是两个独立验收项。

绝对禁止：

- 修改、替换、复制后改写 upstream 的 `configure`、`Makefile`、`ffbuild/**`、`libav*/**`、`libsw*/**`、`compat/**`、`fftools/**`、头文件、汇编、版本文件、许可或版权声明。
- 用 sed/patch/git apply 修改 FFmpeg；向源码目录注入私有 codec、NAPI、日志回调、取消逻辑或平台适配；从社区 fork 搬补丁后称为官方原版。
- 手工修改生成的 `config.h`、`config_components.h`、`ffbuild/config.mak` 强行通过检查；强制伪造 HAVE_* 或隐藏缺失 API。
- 修改 `ffmpeg.c`/`ffprobe.c` 的 main、把 exit 改为 return、用宏重命名 main 然后嵌进闭源 so；复制 fftools 实现到私有目录规避边界。
- 将 FFmpeg 静态库或对象合入闭源 Engine；开启跨边界 LTO；删除 notice；声称“动态链接就自动完成所有 LGPL 义务”。
- `--enable-gpl`、`--enable-nonfree`；`--enable-libx264`、`--enable-libx265`、`--enable-libxvid`、`--enable-libfdk-aac` 等不在本项目许可白名单内的功能。
- 向 FFmpeg 内部注册 OHOS codec 或链接其私有内部符号；硬件功能一律走独立 HarmonyOS AVCodec Engine。

允许：外置构建脚本、编译器 wrapper、标准 configure 开关、独立依赖构建、CMake imported target、调用 FFmpeg 公共 API 的私有代码，以及有记录的产物打包。默认不修改生成构建文件和 ELF；确有命名障碍时仅按第 8 节的显式方案处理。

## 2. 总体架构及能力定义

```text
ArkTS / ArkUI / UI / 业务逻辑（闭源）
                │ NAPI 异步接口
                ▼
HarmonyOS Media Engine（闭源、原创）
 ├─ Session / Queue / Cancel / Progress / 文件权限 / 参数解析
 ├─ Software Pipeline ──动态链接── 官方 libav*.so / libsw*.so
 └─ Hardware Pipeline ──系统 API── HarmonyOS AVCodec Engine

官方 ffmpeg / ffprobe 可执行文件（独立构建，不嵌入闭源 Engine）
 └─ 仅在目标环境允许执行时，走受控 argv + 进程 + 管道
```

“完整”指平台上可用且许可允许的功能尽量保留，不指 Windows/Linux 全部功能，也不指所有编码器。GPL 滤镜/编码器、没有驱动的设备、平台专用协议或不可移植后端不能靠开关变为可用。

原生 AAC、FLAC、PCM 等能力以产物实际枚举为准；不承诺不含 x264/x265 的构建具有等价 H.264/HEVC 软件编码能力。需要 H.264/HEVC 编码时，由私有硬件引擎查询设备实际能力并协商；不支持时明确报告或提供用户接受的其他编码格式。

硬件管线可用 libavformat 解封装/封装、libswscale 转换；应用负责 AVPacket 数据、extradata、时间基、Annex B/长度前缀格式、stride、像素格式和时间戳适配。交互只经过公共 API 和自有缓冲区，不把 HarmonyOS 实现塞回 libavcodec。

## 3. Codex 按阶段实施

| 阶段 | 要做什么 | 完成证据 |
|---|---|---|
| P0 环境 | 确认实际 checkout、分支、AGENTS.md、SDK、主机、最低 API；有 .codegraph 时先用 CodeGraph 理解代码 | environment.json、SDK 元数据、工具版本 |
| P1 信任与零修改 | 锁定官方源码、验签、哈希清单、源外构建 | sources.lock.json、source-integrity.json |
| P2 可行性 | clang hello/so、FFmpeg 无外部依赖基线、CLI 链接 | config.log、完整命令、ELF 报告 |
| P3 加载 | 检查 SONAME/HAP；最小 NAPI 调 av_version_info | 打包清单、目标设备日志 |
| P4 扩展 | 按依赖白名单逐个加功能，不自动引入主机依赖 | SBOM、依赖锁、功能差异 |
| P5 引擎 | 自有软件管线、探测、异步日志、取消；独立硬件管线 | 样本输出、取消/并发测试 |
| P6 发布 | LGPL 替换路径、源码包、notice、CI 与设备 gate | 已关联提交的发布证据 |

先完成 P2/P3 的可行性验证，再做大规模依赖移植。不要先搭完整 UI 后才验证动态库能否装载。失败要按阶段返回，不自动改成带补丁 fork。

## 4. 推荐目录

```text
HmOS_FFmpeg-Kit/
  README.md                         # 本开发规范或规范入口
  docs/architecture.md
  docs/build-ohos.md
  docs/capabilities.md
  docs/replacement-and-relink.md
  config/sources.lock.json
  config/dependencies.lock.json
  config/profiles/{core,extended}.json
  config/required-capabilities.json
  scripts/fetch-sources.py
  scripts/verify-source-tree.py
  scripts/build-ohos.sh
  scripts/build-ohos.ps1              # Windows 入口，明确使用的 shell
  scripts/build-deps.sh
  scripts/package-sdk.py
  scripts/license-gate.py
  scripts/verify-elf.py
  scripts/device-smoke.sh
  cmake/FFmpegImported.cmake
  examples/ohos-smoke/                # 原创 NAPI 最小应用
  tests/fixtures/                     # 有来源及许可的小媒体
  .github/workflows/{verify,build,release}.yml
  work/downloads/                    # 忽略，不提交 SDK/凭据
  work/src/ffmpeg-<version>/          # 只读、干净的原始源码
  work/build/<profile>/arm64-v8a/     # 所有生成文件在这里
  work/prefix/<profile>/arm64-v8a/    # make install 原始输出
  dist/<version>/<profile>/arm64-v8a/
```

本仓库负责可公开的构建配方和 FFmpeg 集成 SDK。私有 Media Engine 留在私有应用仓库；依赖边界使用 SDK 公共头和 so。仓库名称不意味着复用 FFmpegKit 的源码、会话机制或修改方案。

## 5. SDK、主机和工具链锁定

使用面向目标商用 HarmonyOS App 的 **HarmonyOS Native SDK**。OpenHarmony 的构建代码可作参数参考，但不能直接宣称任意 OpenHarmony 系统 SDK 与商用设备 ABI/API 等价。

统一环境变量 `OHOS_NATIVE` 指向同时包含 `llvm/`、`sysroot/`、`build/cmake/ohos.toolchain.cmake` 的 native 目录，不指向外层 SDK。记录 SDK 完整版本、API、host OS/arch、clang 版本、工具链文件哈希。不要把绝对路径硬编码进锁文件。

| 项目 | 基线 |
|---|---|
| 目标 ABI | arm64-v8a，ELF AArch64；不是 Android 二进制 |
| clang target | `aarch64-linux-ohos`；是否需 API 后缀按实际 SDK toolchain 确认 |
| sysroot | `$OHOS_NATIVE/sysroot` |
| C / C++ | `$OHOS_NATIVE/llvm/bin/clang`、`clang++` |
| linker | clang driver + `-fuse-ld=lld`，不直接拿 ld.lld 替代 driver |
| binutils | 同一 SDK 的 llvm-ar、llvm-ranlib、llvm-nm、llvm-strip、llvm-readelf、llvm-objcopy |
| hostcc | 本机构建工具的 C 编译器，绝不能设成目标 clang wrapper |
| CMake | SDK 附带或经验证兼容版本，加载其 ohos.toolchain.cmake |
| 基线目标 CPU | armv8-a，不使用构建机 `-march=native` |

ABI 与 triple 映射有 OpenHarmony 官方工具链可供参考；以安装 SDK 的实际文件为最终依据。[官方工具链参考](https://github.com/openharmony/build/blob/master/ohos/ndk/cmake/ohos.toolchain.cmake)

构建宿主不是本方案的 ABI 要求。下方模板使用 Linux Bash、GNU make、Python 3 和与 Linux 匹配的 SDK；它没有在本次工作中运行。Windows 使用者应先探测现有原生 SDK 和 MSYS2/Git Bash/Make 组合，或使用已获授权的 Linux CI。不得擅自安装 WSL、换远程构建或下载整套工具链。不同宿主不得混用 SDK 的可执行文件；Windows 入口应处理 `.exe` 和 POSIX 路径转换。

最低 API 必须从项目兼容目标导出，并与 Hvigor/CMake 一致；不能用最新 SDK 编过就假设兼容最低系统。读取当前 SDK toolchain 的 target 选择逻辑，记录最终 clang `-###` 输出。不要照搬 Android 的 `aarch64-linux-androidXX`、`__ANDROID__`、bionic 或 Android NDK 库。

## 6. 官方源码获取与 Zero-Patch 证据

Codex 实现 `fetch-sources.py`：只允许 HTTPS 官方 release 地址；版本必须精确锁定。下载 `.tar.xz` 及 `.asc`，使用仓库锁定的可信发布密钥指纹验证签名，再验证锁文件 SHA-256。首次建立哈希只能在可信签名通过后由维护流程写入，不能信任同一下载通道中未经认证的新哈希。

锁文件最少包含：`version`、`url`、`sha256`、`signature_url`、`signing_fingerprint`、SDK 身份、host tools 版本和 profile。首次未知字段必须明确为空/待填并让构建拒绝，绝不写示例假哈希当真值。

解包前拒绝路径穿越、绝对路径和危险符号链接。建立每个原始文件的路径/类型/权限/内容哈希及链接目标清单。configure、make、install 前后都验证：没有改动、删除、额外文件。源外构建中生成指向源码的正常链接不算源码修改；源树内新增生成文件仍视为失败。

可用文件系统只读挂载强化约束；单纯 chmod 对管理员不是充分证据。Git 源码的 `git diff --exit-code` 只能作辅助，还要查 untracked 和 ignored 文件。发布保留原始 tarball、签名、哈希清单、空 changes.diff 和清楚标注的“无源码补丁”说明。构建配方放在外层 bundle，不向原始源码目录新增 README。

## 7. configure 基线和构建模板

本次核查的 n9.0.2 configure 没有原生 `ohos` 分支。因此 **`--target-os=linux` 是待实际 SDK 验证的构建策略**；它不把产物变成通用 Linux 库，真实 ABI 由 OHOS clang target 和 sysroot 决定。[锁定版本 configure](https://github.com/FFmpeg/FFmpeg/blob/n9.0.2/configure)

基线使用 `--disable-autodetect` 隔离外部库，不用 `--disable-everything`；内置且被探测为可用的 LGPL 功能保持默认。core 不包含外部 TLS、字体等依赖，因此不是功能最终形态。ffplay 暂不交付，App 播放走独立系统能力。

以下保存为 `scripts/build-ohos.sh` 的起点。其职责仅为**干净构建**；下载验签、源码完整性、打包、许可 gate 和设备测试由各自脚本执行，CI 必须串联执行，不能把此脚本成功等同发布完成。

```bash
#!/usr/bin/env bash
set -euo pipefail
: "${OHOS_NATIVE:?set native SDK directory}"
: "${FF_SRC:?set verified pristine FFmpeg source directory}"
: "${BUILD_DIR:?set new out-of-tree build directory}"
: "${PREFIX:?set empty installation prefix}"
export LC_ALL=C
export TZ=UTC
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:?set locked release timestamp}"

SDK=$(realpath "$OHOS_NATIVE")
SRC=$(realpath "$FF_SRC")
BUILD=$(realpath -m "$BUILD_DIR")
OUT=$(realpath -m "$PREFIX")
# 简化模板拒绝空格路径；Windows 入口需单独处理，不能悄悄拆参数。
for p in "$SDK" "$SRC" "$BUILD" "$OUT"; do
  [[ "$p" != *[[:space:]]* ]] || { echo 'Use paths without whitespace'; exit 2; }
done
case "$BUILD/" in "$SRC/"*) echo 'Build must be outside source'; exit 2;; esac
case "$OUT/" in "$SRC/"*) echo 'Prefix must be outside source'; exit 2;; esac
[[ "$BUILD" != "$OUT" ]] || exit 2
[[ ! -e "$BUILD" && ! -e "$OUT" ]] || {
  echo 'Use fresh build and prefix paths'; exit 2;
}
BIN="$SDK/llvm/bin"
for t in clang clang++ llvm-ar llvm-ranlib llvm-nm llvm-strip; do
  test -x "$BIN/$t"
done
test -d "$SDK/sysroot"
test -f "$SRC/configure"
HOST_C=$(command -v cc)
mkdir -p "$BUILD" "$OUT"
cd "$BUILD"

# wrapper 保证 configure 的编译、汇编、链接探测都使用相同 target。
export OHOS_WRAPPER_SDK="$SDK"
export OHOS_WRAPPER_TARGET="${OHOS_TARGET:-aarch64-linux-ohos}"
cat > cc-ohos <<'SH'
#!/usr/bin/env bash
exec "$OHOS_WRAPPER_SDK/llvm/bin/clang" \
  --target="$OHOS_WRAPPER_TARGET" \
  --sysroot="$OHOS_WRAPPER_SDK/sysroot" "$@"
SH
cat > cxx-ohos <<'SH'
#!/usr/bin/env bash
exec "$OHOS_WRAPPER_SDK/llvm/bin/clang++" \
  --target="$OHOS_WRAPPER_TARGET" \
  --sysroot="$OHOS_WRAPPER_SDK/sysroot" "$@"
SH
chmod +x cc-ohos cxx-ohos

# 不允许 pkg-config 回落到宿主库。core 不提供外部依赖。
unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH LIBRARY_PATH
export PKG_CONFIG_PATH=
export PKG_CONFIG_LIBDIR="$BUILD/empty-pkgconfig"
mkdir -p "$PKG_CONFIG_LIBDIR"
export PKG_CONFIG_SYSROOT_DIR="$SDK/sysroot"
cat > hello.c <<'C'
int main(void) { return 0; }
C
./cc-ohos -### hello.c -o hello 2> compiler-driver.txt
./cc-ohos hello.c -o hello
./cc-ohos -fPIC -shared hello.c -o libhello.so

args=(
  "--prefix=$OUT"
  --target-os=linux --arch=aarch64 --cpu=armv8-a
  --enable-cross-compile
  "--sysroot=$SDK/sysroot"
  "--cc=$BUILD/cc-ohos" "--cxx=$BUILD/cxx-ohos"
  "--ld=$BUILD/cc-ohos" "--as=$BUILD/cc-ohos"
  "--host-cc=$HOST_C"
  "--ar=$BIN/llvm-ar" "--ranlib=$BIN/llvm-ranlib"
  "--nm=$BIN/llvm-nm" "--strip=$BIN/llvm-strip"
  --enable-shared --disable-static --enable-pic
  --enable-version3 --disable-gpl --disable-nonfree
  --disable-autodetect --disable-ffplay --disable-doc
  --enable-ffmpeg --enable-ffprobe --enable-network --enable-pthreads
  --disable-linux-perf
  '--extra-cflags=-O2 -fPIC -march=armv8-a'
  '--extra-ldflags=-fuse-ld=lld -Wl,-z,relro -Wl,-z,now'
  --disable-stripping
)
printf '%s\n' "${args[@]}" > configure-args.txt
bash "$SRC/configure" "${args[@]}" 2>&1 | tee configure.log
make -j"${JOBS:-4}" V=1 2>&1 | tee build.log
make install 2>&1 | tee install.log
```

使用前：外置 integrity 脚本验源码、确认 SDK/最低 API/target，设置锁定的 `SOURCE_DATE_EPOCH`，选择尚不存在的 BUILD_DIR/PREFIX。构建结束后再次验源码，再做 ELF/license gate。该脚本不删除目录；重试使用新目录，避免旧对象污染。

具体开关要对照所锁版本 `configure --help` 和探测日志。不要无证据添加 `-D__MUSL__`、`-D_GNU_SOURCE`、`-Wno-error` 或整批禁用汇编；如 SDK 有明确要求，将其作为可追踪 profile 配置并解释来源。保留 NEON/汇编，只有定位到具体工具链不兼容后才做临时 C-only 诊断构建。

CLI 若需显式 PIE，先核查该 SDK 默认链接行为和 ELF program headers，再经验证加入 `--extra-ldexeflags=-pie`；不要把 `-pie` 全局用于共享库。不默认开启 LTO、裁剪所有符号或隐藏 FFmpeg 公共导出。

### 7.1 扩展依赖的 pkg-config 隔离

extended 必须显式启用已审计的库，例如 zlib、libopus、libdav1d、libvpx、libass、libfreetype、libharfbuzz、mbedtls；实际选项名称与存在性以锁定 configure 为准。每新增一库：单独交叉编译、验证目标 ELF、审查依赖递归树，再启用 FFmpeg 开关。

将依赖安装进独立目标 rootfs，保持 `.pc` 中 prefix 为 rootfs 内的逻辑路径（如 `/usr`）；设置 `PKG_CONFIG_SYSROOT_DIR=<该rootfs>`，`PKG_CONFIG_LIBDIR=<该rootfs>/usr/lib/pkgconfig:<该rootfs>/usr/share/pkgconfig`，清空 PKG_CONFIG_PATH。编译器的 `--sysroot` 仍指 SDK。禁止对已含 staging 绝对路径的 `.pc` 再机械叠加 sysroot；保存 `pkg-config --cflags --libs` 输出，发现 `/usr/include`、宿主 `/usr/lib` 或错误双重路径即失败。

## 8. SONAME、产物布局与鸿蒙打包

不要先假设 `libavcodec.so` 这个文件名足够。FFmpeg Linux 构建通常使用版本化库和 SONAME；Codex 必须检查 **每个库及 CLI 的 DT_NEEDED**，再检查 HAP 内真实条目和 loader 可见名称。复制或重命名文件不会自动修改 SONAME/NEEDED。

```text
dist/<version>/<profile>/arm64-v8a/
  sdk/include/{libavcodec,libavformat,libavutil,...}/
  sdk/lib/                           # 原始版本链、链接用 .so、pkgconfig
  runtime/                          # HAP 所需真实文件，依赖闭包齐全
  bin/{ffmpeg,ffprobe}               # OHOS ELF，不是 Windows exe
  symbols/                          # llvm-objcopy 生成的独立调试符号
  licenses/                         # 原文许可、第三方 notices
  sources/                          # 精确源码包和签名，或同包独立附件
  manifest.json                     # 哈希、SDK、API、ABI、版本、profile
  sbom.spdx.json
  evidence/{config,elf,capabilities,device,license}/
```

命名处理优先级：

1. 保留原始 SONAME，验证 Hvigor/HAP 能否打包对应真实文件并在 App 进程加载；链接符号链接在 Windows/ZIP 中可能消失，不把它们当运行期文件。
2. 若实际 SDK 强制 `.so` 结尾，先验证原始构建是否有可支持的无补丁命名入口。不要发明 `--target-os=ohos` 或不存在的 configure 选项。
3. 若需外置 GNU make 命令行变量覆盖库名，先为锁定版本设计并测试统一覆盖库目标、SONAME、安装名及 CLI 的 NEEDED，保留原始输出和配方。不得手工编辑 upstream/生成文件。此选项是评估任务，本文没有声称存在通用可用的一行命令。
4. ELF 重命名工具仅可作为明确记录的派生产物策略：所有相关 SONAME/NEEDED 一致处理并重新验证符号版本、加载、哈希和复现。不称为“未加工官方二进制”；Zero-Patch 只保证源码未改。若严格要求连 ELF 后处理也禁止，直接判定该打包路径失败。

不允许只把 `libavcodec.so.63` 改名后继续发布。若无补丁打包路线无法通过，交付库构建证据及阻塞报告，不通过改 configure 悄悄绕过。

调试符号用相同 SDK 的 llvm-objcopy/strip 处理；保留 build-id、符号与发布二进制映射。不要使用宿主 GNU objcopy 处理不支持的 AArch64 文件。SDK 内系统 stub 库不随 App 打包；第三方运行库及 libc++ 是否需要打包，以目标 SDK 的系统清单和实际 NEEDED 判断。

## 9. CMake / NAPI 集成

FFmpeg 自身使用其 configure/make，不改写为 CMake。私有应用 CMake 只导入构建产物。下面是最小模式，路径必须由 package manifest 生成，示例 `libavutil.so` 要替换成实际可链接文件。

```cmake
cmake_minimum_required(VERSION 3.16)
project(media_bridge LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
if(NOT DEFINED FFMPEG_SDK OR NOT DEFINED FFMPEG_AVUTIL_FILE)
  message(FATAL_ERROR "Set SDK root and manifest-selected avutil file")
endif()
add_library(ff_avutil SHARED IMPORTED GLOBAL)
set_target_properties(ff_avutil PROPERTIES
  IMPORTED_LOCATION "${FFMPEG_AVUTIL_FILE}"
  INTERFACE_INCLUDE_DIRECTORIES "${FFMPEG_SDK}/include")
add_library(media_bridge SHARED napi_init.cpp engine.cpp)
target_link_libraries(media_bridge PRIVATE ff_avutil libace_napi.z.so)
# 实际工程为 avformat/avcodec/avfilter/swscale/swresample 等分别建目标，
# 再依据该 profile 的依赖图连接；用该 SDK 支持的 NAPI 链接名。
```

配置入口使用 `-DCMAKE_TOOLCHAIN_FILE=<native>/build/cmake/ohos.toolchain.cmake -DOHOS_ARCH=arm64-v8a`；最低 API/兼容 SDK 参数按安装版 toolchain 和应用工程填写，不固定为网上示例值。通过 Hvigor 构建时以项目 native 配置为入口，防止两套 ABI/API 设置冲突。

NAPI 边界：

- 仅使用安装后的公共头文件；C++ include FFmpeg C API 时用 `extern "C"`。不包含源码内部头、不直接引用 `ff_*` 私有符号。
- 先做 `getBuildInfo()`，返回 `av_version_info()`、各库 version/configuration/license API 和 manifest 摘要，验证加载的是本包库。
- `probe(uriOrFd)` 返回自有结构化结果；`transcode(spec)` 返回 session id；`cancel(id)`、进度/日志事件采用异步接口。私有 API 自己定义，不假装和 FFprobe 所有 JSON 字段完全一致。
- 编码解码使用 send/receive，正确处理 EAGAIN、EOF、flush、时间基和资源释放。配置 AVIO interrupt callback 支持取消和超时。
- 自定义 AVIO 在私有代码中实现 fd/URI 访问；处理偏移、seek、所有权和关闭。不把应用 URI 当可由 libc 打开的路径。
- 不在 ArkTS/UI 线程跑转码；使用受控工作线程。napi 值只能在相应线程使用；跨线程回调采用当前 SDK 支持的线程安全机制，处理环境销毁和 session 生命周期。
- `av_log_set_callback` 是进程级设置，统一安装一次；不要每个会话反复覆盖。无法可靠归属的日志标为全局；对进度队列限速、日志限量。
- 限制并发、输入尺寸/时长、内存和线程总量；取消后停止回调，删除不完整输出，支持重试和应用退出。

不得通过把 FFmpeg 加密嵌入私有 so、校验官方库哈希后拒绝兼容替代库等手段破坏库替换路径。完整性校验用于官方发行包供应链验证，与用户许可下的替换流程分开设计。

## 10. ffmpeg / ffprobe 能力与 App 执行限制

### 10.1 官方 CLI

保持 upstream fftools 原样，构建 ffmpeg/ffprobe 可执行文件。通过官方 CLI 可获得命令参数行为和 FFprobe 输出；`ffprobe -of json -show_format -show_streams` 是结构化探测起点。[FFprobe 文档](https://ffmpeg.org/ffprobe.html)

必须首先在目标设备开发 shell 验证，再单独验证发布形态 App 是否允许从获准路径执行随包 ELF、创建子进程及管道、读取输入和写出结果。hdc shell 成功不等于 App 成功，也不证明商店允许该方案。核查目标 API 的文档、权限和分发政策，并记录结论及证据。

如果平台允许：每任务一个子进程，传入 argv 数组而不是 `sh -c` 拼串；stdin/stdout/stderr/progress 独立管道，限流、防死锁、退出码回收、取消超时、资源上限。进度使用 CLI `-progress pipe:1 -nostats` 等机器可读输出，不依赖解析本地化日志。引入 CLI 不需要修改 main。

### 10.2 App 内公共 API 管线

若 App 不允许执行 CLI：保留 CLI 为 SDK 开发/诊断产物；App 使用自有 libav* 软件管线和探测实现。实现裁剪、缩放、转码、重封装、音频转换、已定义滤镜子集等明确能力；返回 supported/unsupported 清单。

这条路线不能承诺接受所有 ffmpeg 命令或 100% 复制 FFprobe JSON。命令输入可以解析成自有 task spec，但必须公布支持的语法和参数；不支持的选项明确拒绝，不能偷偷忽略。

如果产品硬性要求“商用 App 中完整运行任意官方 ffmpeg/ffprobe 命令”，而进程路线不可用，则该需求在当前约束下为阻塞项。不能用 main 重命名、复制 fftools 或内存调用可执行文件来宣称完成。需要产品重新选择范围，或等待上游提供可满足需求的接口。

## 11. LGPL-compatible 第三方依赖策略

第三方许可按**锁定版本、选项和递归依赖**审计。下表是选型候选，不能代替具体版本 LICENSE/NOTICE；只有具备来源、完整许可文件、哈希和依赖闭包记录后才进入白名单。优先共享库，降低静态链接产生的合规与体积复杂度。

| 功能 | 候选 | 引入条件 |
|---|---|---|
| 压缩 | zlib | 核验具体发布的宽松许可 |
| Opus/Vorbis | libopus、libogg/libvorbis | 核验 BSD 类条款及依赖 |
| MP3 编码 | LAME | 按该版本 LGPL 履行源码/替换义务 |
| VP8/VP9 | libvpx | 核验许可、NOTICE、专利文本 |
| AV1 | dav1d、libaom、SVT-AV1 | 分别核验许可/专利条款、平台支持、资源成本 |
| 字幕/文字 | libass、FreeType、HarfBuzz、FriBidi、libunibreak | 整条依赖链审计；FreeType 选择适用的宽松许可路径；字体另审 |
| HTTPS | mbedTLS 或其他通过审计的 TLS 库 | 核验版本许可兼容、FFmpeg 接口适配和 CA 信任路径 |
| OpenSSL | 仅作为独立评估候选 | 不假设所有旧版/配置与 LGPL 兼容；确认所选版本与 FFmpeg configure 的许可检查 |
| 网络扩展 | SRT 等 | 确有需求才引入，审查 TLS 和其他传递依赖 |

GPL-compatible 不等于满足本项目“不引入 GPL 组件”的条件。许可证扫描需用 SPDX 表达式解析；`LGPL-3.0-or-later` 不得因字符串含 GPL 被误杀；MIT OR GPL 的双许可必须明确选择合适分支并保存证据。

禁用库包括 GPL 编码库、FAAC/FDK 等未获本项目批准的非自由/不兼容依赖，以及依赖链里不可接受的 GPL/AGPL 组件。不能用“我有商业授权”自动解除本项目固定的 GPL/nonfree 禁用策略。

HTTPS 必须真实配置证书信任、验证域名和过期证书；`--enable-network` 不自动提供 TLS。协议可用性需从实际产物枚举，网络访问还受 App 权限与系统策略约束。[FFmpeg 协议文档](https://ffmpeg.org/ffmpeg-protocols.html)

扩展目标至少评估 HTTPS、字幕渲染、Opus/MP3、VP9/AV1。每项写明 supported、disabled-by-license、unavailable-on-platform 或 blocked；不因构建缺库而默默退化成残缺版。`core` 是排障和基础 SDK，`extended` 是功能目标。

## 12. 验证命令与验收矩阵

下面的 `$READELF` 使用本 SDK llvm-readelf。不能在 x86 主机直接运行 OHOS 二进制来判断其功能；主机只做静态检查，功能命令在目标设备受控目录执行。

```bash
# 主机静态检查，对 runtime/ 下每个实际库及 bin 下两个 ELF 执行
"$READELF" -hW <file>
"$READELF" -lW <file>
"$READELF" -dW <file>
"$READELF" --dyn-syms <file>
"$READELF" --version-info <file>
```

检查 ELF64/AArch64、库为 DYN、CLI 为合适 PIE、解释器路径属于目标 OHOS SDK、无 glibc/bionic 或宿主库、无意外 RPATH、无 TEXTREL。闭包中的 NEEDED 要么在目标平台系统 allowlist，要么随包提供；未定义导入不是一概失败，但必须能在系统/包内依赖中解析。

检查段权限、栈不可执行、RELRO、目标系统要求的页对齐与最低 API 符号可用性；不要从 Android 16 KB 规则直接推断 HarmonyOS 要求。导出必须包含预期公共 API，私有 Engine 的 NEEDED 应指向 FFmpeg 共享库，不得出现将 FFmpeg 对象静态合并的情况。

设备开发 shell 示例（先把同一次构建的 bin 与动态库放到获准目录）：

```bash
export LD_LIBRARY_PATH="$PWD/lib"
./bin/ffmpeg -version
./bin/ffmpeg -buildconf
./bin/ffmpeg -L
./bin/ffmpeg -decoders
./bin/ffmpeg -encoders
./bin/ffmpeg -filters
./bin/ffmpeg -formats
./bin/ffmpeg -protocols
./bin/ffmpeg -hwaccels
./bin/ffprobe -v error -show_format -show_streams -of json sample.mp4
./bin/ffmpeg -nostdin -y -i sample.mp4 -map 0 -c copy remux.mkv
./bin/ffmpeg -nostdin -y -i sample.mp4 -vn -c:a pcm_s16le audio.wav
./bin/ffmpeg -nostdin -y -i sample.mp4 -an -vf scale=320:-2 \
  -c:v mpeg4 -q:v 5 scaled.mp4
./bin/ffmpeg -nostdin -i sample.mp4 -f framemd5 decoded.framemd5
```

上述命令假定对应样本流与枚举功能存在；样本须包含确定的视频/音轨，并有已知期望。不要把输出文件存在当作正确，使用 FFprobe、时长/分辨率/时间戳检查和解码结果验证；跨 CPU/优化不保证所有编码输出逐字节相同。LD_LIBRARY_PATH 仅用于开发 shell，不作为 App loader 方案。

| 层次 | 必须验证 | 不能据此宣称 |
|---|---|---|
| 源码静态 | Zero-Patch、许可、参数、依赖、脚本语法 | 编译已通过 |
| 交叉构建 | 完整日志、ELF、依赖闭包、符号 | 真机运行成功 |
| 设备 shell | CLI、样本、TLS 正反例、功能枚举 | App 沙箱执行可用 |
| App 真机 | NAPI 加载、URI/fd、异步、取消、并发、后台生命周期、最低 API | 所有机型硬件一致 |
| LGPL 替换 | 修改兼容库后按公开流程重打包/重链接、安装、运行 | 仅有一个 .so 就当然合规 |

硬件单独验收支持查询、输出 H.264/HEVC 参数、分辨率限制、surface/buffer 模式、stride、色彩、时间戳、取消和失败处理；不得把硬件结果归入 FFmpeg 软件编码器能力。

## 13. LGPL、源码和应用声明

FFmpeg 的许可随构建选择变化；本项目通过 version3 且关闭 GPL/nonfree，以实际 `*_license()`、CLI `-L` 和构建配置共同确认 LGPLv3-or-later。没有修改 FFmpeg 也仍有随分发履行的开源许可义务。[FFmpeg 官方法律说明](https://ffmpeg.org/legal.html)

每次二进制发布关联精确的 FFmpeg 与适用依赖源码、许可原文、构建配方、依赖锁和 notice。应用“关于/开源许可”页与下载页展示 FFmpeg 使用声明、实际许可、对应版本源码入口；禁止只链 upstream 首页。库及其构建脚本的公开不要求把原创私有应用代码一起发布。

闭源 Engine 采用公共接口动态链接是设计基础；还必须落实 LGPLv3 第 4 节的适当共享库机制或其他合规重链接路径，并处理适用的安装信息要求。尤其要验证 HAP 签名和安装流程是否允许用户实际使用接口兼容的修改库；禁止通过 EULA 阻止为调试该修改而必要的逆向工程。签名受限而无可行替换/重链接方案时，license gate 不通过，不声称上架合规已经解决。[LGPLv3 与 GPLv3 官方合并文本，LGPL §4](https://www.gnu.org/licenses/lgpl%2Bgpl-3.0-standalone.html)

`docs/replacement-and-relink.md` 必须给出可操作的工具版本、命令、兼容 ABI、重打包/重签名/安装步骤及验证记录；若采用提供应用目标文件的重链接路径，需单独评估其交付内容和条件，不擅自承诺无需任何应用侧交付。最终发布按实际分发方案审阅，不能用技术架构代替适用条款判断。

示例应用声明（版本、许可和链接在发布时生成）：

> 本应用使用 FFmpeg <实际版本>，相关组件依 GNU LGPL v3 或更高版本授权。许可全文、对应源码和构建说明见“开源许可”页。应用的原创 Media Engine 通过公共接口动态链接 FFmpeg。

本项目还要单独核验编解码专利和品牌使用要求；GPL/nonfree 关闭不是专利许可证明。

## 14. CI / license gate

Codex 实现三个工作流：`verify` 负责文档/脚本/锁/许可策略；`build` 负责 core/extended 交叉构建与静态验证；`release` 仅对已通过必要证据 gate 的确定提交发布。初期可手工触发，避免在 SDK 授权和环境未明确前自动下载 SDK。

推荐 DAG：

```text
validate-locks → verify-signed-sources → snapshot-source
  → build-core → integrity-after-core → elf/license-core
  → build-deps → build-extended → integrity-after-extended
  → elf/license-extended → capability-diff
  → device/App evidence → replacement evidence → release manifest
```

gate 必须 fail closed：

1. 源码/签名/哈希不符、版本浮动、SDK 身份缺失、源码任何改动即失败。
2. 参数 token 出现 enable-gpl/nonfree 即失败；同时解析最终 config 中 GPL=0、NONFREE=0、VERSION3=1；不要只检查命令字符串。
3. 检查生成配置、所有库 license API 和 CLI -L 一致为 LGPLv3 口径；禁用许可分类的源码可以存在于原始 tarball，不等于进入产物。
4. 依赖锁白名单、SPDX、SBOM、链接日志、NEEDED 与递归许可一致；静态吸入的外部依赖不能靠 NEEDED 检出，必须审查构建输入。
5. CLI 两项和预期共享库完整；架构、SONAME、NEEDED、API、导出、运行期依赖闭包通过。
6. required-capabilities 与实际枚举对比；core/extended 分开标准；任何功能下降都生成解释并阻止无说明发布。
7. 真机证据绑定 FFmpeg 版本、提交 SHA、包哈希、SDK/API、设备系统、profile；旧版本证据不能自动复用。设备 runner 不可用时仅发布明确声明未真机验证的 Release 预发布候选包，禁止标为正式已验证 release；不上传 Actions Artifacts。
8. 同版源码包、许可文件、源码下载入口、替换流程记录齐全；私有仓库链接不能充当所有 App 用户可访问的源码入口。

SDK 缓存与发布包分离，按 SDK 许可决定如何供应 CI；不得公开 SDK 安装包、签名密钥和凭据。默认只读 workflow 权限，仅发布 job 按需写权限；第三方 actions 锁 commit，不允许不受信 PR 获得签名/设备/发布 secrets。

本项目按用户要求禁用持久构建缓存；构建成功或失败都不保留 Actions Artifacts，成品及对应源码仅存于 Release。runner 上的临时目录在结束时清理，历史 Artifacts 和本流程旧缓存由清理 job 删除。记录可复现构建偏差；SOURCE_DATE_EPOCH 只解决部分时间信息，不自动保证 bit-for-bit 一致。

## 15. 升级 FFmpeg 的流程

1. 从官方稳定发布页选最新稳定主线及补丁版本，验证 release 身份和签名，记录变更、安全修复和发布时间。
2. 更新锁文件，使用新源码和新构建目录；不将 master 当稳定版，不从旧目录覆盖源码。
3. 比较 configure --help、许可分类、外部依赖要求、公开 API/ABI、SONAME 主版本；不复用旧头文件配新库。
4. 先重跑 core，再逐项重建 extended；生成功能差异、依赖差异、包大小和耗时报告。
5. 用新 SDK/新 FFmpeg 的组合独立验证最低系统；设备测试、App 集成、替换流程和硬件协同重新验收。
6. 更新私有 Engine 对公共 API 的使用，必要时改自有代码；不能为兼容旧 Engine 修改 FFmpeg。
7. 全 gate 通过后发布新版本，保存旧 SDK 和全部配套依赖，支持整包回退；不得只替换其中一个 avcodec 或混用不同版本族库。

如果最新稳定版存在无补丁移植阻塞，默认标为 blocked。仅在明确接受版本降级后才使用经过审计的旧稳定版本，并说明偏离“最新稳定”目标及其安全维护安排。

## 16. 失败回退策略

| 失败 | 先做什么 | 允许的回退 | 禁止 |
|---|---|---|---|
| clang hello 不过 | 查 target/sysroot/SDK 主机版本/driver 日志 | 修正外置工具链配置 | 复制 Android libc |
| configure 检测失败 | 看 config.log 中最小探测与命令 | 修正 wrapper 或单项合法开关 | 手改 HAVE_* |
| 汇编编译失败 | 定位指令/assembler/工具版本 | 临时 C-only 诊断，性能回归后单独决定 | 默认整批砍 NEON |
| libavdevice 后端不可用 | 区分系统设备接口与文件能力 | 精确禁用不可用 indev/outdev 并列明 | 用 disable-everything 掩盖 |
| 外部库不可移植 | 单独构建和递归审计 | core 诊断或替代兼容依赖；extended 仍标阻塞 | 加 GPL/nonfree 解锁 |
| HAP 加载失败 | 检查真实条目/SONAME/NEEDED/namespace | 按第 8 节验证无补丁打包路径 | 改名后假装修复 |
| App 无法执行 CLI | 保存 shell/App 两套证据 | 自有 API 子集并声明范围 | 嵌入 fftools main |
| OHOS 硬编失败 | 查询硬件与输入参数、格式、资源 | 合法软件编码器或明确不支持 | 假装已启用 x264 |
| LGPL 替换无法实现 | 记录签名安装障碍与替代路径评估 | 暂停该分发形态 | 只加 About 声明就发布 |
| upstream 必须改源码才能编过 | 保存最小复现、失败日志 | 向上游报告/等待正式发布，或请求产品变更范围 | 私下应用补丁仍叫 Zero-Patch |

## 17. Codex 最终交付清单

- 外置构建配方、Windows/选定宿主入口、依赖锁、源码验签和完整性脚本；不包含 patched upstream。
- core 与 extended 的独立状态；每个 profile 的 configure、完整构建日志、SDK/API 身份、SBOM、哈希清单。
- arm64-v8a 共享库 SDK、公共头、官方 CLI、符号、运行库闭包与 HAP 集成样例。
- 可重现的示例转码与探测结果；最低 API App 真机测试，取消/并发/生命周期与设备硬件测试。
- 开源声明页、对应源码交付、许可文本、替换/重链接说明和实际验证记录。
- 已知功能缺口、失败原因、后续可执行任务；明确区分“方案完成”“静态通过”“交叉构建通过”“shell 通过”“App 真机通过”“正式发布”。

### 可直接交给实施 Codex 的指令

请按本规范实施。先确认实际仓库、AGENTS.md、SDK 与主机环境；存在 .codegraph 时优先用 CodeGraph。先做只读源码和最小 clang/共享库加载验证，再做扩展依赖和私有应用集成。任何步骤不能通过时提交可复现证据与范围明确的阻塞说明，不修改 upstream FFmpeg、不启用 GPL/nonfree、不静态合并进闭源 Engine、不向 FFmpeg 注册 OHOS codec，也不把 ffmpeg/ffprobe main 当库函数。所有完成声明必须有对应层级的实际证据。

## 18. 官方参考资料与核查范围

本文的版本与参数按下列官方资料核查；原 ChatGPT 对话作为需求背景，不作为构建或许可事实的证据。架构、目录、脚本和 gate 是本项目拟定的工程规范；**未在本次文档交付中下载 SDK、交叉编译、打包 HAP 或运行真机**。第三方候选库须在实施阶段按实际版本逐一审计。

- [FFmpeg 下载与稳定版本](https://ffmpeg.org/download.html)：版本选择与官方下载入口。
- [FFmpeg n9.0.2 configure](https://github.com/FFmpeg/FFmpeg/blob/n9.0.2/configure)：锁定版本的开关、target-os 和构建配置依据。
- [FFmpeg 许可说明](https://ffmpeg.org/legal.html)：构建许可和分发注意事项。
- [FFmpeg LICENSE 原文入口](https://github.com/FFmpeg/FFmpeg/blob/master/LICENSE.md)：实施时改为锁定 release 的对应文件进行审计。
- [GNU LGPLv3/GPLv3 官方文本](https://www.gnu.org/licenses/lgpl%2Bgpl-3.0-standalone.html)：Combined Works、重链接和适用安装信息条款。
- [OpenHarmony 官方 CMake toolchain](https://github.com/openharmony/build/blob/master/ohos/ndk/cmake/ohos.toolchain.cmake)：ABI/target 参数参考，不能替代实际商用 SDK。
- [华为 Native 构建 FAQ](https://developer.huawei.com/consumer/cn/doc/doccenter-tools-faq/faqs-compiling-and-building-33)：SDK toolchain 搜索路径行为参考。
- [FFprobe 文档](https://ffmpeg.org/ffprobe.html)、[协议文档](https://ffmpeg.org/ffmpeg-protocols.html)、[平台说明](https://ffmpeg.org/platform.html)：CLI、网络和宿主构建行为。
