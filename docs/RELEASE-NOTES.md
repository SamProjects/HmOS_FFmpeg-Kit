FFmpeg Kit v1.0.4：包含命令执行接口和扩展音视频编解码器的 HarmonyOS 全架构 HAR。

## 下载

唯一附件：`hmos-ffmpeg-1.0.4-extended-all-command-test.har`，同时包含 arm64-v8a、x86_64，每架构 10 个运行库。HAR 包版本为 1.0.4，FFmpeg 版本为 9.0.2，最低目标 API 12 / HarmonyOS 5。

保留 FFmpeg 默认可构建的内置组件；每个架构的编译注册清单包含 200 个编码器、518 个解码器，这些数量不等于所有组件均已逐一运行验证。新增 AV1（libaom / SVT-AV1 编码、dav1d 解码）、OpenH264、Kvazaar HEVC、VVenC VVC、XEVE/XEVD EVC、OpenAPV、Theora、OpenJPEG、JPEG XL，以及多种音频编码器；完整实现和许可边界见 docs/CODECS.zh-CN.md。禁用 GPL/nonfree，不包含 x264/x265/FDK-AAC。

## 总超时修复

`FFmpeg.execute(args, 0)` 关闭总超时；正整数可设置至 2147483647 秒，默认值仍为 300 秒。取消原先 3600 秒上限，手动取消保持可用。拒绝负数、小数、非有限数和越界值，避免 int32 转换截断或回绕。已发布 v1.0.3 不具备此能力，必须更换新 HAR。

## 命令调用

```typescript
import { FFmpeg } from '@samprojects/hmos-ffmpeg';
const task = FFmpeg.execute([
  '-y', '-i', inputPath,
  '-c:v', 'libopenh264', '-c:a', 'aac', outputPath
], 300);
const result = await task.result;
console.info(result.logs);
```

支持执行期间读取日志、媒体时间进度、取消和超时。参数数组不含 ffmpeg 程序名；不执行 shell，一次运行一个命令。标准输入输出管道和部分进程级参数受限，具体见 docs/COMMAND-TEST.zh-CN.md。修复测试 App 第 58 项保存空日志时的 undefined.buffer 错误。

## 验证与范围

- 上一版 v1.0.3 用户提供的 x86_64 DevEco 本地模拟器结果：97/97 项通过、0 失败、0 不支持，覆盖视频/音频编码、输出重新解码、日志、取消、超时及恢复。
- 本版 Linux 主机同进程命令适配器：101/101 项通过，142 次命令调用，其中 41 次重新解码输出；C++ 适配器、探测引擎和驱动通过 ASan、UBSan、退出泄漏检查，底层 FFmpeg 和外部库未全面插桩。
- 发布前核对锁定源码完整性、LGPLv3 配置、38 个必需外部编解码组件、两种 ABI 的 ELF 依赖闭包、HAR 哈希，以及 ARM64 / x86_64 / 双架构消费 HAP 编译。
- 本版新增超时功能尚未在鸿蒙设备上运行验证。ARM64 手机、HarmonyOS 5 最低版本和应用市场拆分尚未实际运行验证，因此继续作为预发布版。
- XEVE 短片默认 B 帧路径存在已知内存问题，当前通过的 EVC 用例使用 `-bf 0`；详见编解码说明。

命令组件沿用已记录差异的 fftools 适配，以独立动态库交付；libav 原始源码保持不变。HAR 内保留依赖许可证、版权和专利声明以及命令适配配方。项目自有代码 MIT，FFmpeg 按 LGPLv3-or-later 配置；对外分发仍需落实对应源码访问及库替换/重链接等义务。

本次仅发布全架构 HAR，不附带测试视频、测试 HAP、SDK、CLI、调试符号或源码归档。
