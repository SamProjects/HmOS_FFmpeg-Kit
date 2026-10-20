# 首次完整构建与发布验证

验证日期：2026-10-20。构建源码提交：`bdf1ee3ef7a03c2cfe3db9ffb9431b7340cf3e74`。

- [成功的 GitHub Actions 运行](https://github.com/SamProjects/HmOS_FFmpeg-Kit/actions/runs/39393331098)
- [已发布的预发布版 v1.0.0-ci.6](https://github.com/SamProjects/HmOS_FFmpeg-Kit/releases/tag/v1.0.0-ci.6)

## 已通过

- 六项构建工具测试、Shell 语法检查。
- 主机上的 FFmpeg 9.0.2 公共 API 媒体管线测试，启用 AddressSanitizer/UndefinedBehaviorSanitizer；探测、重封装、缩放、音频转码、取消、拒绝覆盖与失败清理。
- 输出解码、1.8～2.2 秒时长、96×64 缩放尺寸及实际文件数据包 DTS 检查。
- core、extended 的 HarmonyOS arm64-v8a 交叉编译：七个 FFmpeg 共享库、原版 ffmpeg/ffprobe、独立 NAPI 桥接库。
- 构建前后原始源码完整性、LGPLv3 配置、GPL/nonfree 禁用、ELF 架构/SONAME/NEEDED 闭包与无 RPATH 检查。
- 两版分别生成 HAR，并分别在独立消费工程中以 HAR 文件依赖编译未签名 HAP，核对运行库全部进入 HAP。
- 两版发布包、对应源码和哈希检查；17 个 Release 附件全部上传，在仓库内发布为预发布版。私有仓库的访问权限仍适用。
- housekeeping、verify、media-test、build-release、cleanup-storage 五个 job 全部成功。结束时 Actions Artifacts 数量为 0，未创建持久构建缓存。

## 下载包标识

| HAR | 大小（字节） | SHA-256 |
|---|---:|---|
| core | 11320602 | `a6732b3fab224e2bf6a2eb2102fd4a969e307f7eff7602c2877eef68773d43e4` |
| extended | 13636337 | `f57247ca63ce345272282862307a1ba027f011a5b69dc9066be1328f8c287b53` |

完整下载名和其他校验值见同次 Release 的 SHA256SUMS。源码包中的配方对应上述构建提交，之后仅修改验证记录或说明文档的提交不改变该二进制来源。

## 尚未验证

没有连接 HarmonyOS 真机执行 HAR/CLI，未证明 API12 设备运行兼容性、真实网络 TLS 行为、硬件编解码或 LGPL 修改库替换/重签名安装流程。独立 HAP 编译通过不能替代这些验证，因此本次保持预发布状态。

ArkTS API 提供探测、重封装、软件转码、单输入滤镜、取消和进度查询；不提供任意 FFmpeg 命令解释器。硬件后端由使用方独立的 HarmonyOS AVCodec Engine 提供，不向 FFmpeg 注册 OHOS codec。
