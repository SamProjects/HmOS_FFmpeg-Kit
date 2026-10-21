# FFmpeg 视频、实时日志和中断测试 App v2

使用 extended 全架构 command-test HAR，最低 API 12，包名 `com.samprojects.ffmpegsmoke`。全程离线，不请求媒体或网络权限。

## 安装和操作

下载全部分卷及 `merge-and-extract.cmd`，放在同一目录，运行脚本还原 HAP。也可用 7-Zip 打开 `.zip.001` 解压。

在电脑启动 DevEco 本地模拟器后执行：

```text
hdc install -r ffmpeg-command-test-emulator-unsigned.hap
hdc shell aa start -b com.samprojects.ffmpegsmoke -a EntryAbility
```

这是允许未签名开发包的本地模拟器使用的 unsigned debug HAP。若安装被签名策略拒绝，使用附带项目在 DevEco 中按 IDE 的 Signing Configs 流程签名运行。云环境无法连接用户电脑的模拟器。

点击“运行全部 60 项测试”，预计需要 1～3 分钟，单项失败仍继续。用“显示实时日志 / 显示测试结果”切换视图。日志可长按复制，界面展示末尾 18000 字符，原生日志每个命令最多保留 256 KiB，达到上限标记 `logsTruncated`。

- “取消当前任务”：取消这一项，完整测试继续；用户主动取消本应成功的项目会记为失败。
- “停止全部”：取消当前任务，并停止后续测试。
- “手动中断演示”：按实时速度进行最长 60 秒的视频转码，供手动点击取消并观察响应，然后可立即重新运行测试。
- 离开页面会请求取消当前命令并停止后续测试。

## 素材和能力边界

使用用户提供的约 300 秒 AV1 + AAC MP4 原片；额外生成其前 8 秒的 320×180 MPEG4 + AAC 片段。原片用于全片重封装、片段复制、音频提取、音频转码以及 AV1 实际解码能力检测。兼容片段用于验证视频滤镜和转码。

当前 HAR 没有 libdav1d/libaom AV1 软件解码器，也没有接入可用的 AV1 硬件解码后端。原生 `av1` 解码器被列出不等于能在当前系统解码。能力检测的明确“不支持”单独统计，不伪装为成功；其他非预期错误记为失败。AV1 无损重封装不需要解码。此版本不新增 AV1 编解码依赖，不宣称原片能转码视频。

原片只加入生成的 HAP 和本地项目 ZIP，不写入 Git，也不上传远端。

## 覆盖范围

60 项共享测试矩阵位于 `examples/consumer/entry/src/main/resources/rawfile/command-cases.json`，由 `scripts/generate-command-test-cases.py` 生成：

- 版本、编码器/解码器/滤镜列表、错误参数、缺失输入、非法编码器/滤镜/流映射、输出创建失败。
- 原片全片重封装、截取复制、音轨提取、PCM/AAC 音频转码、AV1 解码能力。
- MPEG4/AAC 转码、缩放、裁剪、旋转、帧率、灰度、翻转、复杂滤镜和映射、PNG/JPEG 截帧、音频采样率/声道/音量/速度、去音轨。
- 中文、空格和分号路径；拒绝覆盖和强制覆盖恢复。
- 执行结束前读取实时日志、FFmpeg `frame=` 回显和进度；静默日志级别、256 KiB 截断和后续任务日志隔离。
- 立即取消、处理中取消、重复取消、每种取消后的恢复、超时退出及恢复、并发拒绝及恢复、进程/标准 IO 参数拒绝。
- 连续五次转码，检查重复调用状态复位。

成功输出检查大小、probe 元信息、指定编码/尺寸/采样率/声道/时长；部分视频输出再执行完整解码验证。自动取消响应和超时退出有时间上限检查。

## 报告和复现

应用私有目录中保存 `test-report.json` 和 `test-01.log` 至 `test-60.log`。报告含命令参数、状态、退出码、取消/超时标记、耗时、实时读取次数和最大进度。可长按复制界面结果，或在电脑使用 `hdc hilog` 过滤 `FFmpegTest` 获取逐项结构化记录。只有允许访问调试应用私有目录的镜像才能直接 `hdc file recv` 拉取这些文件。

```bash
python3 scripts/build-command-test-app.py \
  --video /private/path/input.mp4 \
  --har dist/assets/hmos-ffmpeg-1.0.2-extended-all-command-test.har \
  --output dist/video-test-app
```

`--video` 必填。构建使用系统 ffmpeg 生成兼容片段；原片保持字节不变。构建检查两种架构全部 20 个动态库与 HAR 哈希、ArkTS 字节码、HAP CRC 和两个视频素材哈希。

主机矩阵通过实际 FFmpeg 9.0.2 进程内命令适配器执行；主机成功不能替代 HarmonyOS 模拟器或真机测试。当前 Cloud 无用户模拟器，HAP 的模拟器结果以用户实际运行报告为准。
