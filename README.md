# HmOS FFmpeg Kit

官方 FFmpeg 9.0.2 → HarmonyOS NDK/clang → arm64-v8a 动态库 → 可本地导入的 HAR。

保持 upstream 源码 Zero-Patch；`--enable-version3 --disable-gpl --disable-nonfree`。ArkTS/NAPI 桥接通过公开 libav API 工作，不修改 fftools，不向 FFmpeg 注册 OHOS codec。硬件编解码由应用自己的 HarmonyOS AVCodec Engine 提供，本仓库不宣称已实现该硬件后端。

## 下载与使用

从 [Releases](https://github.com/SamProjects/HmOS_FFmpeg-Kit/releases) 下载 extended HAR，放到鸿蒙工程 entry/libs，通过模块 oh-package.json5 的本地依赖导入，安装后即可调用：

```typescript
import { FFmpeg } from '@samprojects/hmos-ffmpeg';
const info = FFmpeg.getBuildInfo();
const media = await FFmpeg.probe(inputPath);
await FFmpeg.remux(inputPath, outputPath).result;
const task = FFmpeg.transcode({ input: inputPath, output: outputPath,
  videoCodec: 'mpeg4', audioCodec: 'aac', videoFilter: 'scale=640:-2' });
await task.result;
```

[完整导入与 API 说明](docs/INTEGRATION.zh-CN.md) · [开发规范](docs/DEVELOPMENT.zh-CN.md)

| 产物 | 内容 |
|---|---|
| core.har | 内置可用 LGPL 编解码/封装/滤镜，ArkTS/NAPI，FFmpeg 动态库 |
| extended.har | core + libopus、LAME、libvpx、zlib、mbedTLS |
| sdk.tar.gz | 原生头文件/so、运行库、官方 ffmpeg/ffprobe CLI、调试符号、证据、SBOM、许可 |
| sources.tar.gz | 对应官方源码原包及签名、精确依赖源码、外置构建配方和完整性清单 |

API 支持探测、重封装、软件转码、单输入滤镜、取消和进度查询。不是任意 FFmpeg 命令解释器；官方 CLI 单独交付，App 内执行须验证平台限制。禁用 GPL 不会提供 x264/x265；H.264/HEVC 硬编与 FFmpeg 解耦。完整功能以每个构建配置和实际设备为准，未引入字幕字体/AV1 外部编码依赖。

## 构建与发布

GitHub Actions 在 main push、PR、tag、手动运行时做校验并构建 core/extended。成功后自动构建 HAR，再用独立消费工程从 HAR 编译未签名 HAP，检查动态库打包闭包。main/tag/手动发布生成 GitHub **预发布版**；PR 不发布。版本锁定在 config/project.json；升级先改锁文件和依赖哈希，不追踪 master/latest。

Linux x64 本地（使用已取得许可的 HarmonyOS Command Line Tools）：

```bash
export HARMONY_TOOLS=/path/to/command-line-tools
export OHOS_NATIVE="$HARMONY_TOOLS/sdk/default/openharmony/native"
export HOS_SDK_HOME="$HARMONY_TOOLS/sdk"
export PATH="$HARMONY_TOOLS/bin:$HARMONY_TOOLS/tool/node/bin:$PATH"
python3 scripts/setup-sdk.py
bash scripts/build-ohos.sh extended
python3 scripts/build-har.py extended
python3 scripts/release-assets.py extended
```

需要 Python 3.12+、GNU make、C/C++ host compiler、cmake、ninja、pkg-config、gpg；原生最低目标 API12，当前固定 SDK26 编译。FFmpeg 使用源外构建；库名通过 GNU make 命令行变量统一设置，不改源文件、生成配置或 ELF。构建保留调试信息并用同 SDK LLVM 工具产生符号。

CI 默认下载 config/sdk.lock.json 中固定 SHA-256 的 Huawei CLI 社区镜像，不把 SDK 重新发布到本项目；生产组织可以自行提供已授权、核验过的 SDK，用 OHOS_NATIVE/HARMONY_TOOLS 指向本地安装。所有媒体依赖来自锁定官方发布源。不要把社区 SDK 镜像误称为官方分发站点。

首次重跑请使用全新 workspace；脚本拒绝复用已有构建目录，避免污染。Windows 可以通过 DevEco 直接消费 HAR；完整 FFmpeg 构建入口当前是 Linux/Actions，未声称 Windows PowerShell 本地交叉构建通过，也不自动安装 WSL。

## 验证和许可证

原始项目代码 MIT；FFmpeg 二进制按 LGPLv3-or-later，第三方保留其条款。预发布意味着没有宣称真机执行、最低系统运行或 LGPL 替换安装验证通过。所有门禁状态在 manifest.json 中；静态/构建/HAP 打包证据与设备证据分开。正式 App 分发还必须落实对应源码可访问、notice、兼容库替换/重链接等义务。[替换验证](docs/replacement-and-relink.md)

不满足 Zero-Patch、GPL/nonfree 禁用、依赖闭包或 HAR 消费编译的构建不得发布；不通过的任务上传诊断日志。某些 GPL 源文件存在于官方原始源码包中并不表示被链接到本 LGPL 构建。
