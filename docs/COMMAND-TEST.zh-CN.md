# FFmpeg 命令执行实验版

目标为 HarmonyOS 5 / API 12 起的手机应用；当前未完成真机运行验证。本版本在 HAR 中加入独立命令动态库，经 NAPI 工作线程调用 FFmpeg 9.0.2 的适配后命令入口，不执行 shell，不依赖 Native 子进程 API。

## 使用

使用文件名带 `-command-test.har` 的 extended 全架构 HAR。普通 HAR 中调用 execute 会明确报未启用实验引擎。

```typescript
import { FFmpeg } from '@samprojects/hmos-ffmpeg';

// 参数数组不包含开头的 ffmpeg，文件路径直接作为一个元素，无需额外加引号。
const task = FFmpeg.execute([
  '-y', '-i', inputPath,
  '-c:v', 'mpeg4', '-c:a', 'aac', outputPath
]);
const result = await task.result;
console.info(`exitCode=${result.exitCode}, cancelled=${result.cancelled}`);
console.info(result.logs);
```

`task.result` 返回 `{ exitCode, cancelled, timedOut, logs, logsTruncated }`。FFmpeg 命令失败通过非零 exitCode 表达；接口参数错误、引擎未启用或已有任务运行时抛出异常。调用方需要同时处理两种情况。

运行期间可调用 `FFmpeg.cancel(task.id)`；`FFmpeg.progressUs(task.id)` 返回最近的媒体时间戳（微秒），不是百分比，也不保证等于输出时长。v1.0.4 默认不设置总超时；省略超时参数或传 `timeoutSeconds=0` 均可持续执行，直到完成、报错或被取消。仅调用方显式传入正整数时启用总超时，正整数可设置到 2147483647 秒，取消原有 3600 秒上限；负数、小数、NaN、Infinity 和超范围值拒绝。此变更需使用重编译的新 HAR，已发布 v1.0.3 不支持。关闭总超时不关闭 `FFmpeg.cancel(task.id)`，也不绕过操作系统后台限制或 FFmpeg 自身协议超时。阻塞 I/O 的取消依赖 FFmpeg 协议实现响应中断，不能保证所有第三方协议均立即退出。

## 手机测试工程

`examples/consumer` 当前提供扩展编解码测试 v3，使用用户提供的原片及由其生成的兼容片段，覆盖 97 项转码、日志、取消、超时和恢复测试。通过 `scripts/build-command-test-app.py --video /path/input.mp4` 生成包含素材的 App；素材不写入 Git。安装和操作见 [测试 App 说明](TEST-APP.zh-CN.md)。旧版 9 项音频自检已由用户确认在 DevEco 本地模拟器通过，用户已反馈 v3 在 x86_64 DevEco 本地模拟器 97/97 项全部通过；ARM64 手机及最低系统版本仍待验证。

本地构建生成的三个消费 HAP 是未签名的编译验证产物，不能当作已经安装运行的证据。签名、安装和手机权限按自己的应用配置处理。不要替换签名或将 hdc shell 运行成功视为 App 沙箱验证成功。

## 范围与限制

- 仅接受 FFmpeg 参数数组，不提供 ffprobe 命令入口或命令字符串解析器。既有 `FFmpeg.probe()` 接口仍可使用。
- 一次只能执行一个命令，且不能与本 HAR 的 probe/remux/transcode 同时运行；遇到冲突直接报错，调用方等待已有任务结束再重试。
- 支持范围取决于已编译组件和平台权限。原有 extended 依赖保持不变；不新增 x264/x265，不宣称硬件编解码已实现。
- 不接受 shell 的 `|`、`>`、变量展开等语法，也不以 shell 解释文件名。`pipe:`、`fd:`、标准输入输出媒体流、`-stdin`、`-report`、`-progress`、`-vstats*` 和会改变进程资源/全局 CPU 设置的参数在本测试入口中明确禁用。
- 显式 `-y` 会按 FFmpeg 语义覆盖输出。未指定 `-y` 时已有文件不会被覆盖，并返回错误。
- 日志最多保留 256 KiB，单条格式化日志最多约 4 KiB；超出总量设置 logsTruncated。FFmpeg 日志回调是进程级资源，命令执行期间会被接管，结束恢复默认回调；不要同时使用另一个共享相同 FFmpeg 库实例且自行管理日志回调的 SDK。
- 相对路径、媒体 URI、网络证书和访问权限没有自动适配。首轮手机测试应使用应用 filesDir 内的绝对文件路径。

