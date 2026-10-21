# HmOS FFmpeg Kit

官方 FFmpeg 9.0.2 → HarmonyOS NDK/clang → arm64-v8a / x86_64 动态库 → 可本地导入的 extended 全架构 HAR。

保持 upstream 源码 Zero-Patch；`--enable-version3 --disable-gpl --disable-nonfree`。ArkTS/NAPI 桥接通过公开 libav API 工作，不修改 fftools，不向 FFmpeg 注册 OHOS codec。硬件编解码由应用自己的 HarmonyOS AVCodec Engine 提供，本仓库不宣称已实现该硬件后端。

需要执行 FFmpeg 参数命令时，可显式构建 [命令执行实验版](docs/COMMAND-TEST.zh-CN.md)。该版本新增 `FFmpeg.execute(args)`，命令组件使用已记录差异的 fftools 适配，属于上述零补丁约束的实验例外；当前尚未完成鸿蒙手机运行验证。 可使用 [测试 App](docs/TEST-APP.zh-CN.md) 在 DevEco 本地模拟器执行一键自检。

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

`*-all.har` 同时包含当前 HarmonyOS 应用支持的 arm64-v8a、x86_64；不包含已不受 HarmonyOS 应用工具链支持的 armeabi-v7a，也不包含 x86 32 位。[全架构包与应用体积说明](docs/ABI-DISTRIBUTION.zh-CN.md)说明如何在消费工程里排除无关架构，不能只靠 HAR 大小推算用户下载大小，也不假定应用市场必然自动裁剪。

[首次完整 CI 与发布验证记录](docs/VALIDATION.zh-CN.md)：core/extended HAR 和独立消费 HAP 均已构建通过；真机运行尚未验证。

默认流水线仅交付 `hmos-ffmpeg-<版本>-extended-all.har`，包含 ARM64 与 x86_64 的 FFmpeg、ArkTS/NAPI 桥接、运行库及许可证。extended 同时包含 libopus、LAME、libvpx、zlib、mbedTLS。core、单架构 HAR、SDK、CLI、调试符号及源码归档不再作为默认发布附件；旧版发布和完整打包脚本仍保留。

API 支持探测、重封装、软件转码、单输入滤镜、取消和进度查询。不是任意 FFmpeg 命令解释器；默认 HAR 不交付官方 CLI。禁用 GPL 不会提供 x264/x265；H.264/HEVC 硬编与 FFmpeg 解耦。完整功能以每个构建配置和实际设备为准，未引入字幕字体/AV1 外部编码依赖。

## 构建与发布

GitHub Actions 在 main push、PR、tag、手动运行时仅构建 extended 的 ARM64、x86_64 运行库，然后合并为一个全架构 HAR。通过独立 ARM64、x86_64、双架构消费工程编译未签名 HAP，检查动态库打包闭包。main/tag/手动发布生成 GitHub **预发布版**；PR 不发布。版本锁定在 config/project.json；升级先改锁文件和依赖哈希，不追踪 master/latest。

Linux x64 本地（使用已取得许可的 HarmonyOS Command Line Tools）：

```bash
export HARMONY_TOOLS=/path/to/command-line-tools
export OHOS_NATIVE="$HARMONY_TOOLS/sdk/default/openharmony/native"
export HOS_SDK_HOME="$HARMONY_TOOLS/sdk"
export PATH="$HARMONY_TOOLS/bin:$HARMONY_TOOLS/tool/node/bin:$PATH"
python3 scripts/setup-sdk.py
export HMOS_HAR_ONLY=1
for abi in arm64-v8a x86_64; do
  HMOS_ABI="$abi" bash scripts/build-ohos.sh extended
  HMOS_ABI="$abi" python3 scripts/cleanup-profile.py extended
done
python3 scripts/build-har.py extended --universal
python3 scripts/check-release.py dist/assets
```

需要 Python 3.12+、GNU make、C/C++ host compiler、cmake、ninja、pkg-config、gpg；原生最低目标 API12，当前固定 SDK26 编译。FFmpeg 使用源外构建；库名通过 GNU make 命令行变量统一设置，不改源文件、生成配置或 ELF。默认流水线使用同 SDK LLVM 工具剥离调试信息，不生成独立符号包。

CI 默认下载 config/sdk.lock.json 中固定 SHA-256 的 Huawei CLI 社区镜像，不把 SDK 重新发布到本项目；生产组织可以自行提供已授权、核验过的 SDK，用 OHOS_NATIVE/HARMONY_TOOLS 指向本地安装。所有媒体依赖来自锁定官方发布源。不要把社区 SDK 镜像误称为官方分发站点。

需要发布时，CI 在长时间编译之前检查发布权限、固定源码标签并创建中文草稿；全部构建验证后核对远端附件名称、大小和 SHA-256，再公开为预发布版。构建期间 main 发生变化也不会把标签悄悄改指向新提交。上传失败会重试并保留草稿，不公开不完整版本。完整编译命令写入临时日志；Actions 控制台输出阶段进度及失败摘要，临时文件在任务结束时清理。

首次重跑请使用全新 workspace；脚本拒绝复用已有构建目录，避免污染。Windows 可以通过 DevEco 直接消费 HAR；完整 FFmpeg 构建入口当前是 Linux/Actions，未声称 Windows PowerShell 本地交叉构建通过，也不自动安装 WSL。

## 验证和许可证

原始项目代码 MIT；FFmpeg 二进制按 LGPLv3-or-later，第三方保留其条款。预发布意味着没有宣称真机执行、最低系统运行或 LGPL 替换安装验证通过。门禁记录保存在构建期间的临时 manifest.json 中，不作为 Release 附件；静态/构建/HAP 打包证据与设备证据分开。正式 App 分发还必须落实对应源码可访问、notice、兼容库替换/重链接等义务。[替换验证](docs/replacement-and-relink.md)

不满足 Zero-Patch、GPL/nonfree 禁用、依赖闭包或 HAR 消费编译的构建不得发布。构建和发布在同一个 runner 中完成，不上传 Actions Artifacts，不使用持久构建缓存；失败只保留 Actions 控制台日志。工作流开始及结束会清理本仓库旧 Artifacts 和本流程早期缓存，Release 仅保留全架构 HAR，HAR 内仍保留许可证声明；对外分发时需要另行安排对应源码的提供。某些 GPL 源文件存在于官方原始源码包中并不表示被链接到本 LGPL 构建。
