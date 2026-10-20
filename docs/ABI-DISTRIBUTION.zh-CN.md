# 全架构 HAR 与最终应用体积

## HAR 200MB，不等于设备下载 205MB

HAR 是构建依赖，最终用户接收的是应用的分发/安装包。最终体积取决于哪些架构的 `.so` 进入 HAP、应用资源、压缩和签名，不能简单把本地 HAR 大小加上业务代码大小。

例如，仅用于说明：全架构库共 200MB，其中 ARM64 运行库为 80MB，其他运行库为 120MB。若最终包已明确排除其他架构，则是约 5MB 业务内容加 ARM64 那部分，再考虑压缩/签名等差异；不会因为 HAR 原来是 200MB 就必然全部进入该包。这个数字不是本项目实测体积。

如果最终 HAP 保留所有架构，不能只根据设备是 ARM64 就保证它不会下载其他库。华为官方提供将 HAP/HSP 按 libs 架构拆分后重新打包的工具，但工具能力本身不等于已经验证某个商店发布流程必然自动拆分。本仓库没有上传用户应用到市场验证云端分发；不作此保证。

## 本项目的全架构范围

`*-all.har` 包含 `arm64-v8a` 与 `x86_64` 两套完整 FFmpeg/NAPI/C++ 运行库；同时保留这两个 ABI 的单独 HAR 与 SDK。

这里的“全架构”以当前 HarmonyOS 应用开发支持范围为准，不沿用 Android 四 ABI：HarmonyOS 应用在 DevEco Studio NEXT Developer Beta1 及以上不再支持编译 armeabi-v7a；OpenHarmony 工具链文件仍列出 ARM32 不代表商用 HarmonyOS 应用支持它。x86 32 位也不在当前交付范围内。

## ARM64 应用的明确打包配置

修改消费工程 **entry/build-profile.json5**，保留原有其他配置：

```json
{
  "apiType": "stageMode",
  "buildOption": {
    "externalNativeOptions": {"abiFilters": ["arm64-v8a"]},
    "nativeLib": {"filter": {"excludes": ["**/x86_64/**"]}}
  },
  "targets": [{"name": "default"}]
}
```

`abiFilters` 用于编译目标选择；预编译第三方库还应明确配置打包排除。x86_64 消费者反过来设置 ABI 为 x86_64，排除 `**/arm64-v8a/**`。需要包含两架构的安装包时选择两 ABI，移除排除规则，并接受最终 HAP 中确实含两套库；是否由市场再拆分需在真实发布渠道验证。

本项目 CI 从每个真实全架构 HAR 构建 ARM64、x86_64、双架构三种独立消费 HAP，解压核对 ABI 目录、九个运行库及文件哈希。出现多余架构、缺库或库内容变化就阻止发布。证据放在同次 Release 的 `*-all-consumer-validation.json`，包括最终 HAP 字节数及各 ABI 原生库字节数；这是构建产物测量，不是商店下载体积测量。

同一模块有其他第三方原生库时，仍需保证所选 ABI 的整套依赖完整；不能只补 FFmpeg 一个库的架构目录。

## 本地构建

```bash
export HMOS_ABI=arm64-v8a # 或 x86_64
bash scripts/build-ohos.sh extended
python3 scripts/build-har.py extended
python3 scripts/release-assets.py extended
# 两种 ABI 都完成后：
python3 scripts/build-har.py extended --universal
```

保持同一 checkout 和固定 SDK，所有构建从全新目录开始。全架构 HAR 使用两个 ABI 的运行库，不把 CLI、SDK 头文件、源码或调试符号塞进 HAR。

## 官方依据

- [HarmonyOS ABI 匹配 FAQ](https://developer.huawei.com/consumer/cn/doc/harmonyos-faqs/faqs-app-debugging-14)：HarmonyOS 与 OpenHarmony 的 ABI 配置区别。
- [定制多目标与产物](https://developer.huawei.com/consumer/cn/doc/doccenter-deveco-studio/ide-hmos-customized-multi-targets-and-products-guides)：nativeLib.filter 的排除配置。
- [拆包工具](https://developer.huawei.com/consumer/cn/doc/doccenter-capabilities/unpacking-tool)：按 libs / cpu-abis 拆分 HAP、HSP。

Actions 不上传 Artifacts，不创建持久缓存；单架构与全架构产物直接发布到 Release。真机执行及商店实际下载仍是单独的验证项目。