## 构建

自 v1.0.3 起，正常流水线默认生成包含命令组件的 extended 全架构 HAR；手动运行 `build-release.yml` 时 `command_test` 默认开启，显式设为 false 才构建无命令组件的包。流水线仍不保存 Actions Artifacts；需要保留下载成品时，应显式选择发布预发布版。

本地使用已安装且校验过的 HarmonyOS SDK：

```bash
export HMOS_HAR_ONLY=1 HMOS_COMMAND_TEST=1
for abi in arm64-v8a x86_64; do
  HMOS_ABI="$abi" bash scripts/build-ohos.sh extended
  HMOS_ABI="$abi" python3 scripts/cleanup-profile.py extended
done
python3 scripts/build-har.py extended --universal
python3 scripts/check-release.py dist/assets
```

命令库 `libhmosffmpegcmd.so` 单独动态链接 FFmpeg；每个 ABI 的运行库闭包从 9 个增加为 10 个。Release 仍只提供一个 HAR，实验版文件名带 `-command-test`。HAR 内保留许可证、命令源码适配差异及生成配方。

## 适配与验证边界

本次用户明确要求制作命令测试版，作为原 `DEVELOPMENT.zh-CN.md` 零补丁约束的实验例外。`prepare-command-source.py` 只处理锁定的 9.0.2，复制原始树后适配四个 fftools 文件，记录逐文件前后哈希及完整 diff。`work/src/ffmpeg` 的原始树仍执行原完整性检查，libav 源码不修改。不得将命令组件标为原版零补丁。

适配包括：库入口、选项/计数/进度状态复位、禁用应用进程信号和终端处理、取消/进度钩子、日志转发、已有文件冲突返回码。生产源码树不在原地打补丁，命令版启用该适配；显式关闭命令组件时不启用。

主机验证使用与 NAPI 相同的 `native/command.cpp`，在同一个进程里重复调用命令库，覆盖 20 次命令执行、WAV 产物内容、选项状态复位、错误重试、复杂滤镜、取消和超时重试、应用 SIGINT 处理器保留；另用 AddressSanitizer/UndefinedBehaviorSanitizer 检查 C++ 适配层及进程退出泄漏。底层 FFmpeg 动态库未做全量 sanitizer 插桩，这些结果不替代手机测试。可执行 `bash scripts/test-command-host.sh /path/to/ffmpeg-9.0.2` 复现；实验流水线在原媒体测试后执行该项，仅显式关闭命令组件的手动流水线跳过。

本地实验 HAR 复用了已发布 `v1.0.2-ci.11` 中校验过的 extended 动态库，使用锁定 SDK 为 ARM64、x86_64 重新编译命令组件和 NAPI 桥接。临时 manifest 记录基线与适配哈希。标准实验构建脚本则从锁定源码完整重建，不依赖该复用流程。没有推送或触发远端构建。

## 实时日志（实验版 v2）

`FFmpeg.readCommandLogs(session.id)` 返回 `{ logs, logsTruncated }`，任务已结束/不存在时返回 null。推荐在 ArkTS 每 150 ms 读取一次，同时用 `FFmpeg.progressUs(id)` 读微秒进度；在 finally 中清除定时器。原生工作线程写入有锁、最多 256 KiB 的每任务缓存，不直接调用 ArkTS 回调。Promise 返回后使用 `result.logs` 读取最终日志；缓存不会保留在已完成任务表中。

默认禁用终端统计回显，可在命令参数加入 `-stats -stats_period 0.2`，实时捕获 `frame= / time= / speed=` 等统计信息。普通 FFmpeg 日志无需开启 `-stats`。日志达到上限时停止追加并设置 `logsTruncated`，应用应按需要保存每项最终日志。不能通过此接口使用 shell、标准输入或 `-progress pipe:1`。

扩展视频测试说明见 [TEST-APP.zh-CN.md](TEST-APP.zh-CN.md)。

第三方库自行写入进程 stdout/stderr 的内容不保证被捕获；本接口捕获 FFmpeg 的 av_log 和 FFTools 输出，不重定向整个 App 的标准 IO。

长任务调用：`const task = FFmpeg.execute(args, 0);`；两小时总超时：`FFmpeg.execute(args, 7200)`。
