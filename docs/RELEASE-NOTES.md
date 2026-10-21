适用于 HarmonyOS 的 FFmpeg extended 全架构 HAR 预发布版，同时包含 arm64-v8a 与 x86_64。

## 下载与使用

本次发布仅提供 `hmos-ffmpeg-<版本>-extended-all.har`。将 HAR 放入消费项目并配置本地依赖，具体步骤见仓库中文集成说明。

extended 包含 FFmpeg 内置 LGPL 功能，以及 Opus、LAME、libvpx、zlib、mbedTLS。不再随默认发布提供 core、单架构 HAR、原生 SDK、CLI、调试符号或源码归档。

## 架构与验证

同一 HAR 包含 ARM64 和 x86_64 两套运行库。使用方应配置编译 ABI 与 `nativeLib.filter` 打包排除规则，详见 `docs/ABI-DISTRIBUTION.zh-CN.md`。

发布前检查源码完整性、LGPL 配置、两种架构的 ELF 依赖闭包和 HAR 文件哈希，并通过独立 ARM64、x86_64、双架构消费 HAP 编译验证。验证记录仅在构建期间使用，不作为发布附件。上传后按 Release ID 核对附件名称、大小与 SHA-256，通过后才公开草稿。

ArkTS 接口支持探测、重封装、软件转码、单输入滤镜、取消和进度查询，不是任意 FFmpeg 命令解释器。尚未进行真机运行或市场云端拆分验证，因此保持预发布状态。

## 版权与分发

HAR 内保留 FFmpeg、依赖和运行库的许可证声明。FFmpeg 按 LGPLv3-or-later 配置构建，禁用 GPL/nonfree；项目自有代码使用 MIT 许可证。对外分发者仍需落实适用的声明、对应源码访问及库替换/重链接要求。

构建成功或失败均不上传 Actions Artifacts，不创建持久构建缓存；仅将全架构 HAR 直接存入 Release。
