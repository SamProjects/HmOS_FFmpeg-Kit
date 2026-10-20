#!/usr/bin/env python3
from common import *
import shutil
import sys

profile = sys.argv[1]
directory = WORK / 'har' / profile
run(['ohpm', 'install', '--all'], cwd=directory)
run(['hvigorw', '--mode', 'module', '-p', 'product=default', '-p', 'module=ffmpeg@default',
     '-p', 'buildMode=release', 'assembleHar', '--no-daemon'], cwd=directory)
candidates = list((directory / 'ffmpeg/build/default/outputs').rglob('*.har'))
if len(candidates) != 1:
    raise SystemExit(f'Expected one HAR, got {candidates}')
output = DIST / profile / f'hmos-ffmpeg-{PROJECT["version"]}-{profile}-arm64-v8a.har'
shutil.copy2(candidates[0], output)
with tarfile.open(output) as t:
    names = t.getnames()
    for name in ['libhmosffmpeg.so'] + [x.name for x in (DIST / profile / 'runtime/arm64-v8a').glob('*.so')]:
        if not any(n.endswith('/libs/arm64-v8a/' + name) or n == 'libs/arm64-v8a/' + name for n in names):
            raise SystemExit('HAR missing library: ' + name)
    if not any(n.endswith('/Index.ets') or n == 'Index.ets' for n in names):
        raise SystemExit('HAR missing ArkTS entry')
write_json(DIST / profile / 'har-validation.json', {'harSha256':digest(output),'structure':True})
# Validate a separate project consuming the artifact, not a source-module dependency.
consumer = WORK / 'consumer' / profile
shutil.copytree(ROOT / 'examples/consumer', consumer)
(consumer / 'entry/libs').mkdir()
shutil.copy2(output, consumer / 'entry/libs/hmos-ffmpeg.har')
run(['ohpm', 'install', '--all'], cwd=consumer)
run(['hvigorw', '--mode', 'module', '-p', 'product=default', '-p', 'module=entry@default',
     '-p', 'buildMode=debug', 'assembleHap', '--no-daemon'], cwd=consumer)
haps = list((consumer / 'entry/build/default/outputs').rglob('*.hap'))
if not haps:
    raise SystemExit('Consumer HAP not built')
import zipfile
with zipfile.ZipFile(haps[0]) as z:
    files = z.namelist()
    for lib in (DIST / profile / 'runtime/arm64-v8a').glob('*.so'):
        if 'libs/arm64-v8a/' + lib.name not in files:
            raise SystemExit('Consumer HAP missing ' + lib.name)
write_json(DIST / profile / 'consumer-validation.json', {'harSha256':digest(output),'consumerHapBuilt':True,'deviceRun':False})
