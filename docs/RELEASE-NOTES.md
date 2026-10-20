HarmonyOS arm64-v8a FFmpeg SDK prerelease.

Download the extended HAR for Opus, MP3, VP8/VP9 and TLS support; core uses built-in FFmpeg components. Both contain the ArkTS/NAPI API and dynamically linked, unpatched official FFmpeg libraries. Native headers/libraries, original ffmpeg/ffprobe executables, debugging symbols, exact corresponding sources, build recipes, license texts, manifests and SHA-256 checksums accompany each HAR.

Gates: source integrity, license configuration, AArch64 ELF dependency closure, HAR assembly, and a separate consumer HAP compilation. These gates do not prove device execution or app-store compliance. This is a prerelease: no device runtime or LGPL replacement/reinstallation evidence is asserted. Do not describe it as device-tested or use it as a completed compliance determination.

The in-app API supports probe/remux/transcode/filter/cancel/progress through public libav APIs. It is not an arbitrary FFmpeg command interpreter. Original CLI tools are separate diagnostic executables; their use inside an app depends on platform execution policy. Hardware encoding remains an independent HarmonyOS AVCodec backend, outside FFmpeg.

This application uses FFmpeg under LGPL v3 or later. Corresponding source and build instructions are attached to this same release. Application distributors must provide notices, exact corresponding sources and a workable library replacement/relinking route appropriate to their distribution.
