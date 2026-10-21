# FFmpeg 命令测试 App（DevEco 本地模拟器）

本 App 引用已有的 extended 全架构 command-test HAR，提供“一键自检”和取消按钮。内置 0.2 秒音频，不需要联网、选择文件或额外媒体权限。应用名称为“FFmpeg 命令测试”，包名 `com.samprojects.ffmpegsmoke`。

## 安装

下载 `ffmpeg-command-test-emulator-unsigned.hap` 到**电脑**，启动 DevEco Studio 的本地模拟器。将 HAP 从电脑拖入模拟器窗口安装，或在电脑终端使用 DevEco SDK 自带的 hdc：

```text
hdc list targets
hdc install ffmpeg-command-test-emulator-unsigned.hap
hdc shell aa start -b com.samprojects.ffmpegsmoke -a EntryAbility
```

hdc 位于 DevEco SDK 的 `default/openharmony/toolchains` 目录；Windows 使用 `hdc.exe`，也可将该目录加入 PATH。存在多个设备时，在每条设备操作中使用 `hdc -t <目标ID> ...`，目标 ID 取自 `hdc list targets`。路径包含空格时用双引号包住 HAP 的完整路径。

这是未签名的 debug HAP，供允许未签名开发包的 DevEco 本地模拟器使用；不是应用市场或真机安装包。不要把 HAP 当作 HAR 放进依赖，也不要只在模拟器文件管理器中点开尝试安装。

若模拟器镜像拒绝签名，保留完整 HDC 安装报错，并使用同目录的 `ffmpeg-command-test-project.zip`：解压，在 DevEco Studio 中打开 `FFmpegCommandTest`，选择本地模拟器并运行；如 IDE 提示需要签名，按其 Signing Configs 自动签名流程完成。不需要上传账号密码或私钥。

## 测试

打开 App 后显示 FFmpeg 9.0.2 和“准备就绪”。点击“一键自检”，依次执行：

1. 版本查询。
2. 非法参数返回错误（预期失败）。
3. 错误后再次执行。
4. 音频重封装，并通过 probe 检查输出。
5. 音量滤镜，并通过 probe 检查输出。
6. 取消运行中的命令。
7. 取消后再次执行。
8. 超时退出。
9. 超时后再次执行。

全部完成后显示“全部通过 · 9 / 9”。建议连续执行两次，确认状态复位。如果失败，界面会显示停止阶段及错误；可长按复制结果，或在电脑运行 `hdc hilog` 并过滤 `FFmpegTest` 和崩溃信息。

只需把最终状态截图或失败信息发回即可判断下一步。未通过某一项时不应把编译通过当作运行成功。

## 构建与验证边界

HAP 同时包含 ARM64、x86_64，最低兼容 API 12。构建会逐个核对其中 20 个动态库与输入 HAR 的哈希，检查 ArkTS 编译代码和内置音频。`validation.json` 记录 HAP 与 HAR 哈希。

当前云工作区无法访问你的电脑模拟器，因此这里只完成编译与包结构验证，没有声称已在你的模拟器中安装或运行成功。模拟器验证也不等价于真机验证。

复现构建：

```bash
python3 scripts/build-command-test-app.py \
  --tools /path/to/command-line-tools \
  --har /path/to/hmos-ffmpeg-1.0.2-extended-all-command-test.har
```

工具链环境与 HAR 的命令执行能力说明见仓库 `docs/COMMAND-TEST.zh-CN.md`。本地测试 App 不影响正常 Release 流水线。
