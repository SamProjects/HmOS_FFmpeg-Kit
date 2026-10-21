#!/usr/bin/env python3
from common import *
from hap_validation import validate_hap
import shutil
import sys

profile = sys.argv[1]
universal = '--universal' in sys.argv[2:]
abis = PROJECT['abis'] if universal else [ABI]
key = profile + '-all' if universal else profile_key(profile)
directory = WORK / 'har' / key
package = DIST / key
package.mkdir(parents=True, exist_ok=True)
if universal:
    shutil.copytree(ROOT / 'harmony', directory)
    module = directory / 'ffmpeg'
    for abi in abis:
        shutil.copytree(DIST / profile_key(profile, abi) / 'runtime' / abi, module / 'libs' / abi)
    shutil.copytree(DIST / profile / 'licenses', module / 'licenses')
    shutil.copytree(DIST / profile / 'licenses', module / 'src/main/resources/rawfile/hmos_ffmpeg_licenses')
    shutil.copy2(ROOT / 'docs/INTEGRATION.zh-CN.md', module / 'README.md')
# These are prebuilt libraries. Setting externalNativeOptions on a HAR
# asks Hvigor to run CMake; all required ABI directories are already staged.
run(['ohpm', 'install', '--all'], cwd=directory)
run(['hvigorw', '--mode', 'module', '-p', 'product=default', '-p', 'module=ffmpeg@default',
     '-p', 'buildMode=release', 'assembleHar', '--no-daemon'], cwd=directory)
candidates = list((directory / 'ffmpeg/build/default/outputs').rglob('*.har'))
if len(candidates) != 1:
    raise SystemExit(f'Expected one HAR, got {candidates}')
base = f'hmos-ffmpeg-{PROJECT["version"]}-{profile}-' + ('all' if universal else ABI) + HAR_SUFFIX
output = package / (base + '.har')
shutil.copy2(candidates[0], output)
expected = {abi: {p.name:digest(p) for p in (DIST / profile_key(profile, abi) / 'runtime' / abi).glob('*.so')}
            for abi in abis}
with tarfile.open(output) as t:
    members = {m.name.removeprefix('./').removeprefix('package/'):m for m in t.getmembers()}
    for abi, libraries in expected.items():
        if len(libraries) != RUNTIME_LIBRARY_COUNT:
            raise ValueError('Expected FFmpeg, bridge and C++ runtime closure: ' + abi)
        for name, sha in libraries.items():
            member = members.get(f'libs/{abi}/{name}')
            if not member or hashlib.sha256(t.extractfile(member).read()).hexdigest() != sha:
                raise ValueError('HAR missing or altered library: ' + abi + '/' + name)
    if 'Index.ets' not in members:
        raise ValueError('HAR missing ArkTS entry')
write_json(package / 'har-validation.json', {'harSha256':digest(output),'abis':abis,'structure':True})

# Consume the real HAR in independent projects. Explicit packaging exclusions
# are essential: abiFilters alone controls compilation, not every prebuilt .so.
selections = [[abi] for abi in abis] + ([abis] if universal else [])
reports = []
for selected in selections:
    selection = '-'.join(selected)
    consumer = WORK / 'consumer' / key / selection
    shutil.copytree(ROOT / 'examples/consumer', consumer)
    (consumer / 'entry/libs').mkdir()
    shutil.copy2(output, consumer / 'entry/libs/hmos-ffmpeg.har')
    build_profile = json.loads((consumer / 'entry/build-profile.json5').read_text())
    build_profile['buildOption'] = {
        'externalNativeOptions':{'abiFilters':selected},
        'nativeLib':{'debugSymbol':{'strip':False}, 'filter':{'excludes':[
            '**/' + abi + '/**' for abi in PROJECT['abis'] if abi not in selected]}}}
    write_json(consumer / 'entry/build-profile.json5', build_profile)
    run(['ohpm', 'install', '--all'], cwd=consumer)
    run(['hvigorw', '--mode', 'module', '-p', 'product=default', '-p', 'module=entry@default',
         '-p', 'buildMode=debug', 'assembleHap', '--no-daemon'], cwd=consumer)
    haps = list((consumer / 'entry/build/default/outputs').rglob('*.hap'))
    if len(haps) != 1:
        raise ValueError('Expected one consumer HAP')
    reports.append(validate_hap(haps[0], expected, selected))
report = {'harSha256':digest(output), 'consumerHapBuilt':True, 'deviceRun':False,
          'cloudDistributionTested':False, 'selections':reports}
write_json(package / 'consumer-validation.json', report)
if universal:
    assets = DIST / 'assets'
    assets.mkdir(exist_ok=True)
    shutil.copy2(output, assets / output.name)
    if not HAR_ONLY:
        write_json(assets / (base + '-consumer-validation.json'), report)
        for name in [output.name, base + '-consumer-validation.json']:
            (assets / (name + '.sha256')).write_text(digest(assets / name) + '  ' + name + '\n')
