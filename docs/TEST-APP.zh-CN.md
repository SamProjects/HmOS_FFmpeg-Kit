# FFmpeg 扩展编解码测试 App v3

引用 extended 全架构 command-test HAR，最低 API 12，包名 `com.samprojects.ffmpegsmoke`。内置用户原始 AV1 + AAC 视频和由它生成的 8 秒 MPEG4 + AAC 片段，全程离线，不请求媒体或网络权限。原片只进入生成的 HAP 和本地项目包，不写入 Git。

## 安装和操作

下载未压缩的 `1.hap` 到电脑，启动 DevEco 本地模拟器后安装：

```text
hdc install -r 1.hap
hdc shell aa start -b com.samprojects.ffmpegsmoke -a EntryAbility
```

这是供允许未签名开发包的本地模拟器使用的 unsigned debug HAP。签名策略拒绝安装时，可使用生成的项目在 DevEco 中按 IDE 的 Signing Configs 流程签名运行。Cloud 无法连接用户电脑的模拟器。

点击“运行全部 97 项测试”，单项失败后继续。顶部显示实际加载的 FFmpeg 许可及编码器/解码器注册数量。用“显示实时日志 / 显示测试结果”切换视图；日志和结果可长按复制。

- 取消当前任务：取消这一项，测试继续；手动取消原本应成功的项目会记为失败。
- 停止全部：请求取消当前任务，并停止后续测试。
- 手动中断演示：按实时速度进行最长 60 秒的转码，供手动点击取消、观察日志和进度，然后重新测试。
- 离开页面会请求取消当前命令，并停止后续测试。

界面展示日志末尾 18000 字符，原生每任务最多保留 256 KiB，达到上限标记 `logsTruncated`。日志在执行期间每 150 ms 刷新，`-stats -stats_period 0.2` 用于输出 `frame/time/speed` 等信息。

## 97 项测试内容

共享矩阵由 `scripts/generate-command-test-cases.py` 生成到 `examples/consumer/entry/src/main/resources/rawfile/command-cases.json`。

保留原来的 60 项版本/列表、重封装、音频处理、滤镜、截帧、中文路径、覆盖策略、并发拒绝、错误恢复、立即/处理中/重复取消、超时、日志上限、重复调用等测试。v3 有两处关键修正：

1. 原片 AV1 解码改为必须通过，显式使用新编入的 dav1d 软件解码器。
2. 第 58 项 `-v quiet` 要求结果日志为空，并保存出 0 字节文件。空字符串不交给 HarmonyOS `TextEncoder.encodeInto`，避免此前的 `undefined.buffer` 错误；第 59 项仍是独立的日志截断测试。

扩充项目包括：运行时 LGPLv3 文本、AV1 原片转 H.264/HEVC、libaom 和 SVT-AV1 编码、OpenH264、Kvazaar、VP8/VP9、VVenC/VVC、XEVE/XEVD、APV、Theora、JPEG 2000、JPEG XL，以及 LAME、Shine、TwoLAME、Opus、Vorbis、Speex、GSM/WAV49、AMR-NB/WB、LC3、iLBC、Codec2 编解码。另对 H.264、HEVC、libaom AV1、SVT-AV1 分别验证转码中取消和取消后恢复。

输出检查文件大小、编码格式、指定尺寸/时长/采样率/声道；选定输出再执行完整解码。自动取消响应和超时退出有时间上限检查。编码器参数范围、许可和未加入的后端见 [CODECS.zh-CN.md](CODECS.zh-CN.md)。

## 报告

应用私有目录保存 `test-report.json` 和每项 `test-XX.log`。报告包含实际参数、通过/失败、退出码、取消/超时标记、耗时、实时日志读取和最大进度。可长按复制界面结果，或用 `hdc hilog` 过滤 `FFmpegTest` 获取逐项结构化记录。只有允许访问调试应用私有目录的镜像才能直接拉取这些文件。

## 构建与验证边界

```bash
python3 scripts/build-command-test-app.py \
  --video /private/path/input.mp4 \
  --har dist/assets/hmos-ffmpeg-1.0.2-extended-all-command-test.har \
  --abi x86_64 \
  --output dist/emulator-codec-test
```

构建用系统 FFmpeg 生成兼容片段，原片保持字节不变；核对所选架构的全部动态库与 HAR 哈希、ArkTS 字节码、HAP CRC 和两个素材的哈希。`validation.json` 记录所选架构、测试项数、包和 HAR 哈希。`--abi x86_64` 只影响模拟器测试 HAP，输入与交付 HAR 仍保留全架构；不传此选项则构建双架构测试 HAP。

主机功能验证通过固定版本 FFmpeg 的真实进程内命令适配器、原生 probe 和再次解码完成，不使用旧版系统 FFmpeg 判断新格式。主机通过和 HAP 构建通过均不能替代 HarmonyOS 模拟器或真机验证，最终以用户安装后的报告为准。
