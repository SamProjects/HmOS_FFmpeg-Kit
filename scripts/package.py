#!/usr/bin/env python3
from common import *
import importlib.util
import shutil
import sys

profile = sys.argv[1]
key = profile_key(profile)
build = WORK / 'build' / key
prefix = WORK / 'prefix' / key
sdk = Path(os.environ['OHOS_NATIVE'])
package = DIST / key
package.mkdir(parents=True, exist_ok=False)
runtime = package / 'runtime' / ABI
runtime.mkdir(parents=True)
for lib in (prefix / 'lib').glob('lib*-*.so'):
    shutil.copy2(lib, runtime / lib.name)
shutil.copy2(build / 'bridge/libhmosffmpeg.so', runtime / 'libhmosffmpeg.so')
shutil.copy2(sdk / 'llvm/lib' / TRIPLE / 'libc++_shared.so', runtime / 'libc++_shared.so')
# SDK runtime is kept verbatim. Library build IDs/symbols are never manufactured.
symbols = package / 'symbols' / ABI
symbols.mkdir(parents=True)
for lib in runtime.glob('*.so'):
    if lib.name == 'libc++_shared.so':
        continue
    run([sdk / 'llvm/bin/llvm-objcopy', '--only-keep-debug', lib, symbols / (lib.name + '.debug')])
    run([sdk / 'llvm/bin/llvm-strip', '--strip-debug', lib])
shutil.copytree(prefix / 'include', package / 'sdk/include')
shutil.copytree(prefix / 'lib', package / 'sdk/lib', symlinks=True)
cmake_config = ['set(FFmpeg_VERSION "' + PROJECT['ffmpeg'] + '")']
for component in ['avutil','swresample','swscale','avcodec','avformat','avfilter','avdevice']:
    lib = list((prefix / 'lib').glob('lib' + component + '-*.so'))
    if len(lib) != 1: raise ValueError('Ambiguous imported library: ' + component)
    cmake_config += [f'if(NOT TARGET FFmpeg::{component})',
        f'  add_library(FFmpeg::{component} SHARED IMPORTED)',
        f'  set_target_properties(FFmpeg::{component} PROPERTIES',
        f'    IMPORTED_LOCATION "${{CMAKE_CURRENT_LIST_DIR}}/lib/{lib[0].name}"',
        '    INTERFACE_INCLUDE_DIRECTORIES "${CMAKE_CURRENT_LIST_DIR}/include")', 'endif()']
cmake_config += ['if(NOT TARGET FFmpeg::FFmpeg)', '  add_library(FFmpeg::FFmpeg INTERFACE IMPORTED)',
    '  set_target_properties(FFmpeg::FFmpeg PROPERTIES INTERFACE_LINK_LIBRARIES "FFmpeg::avdevice;FFmpeg::avfilter;FFmpeg::avformat;FFmpeg::avcodec;FFmpeg::swscale;FFmpeg::swresample;FFmpeg::avutil")', 'endif()']
(package / 'sdk/FFmpegConfig.cmake').write_text('\n'.join(cmake_config) + '\n')
shutil.copytree(prefix / 'bin', package / 'bin')
shutil.copytree(ROOT / 'harmony', WORK / 'har' / key)
har = WORK / 'har' / key / 'ffmpeg'
shutil.copytree(runtime, har / 'libs' / ABI)
licenses = package / 'licenses'
licenses.mkdir()
for name, source in SOURCES.items():
    if profile == 'core' and name != 'ffmpeg':
        continue
    directory = licenses / name
    directory.mkdir()
    for p in (WORK / 'src' / name).rglob('*'):
        if p.is_file() and (p.name.startswith(('COPYING','LICENSE','NOTICE')) or p.name in {'PATENTS','AUTHORS'}):
            dest = directory / p.relative_to(WORK / 'src' / name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
# libc++ runtime redistributable notices from this exact SDK.
for p in [sdk / 'NOTICE.txt', sdk / 'llvm/NOTICE.txt', sdk / 'llvm/LICENSE.TXT']:
    if p.is_file(): shutil.copy2(p, licenses / ('sdk-' + p.parent.name + '-' + p.name))
shutil.copytree(licenses, har / 'licenses')
shutil.copy2(ROOT / 'LICENSE', licenses / 'project-MIT.txt')
shutil.copy2(ROOT / 'LICENSE', har / 'licenses/project-MIT.txt')
shutil.copytree(licenses, har / 'src/main/resources/rawfile/hmos_ffmpeg_licenses')
shutil.copy2(ROOT / 'docs/INTEGRATION.zh-CN.md', har / 'README.md')
for file in ['config.h','config_components.h','configure-args.txt','configure.log','build.log','install.log']:
    shutil.copy2(build / 'ffmpeg' / file, package / file)
import re
components = (build / 'ffmpeg/config_components.h').read_text()
write_json(package / 'compiled-capabilities.json', {
    'method':'configure component inventory; runtime enumeration is available through FFmpeg.getCapabilities()',
    'enabled': re.findall(r'^#define CONFIG_(\w+) 1$', components, re.M)})
shutil.copy2(build / 'license-gate.json', package / 'license-gate.json')
shutil.copy2(WORK / 'sdk.json', package / 'sdk-build.json')
spec = importlib.util.spec_from_file_location('verify_build', ROOT / 'scripts/verify-build.py')
gate = importlib.util.module_from_spec(spec)
# verify-build module reads argv[1], which remains profile here.
spec.loader.exec_module(gate)
gate.inspect(list(runtime.glob('*.so')) + list((package / 'bin').iterdir()), package / 'elf.json')
write_json(package / 'manifest.json', {
    'project': PROJECT, 'profile': profile, 'abi': ABI, 'commit': os.environ.get('GITHUB_SHA', 'local'),
    'validation': {'sourceIntegrity': True, 'licenseConfig': True, 'elfClosure': True, 'device': False, 'appRuntime': False},
    'libraries': {p.name: digest(p) for p in runtime.glob('*.so')}, 'sources': SOURCES,
    'naming': 'GNU make command-line overrides; no source or ELF patching'})
write_json(package / 'sbom.spdx.json', {
    'spdxVersion':'SPDX-2.3','dataLicense':'CC0-1.0','SPDXID':'SPDXRef-DOCUMENT',
    'name':f'hmos-ffmpeg-{PROJECT["version"]}-{profile}',
    'documentNamespace':f'https://github.com/SamProjects/HmOS_FFmpeg-Kit/sbom/{os.environ.get("GITHUB_SHA","local")}/{profile}',
    'creationInfo':{'created':__import__('datetime').datetime.fromtimestamp(PROJECT['sourceDateEpoch'],__import__('datetime').timezone.utc).isoformat().replace('+00:00','Z'), 'creators':['Tool: HmOS_FFmpeg-Kit']},
    'packages':[{'SPDXID':'SPDXRef-'+name,'name':name,'versionInfo':s['version'], 'downloadLocation':s['url'],
       'licenseConcluded':s['license'],'licenseDeclared':s['license'],'filesAnalyzed':False,
       'checksums':[{'algorithm':'SHA256','checksumValue':s['sha256']}]} for name,s in SOURCES.items() if profile != 'core' or name == 'ffmpeg']})
print('Staged HAR project:', har.parent)
