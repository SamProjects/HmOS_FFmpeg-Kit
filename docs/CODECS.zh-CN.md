# extended 编解码器扩充与许可边界

构建继续使用 FFmpeg 9.0.2，启用 `--enable-version3 --disable-gpl --disable-nonfree --disable-autodetect`。保留 FFmpeg 默认可构建的原生软件编解码器，外部库逐项显式加入，最终配置必须报告 `LGPL version 3 or later`。这不是只允许名称为 LGPL 的依赖：经核验的 BSD、MIT、Apache 等兼容组件也可组合使用。

## 视频和图像

| 格式 | 外部编码实现 | 解码实现 |
|---|---|---|
| AV1 | libaom、SVT-AV1 | dav1d、libaom；优先使用软件解码，不依赖手机硬件 AV1 后端 |
| H.264/AVC | OpenH264 | FFmpeg 原生、OpenH264 |
| HEVC/H.265 | Kvazaar | FFmpeg 原生 |
| VVC/H.266 | VVenC | FFmpeg 原生 |
| EVC | XEVE | XEVD |
| VP8/VP9 | libvpx（原有） | FFmpeg 原生、libvpx |
| Theora | libtheora | FFmpeg 原生 |
| APV | OpenAPV | FFmpeg 原生 |
| JPEG 2000 | OpenJPEG，另保留原生编码器 | FFmpeg 原生 |
| JPEG XL（含动画接口） | libjxl | libjxl |
| AVS3 | 本配方无 FFmpeg 可集成的非 GPL 外部编码实现 | uavs3d |

FFmpeg 自带的 MPEG4、MPEG1/2、MJPEG、PNG、GIF、FFV1、HuffYUV、ProRes、DNxHD/DNxHR、各种 PCM 等能力继续按平台实际配置保留，不使用 `--disable-everything` 精简交叉构建。实际列表以产物的 `FFmpeg.getCapabilities()`、`-encoders` 和 `-decoders` 为准。

## 音频

新增 Vorbis、Speex、TwoLAME/MP2、Shine/MP3、GSM/WAV49、iLBC、LC3、AMR-NB、AMR-WB、Codec2；原有 libopus、LAME 以及 FFmpeg 原生 AAC、FLAC、ALAC、PCM 等保留。具体采样率、声道和码率由每种编码器决定，不是任意输入参数均可接受。

## 未加入项目及原因

- x264、x265、Xvid、xavs/xavs2、davs2 等 GPL 库与本项目的 GPL 禁用要求冲突；分别使用 OpenH264、Kvazaar 等兼容实现提供相应常用编码能力。
- FDK-AAC 等 FFmpeg 分类为 nonfree 的组件不加入。
- rav1e 是额外的 AV1 编码器。本固定 HarmonyOS NDK 配方尚没有经过验证并锁定的 OHOS Rust 标准库、cargo-c 和传递依赖构建链，未把它冒充为已编译；AV1 编码由 libaom 和 SVT-AV1 提供。
- NVENC/CUDA、QSV、VAAPI、VideoToolbox、Android MediaCodec 等依赖各自平台的后端不能按名称视作鸿蒙可用。注册列表不等于设备硬件支持；本轮不把未验证的硬件封装计作已验证编码能力。

## 源码与许可证据

版本、下载地址和 SHA-256 固定在 `config/sources.lock.json`；依赖开关和必须存在的编解码组件固定在 `config/codec-dependencies.json`。JPEG XL 的 Brotli、Highway、skcms 使用其正式发布版引用的精确提交，不跟随分支。

原始 FFmpeg 及外部库源码树保持原样，依赖在私有复制树中编译；命令实验版仅沿用已有且记录差异的 fftools 适配，不修改 libav 源码。依赖配方只安装所需静态库到 FFmpeg 的私有 prefix，最终仍交付独立的 FFmpeg 动态库及 HAR；不会额外发布依赖工具或整套 SDK。

构建输出的 pkg-config 元数据会做两项有记录的修正：OHOS 的 C++ 运行库名使用 `-lc++`；OpenJPEG 2.5.4 的 `-l-lpthread` 修正为 `-lpthread`。EVC 的上游安装目标还依赖不需要的共享库，本配方只复制未改写的静态产物、公共头和生成的 pc 文件。Shine 在私有源副本中构建，以满足该版本的相对路径假设。Codec2 和 Speex 的两个内部 LSP 函数同名，Codec2 通过编译宏将其加上 `codec2_` 前缀隔离；不使用允许重复定义的链接选项，公开的 codec2/FFmpeg API 不变。OpenAPV 与 XEVE 的 ARM NEON 内部 SAD 函数也使用相同方法增加 `oapv_` 前缀，避免两库同时链接时重名。

`license_gate` 检查实际 GPL/NONFREE/VERSION3 和许可字符串；`codec_gate` 检查实际 `config_components.h`，缺少必需组件直接失败。SHA-256、源码完整性、两种 ABI 的 ELF/SONAME/依赖闭包及 HAR 消费矩阵继续检验。许可证、COPYRIGHT 和 PATENTS（含 `.md` 后缀）一并保留。软件许可配置不能替代特定使用场景所需的专利授权。

## 测试

测试 App v3 包含原始 AV1 视频及兼容片段，运行 97 项检查，包括新增视频/音频编码、输出元信息与再次解码、四种主要视频编码器的取消和恢复、实时日志和进度、超时、错误隔离及空日志文件。第 58 项专门确认 `-v quiet` 返回空日志且保存出 0 字节文件，避免 HarmonyOS 空字符串编码返回 undefined 的问题。

主机测试通过同一 C++ 命令适配器与 `engine.probe` 检查输出，重新解码也在同一进程中进行，避免调用旧版系统 FFmpeg 判断新格式。主机结果不能替代 HarmonyOS 模拟器或真机结果。

本轮 Linux 主机验证：97/97 通过，实际调用命令 137 次，其中 40 次用于重新解码输出。启用 AddressSanitizer、UndefinedBehaviorSanitizer 和退出时泄漏检查；仅 C++ 适配器、探测引擎和测试驱动经过插桩，FFmpeg 与外部编码库没有全面插桩，不能据此宣称所有内部路径无内存问题。报告见 `experiments/command-execution/expanded-video-host-validation.json`。

XEVE 0.7.1 的短片默认 B 帧配置在主机测试中出现缓存图像未释放。本轮 EVC 用例显式使用 `-bf 0`，转码、再次解码及退出泄漏检查通过；这不代表其默认 B 帧路径已修复。OpenAPV 固定为与当前 FFmpeg 接口兼容的 0.3.0.0；切换版本时移除旧的平铺静态库，防止误链接到另一安装目录的旧产物。
