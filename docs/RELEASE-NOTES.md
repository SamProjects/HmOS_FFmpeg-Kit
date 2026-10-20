适用于 HarmonyOS 的 FFmpeg 预发布版，支持 arm64-v8a 与 x86_64，提供单架构和全架构 HAR。

## 下载与使用

- 一般通过 ArkTS 使用时，下载 `extended-all.har`，同时包含两种受支持架构；也可选择文件名带 `arm64-v8a` 或 `x86_64` 的单架构 HAR。
- `core` 保留可用的内置 LGPL 功能；`extended` 额外包含 Opus、LAME、libvpx、zlib、mbedTLS，提供相应编解码实现、MP3/VP8/VP9 编码及 HTTPS/TLS 等能力。
- `sdk.tar.gz` 提供 C/C++ 头文件、动态库、官方 ffmpeg/ffprobe、调试符号、许可证及构建记录，供原生集成和调试使用。
- `sources.tar.gz` 提供对应的官方源码、依赖源码、签名、构建配方与完整性记录。底部 GitHub 自动生成的源码快照不能代替此对应源码包。
- `manifest.json` 是构建与验证清单；`SHA256SUMS` 和各 `.sha256` 文件用于下载校验。

将 HAR 放入消费项目并配置本地依赖，具体步骤见仓库中文集成说明。不要将 SDK、源码或调试符号压缩包放进应用资源目录。

## 架构与包体积

`*-all.har` 包含 ARM64 和 x86_64 两套运行库。使用方应同时配置编译 ABI 与 `nativeLib.filter` 打包排除规则；HAR 大小不等于应用下载大小，不假定市场必然自动裁剪所有无关架构。

每个全架构 HAR 均经过独立 ARM64、x86_64、双架构消费 HAP 编译，并检查 ABI 目录、运行库闭包及文件哈希。实测 HAP 与原生库大小见 `*-all-consumer-validation.json`；这是构建产物测量，不是应用市场下载体积测量。配置方法见仓库 `docs/ABI-DISTRIBUTION.zh-CN.md`。

## 功能与验证范围

ArkTS 接口支持探测、重封装、软件转码、单输入滤镜、取消和进度查询，不是任意 FFmpeg 命令解释器。原版 CLI 单独交付，App 内能否启动它们仍需验证平台执行限制。硬件编解码由独立 HarmonyOS AVCodec 后端提供，不向 FFmpeg 注册 OHOS codec。

已执行源码完整性、LGPL 配置、AArch64/x86-64 ELF 依赖闭包、HAR 打包与独立消费 HAP 编译检查。尚未进行真机运行、市场云端拆分或 LGPL 修改库替换/重签名安装验证，因此保持预发布状态。

## 版权与分发

本项目使用未经源码修改的官方 FFmpeg，按 LGPLv3-or-later 配置构建，禁用 GPL/nonfree。对应源码、构建配方和许可文件随本次发布提供。应用分发者仍需落实适用的声明、对应源码访问及库替换/重链接要求；私有仓库链接不一定能被最终用户访问。第三方许可证和版权声明保留原文。

## 存储策略

构建成功或失败均不上传 Actions Artifacts，不创建持久构建缓存；成品直接存入 Release。
