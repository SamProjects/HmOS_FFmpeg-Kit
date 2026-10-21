# 鸿蒙手机执行 FFmpeg 命令的可行性复查

日期：2026-10-21。目标：手机，尽可能兼容 HarmonyOS 5；新版系统仅作为必要时的备选。

## 结论

存在可实施路线：在 HAR 内加入经过适配的 FFmpeg 命令引擎，经 NAPI 接收参数数组，在工作线程内执行。OpenHarmony FFmpegKit 已有这类实现先例。因此，不能把“当前 HAR 没有命令入口”解释成“鸿蒙无法支持 FFmpeg 命令”。

但当前项目只封装公开 libav API，没有这套命令引擎。本次完成源码核查和 Linux 主机命令基线实验，**没有完成 HarmonyOS 5 手机命令执行验证，也没有给现有 HAR 添加 execute 接口**。FFmpegKit 先例基于 FFmpeg 6.0，不能直接证明 FFmpeg 9.0.2 的进程内适配已经可用。

## 三条路线的判断

| 路线 | 本次证据 | 对手机目标的判断 |
|---|---|---|
| 公开 libav API + 自有参数解析 | 当前工程已经采用 | 能扩展命令子集，无法据此承诺官方完整命令语义 |
| 官方 FFmpeg CLI + 子进程 | 精确 9.0.2 主机基线实验通过；未测试目标 App 的 exec、文件标签、沙箱、权限 | 保留候选，不能从 Linux 或 hdc shell 成功推断手机 App 可用 |
| 适配 fftools 的进程内命令引擎 | OpenHarmony FFmpegKit 的 ArkTS/C++/命令引擎调用链可追踪 | 优先验证；不依赖新 Native 子进程 API，但需专门适配和维护 |

官方 Native 子进程接口不是任意 CLI 启动器：`OH_Ability_StartNativeChildProcess` 加载指定动态库及入口函数。所查官方文档列出的设备范围为 API 13 及以前 PC/2in1，API 14 起 PC/2in1、Tablet；其他设备返回不支持。当前项目最低 API 为 12，不能把该接口作为兼容手机的默认基础，也不能承诺提高到最新系统就能解决。

证据：[OpenHarmony 官方 Native 子进程 API 文档](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/reference/apis-ability-kit/capi-native-child-process-h.md)。本地核查快照 SHA-256：`cd42cd8a84704d5f46dc5a38eb9bc8979ad29691ae6f8745a2e576727c8dd944`。该范围描述来自 OpenHarmony 文档，实际 Huawei 设备及系统版本仍须验证。

## FFmpegKit 先例的源码证据

核查项目：[OpenHarmony-SIG/ohos_ffmpeg_kit](https://gitcode.com/openharmony-sig/ohos_ffmpeg_kit)，检出提交 `4820f039e7bdbcd36ee068bb03f570ad8f9d82be`。

- `ohos/src/main/ets/components/FFmpegMethod.ets` 将命令会话交给 Native 层。
- `ohos/src/main/cpp/ffmpegKit/ffmpegKitConfigMethod.cpp` 通过工作线程执行 `FFmpegKitConfig::ffmpegExecute`。
- `linux/src/FFmpegKitConfig.cpp` 将参数数组交给 `ffmpeg_execute(argc, argv)`。
- `linux/src/fftools_ffmpeg.c` 提供上述入口，包含入口改造、退出拦截、线程局部状态、取消及进度适配。不是给官方 libav 公共函数批量改名。
- `ohos/src/main/cpp/doc/FFmpeg/HPKBUILD` 标注基础版本 `n6.0`。其构建和依赖与本工程不同，不能直接复制预编译库来替代当前 9.0.2 extended。

## 本次实测范围与结果

从项目锁文件指定的官方地址下载 `ffmpeg-9.0.2.tar.xz`，SHA-256 与锁文件一致：`8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e`。源外编译后核对 10,399 个源文件，均与官方归档一致。

实验使用 Linux x86_64/GCC、最小 PCM/WAV 音频配置，不是鸿蒙交叉编译，不是 extended 全量配置，也不是进程内引擎测试。结果记录在 `experiments/command-execution/host-result.json`：

1. 精确 FFmpeg 9.0.2 版本检查通过。
2. 官方命令解析及含空格、分号的文件名参数通过；使用 argv，不经过 shell。
3. 音频重封装、FFprobe 输出校验及 `-progress pipe:1` 完成事件通过。
4. 非法参数返回错误，父进程存活，之后可再次启动命令。
5. 多次独立命令进程执行通过。
6. SIGINT 取消和进程回收通过，返回码 255。

独立进程天然隔离状态；以上结果**不证明**在同一进程反复调用改造后的命令入口安全。

复现实验：解压锁定的官方源码到独立目录，在另一个空目录运行：

```bash
/path/to/ffmpeg-9.0.2/configure \
  --disable-autodetect --disable-x86asm --disable-doc --disable-debug \
  --disable-network --disable-everything --enable-ffmpeg --enable-ffprobe \
  --enable-protocol=file,pipe --enable-indev=lavfi \
  --enable-filter=sine,anull,aresample --enable-encoder=pcm_s16le \
  --enable-decoder=pcm_s16le --enable-muxer=wav,null --enable-demuxer=wav
make -j4 ffmpeg ffprobe
python3 /path/to/HmOS_FFmpeg-Kit/experiments/command-execution/host-smoke.py \
  --ffmpeg ./ffmpeg --ffprobe ./ffprobe --report ./host-result.json
```

## 进程内方案需要验证的事项

官方 `fftools/ffmpeg.c` 提供程序 `main`，不是安装后的公共 libav 命令执行 API。9.0.2 的该文件仍包含全局/静态状态、进程级信号和日志操作以及信号退出路径；简单重命名 main 不足以证明可重入性。需要独立的命令组件处理入口、退出、资源清理、状态复位、日志、进度及取消，初版宜串行执行，不承诺并发会话安全。

这会改变 `docs/DEVELOPMENT.zh-CN.md` 中禁止改造 fftools、要求 Zero-Patch 的原有设计。当前软件管线无需调整；新增命令组件若采用源码适配，必须如实记录补丁和许可证边界，不能继续宣称所有 FFmpeg 相关源码均零修改。应用闭源与第三方组件的对应源码义务需要分别处理。

下一阶段应先做 API 12/ARM64 的手机最小验证包：`-version`、非法参数后再次执行、真实文件重封装/转码、引号与中文路径、复杂滤镜、循环多次调用、取消后重试、后台及页面退出、内存和线程回收。再扩展 x86_64 打包验证。命令引擎只支持已编译的组件，不包含 shell 的管道、重定向、脚本，也不会因此自动获得硬件编解码能力。

本次没有连接 hdc、DevEco 模拟器或鸿蒙真机，没有安装测试包，没有触发 Actions 或推送提交。生产流水线和已有 HAR 的功能保持当前状态。
