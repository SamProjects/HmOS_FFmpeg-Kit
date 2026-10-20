# 导入鸿蒙项目

下载同一次 Release 的 `hmos-ffmpeg-1.0.0-extended-arm64-v8a.har`，放入应用的 `entry/libs/`，在 **entry 模块** `oh-package.json5` 添加：

```json
{"dependencies":{"@samprojects/hmos-ffmpeg":"file:./libs/hmos-ffmpeg-1.0.0-extended-arm64-v8a.har"}}
```

安装依赖（ohpm install），目标 ABI 选择 arm64-v8a，兼容 API 12 及以上。HAR 包含桥接、FFmpeg so 和所需 C++ runtime，不要再同时引入另一套同名 FFmpeg so。消费项目需要 DevEco/Command Line Tools 中支持本包模型的 Hvigor；原生最低 API 和实际运行兼容性仍需在目标设备验证。

```typescript
import { FFmpeg } from '@samprojects/hmos-ffmpeg';

const build = FFmpeg.getBuildInfo();
const media = await FFmpeg.probe('/sandbox/input.mp4');
const copy = FFmpeg.remux('/sandbox/input.mp4', '/sandbox/output.mkv');
await copy.result;

const job = FFmpeg.transcode({
  input: '/sandbox/input.mp4', output: '/sandbox/scaled.mp4',
  videoCodec: 'mpeg4', audioCodec: 'aac', videoFilter: 'scale=640:-2'
});
// 工作期间可轮询 FFmpeg.progressUs(job.id)，或 FFmpeg.cancel(job.id)
await job.result;

// 提取并转换音频：videoCodec: 'none', audioCodec: 'pcm_s16le'，输出 .wav
// 原样保留某一流：codec 为 'copy'；丢弃该类流：codec 为 'none'
```

路径替换为应用有权限的绝对沙箱路径。输出不得已存在，失败/取消会删除本次创建的不完整输出。`probe` 还接受 `fd:<打开的文件描述符>`；整个异步任务结束之前，调用者保持其 FileIO 文件对象存活。内部 dup 不关闭调用者的 fd，但 dup 共享当前位置；不要并发读取同一 fd。源 URI 由应用通过系统文件选择器授权并打开，不能直接把 `file://` 或图库 URI 当 libc 路径。

`probe` 返回本项目定义的格式/时长/流信息，不承诺完整 FFprobe JSON。`progressUs` 为最近输入包时间戳，未知可能为负数，并非精确输出进度或百分比；会话结束返回 -1。全进程至多四个并行会话，每路 codec/filter 最多两线程。`cancel` 为协作取消；正在阻塞的本地文件/codec 操作不保证立即退出。网络不活动期限 30 秒。

transcode 处理输入的各音视频流，其他流尝试原样复制；目标容器不支持某流会拒绝并清理输出。视频默认 MPEG-4 Part 2，音频默认 AAC；H.264/HEVC 软件编码器未因禁用 x264/x265 而自动可用。用 getCapabilities 查询真实编码器/滤镜；自定义视频/音频滤镜必须分别是一入一出 filter chain，复杂多输入 filter_complex 不在该接口范围内。默认不支持输入尺寸或像素格式在同任务中途变化，不支持硬件编码、完整 FFmpeg 命令解析或跨轨自动混音。

HTTPS 输入需应用声明 `ohos.permission.INTERNET`，通过 `caFile` 提供应用可读的可信 CA PEM 文件，开启证书与主机验证。没有可用 CA 时请求应失败；绝不关闭验证来规避错误。core 没有 TLS 外部依赖。网络及硬件能力都需要单独做设备测试。

原生使用者下载同版 `-sdk.tar.gz`，以 imported SHARED targets 链接 sdk/include 和 sdk/lib；运行时打包 runtime/arm64-v8a 的完整闭包。库采用 `libavcodec-<major>.so` 命名，由外置 make 参数生成；没有对源码或 ELF 作补丁。不要手动改文件名，不要静态合并 FFmpeg 进入私有 so。

SDK 包的 bin/ffmpeg 和 bin/ffprobe 是 OHOS ELF。开发 shell 可以验证；App 内能否启动它们取决于沙箱/执行政策。本 HAR 没有把 main 重命名或嵌进应用。

原生 SDK 的 CMake 导入配置可随解压目录搬移：

```cmake
find_package(FFmpeg CONFIG REQUIRED PATHS "<解压目录>/sdk" NO_DEFAULT_PATH)
target_link_libraries(your_native_target PRIVATE FFmpeg::FFmpeg)
set_target_properties(your_native_target PROPERTIES SKIP_BUILD_RPATH TRUE)
# 也可按需选择 FFmpeg::avformat / avcodec / avfilter / avutil 等目标。
```

应用仍需打包 runtime/arm64-v8a 的运行库闭包；链接成功不能代替运行库打包。

## 版权与分发

应用“关于/开源许可”页标明使用 FFmpeg、实际版本、LGPLv3-or-later、许可全文及**同次发布对应源码**入口。原生库与第三方 license 原文随包提供。原创桥接代码采用 MIT，FFmpeg 仍采用其构建对应的 LGPL；HAR 这个“静态共享包”名称不代表 FFmpeg 被静态链接，FFmpeg 继续以独立 so 动态链接。

本仓库目前为私有仓库时，仓库 Release 链接对所有最终用户并不一定可访问；应用正式分发前应将对应源码和配方放到用户可访问的服务，不能只提供受限链接。

必须评估并实际验证用户替换兼容 LGPL 库的方式；签名/安装受限时评估可行重链接路径，详见 replacement-and-relink.md。预发布包的构建通过不能代替设备运行和分发合规结论。
