#!/usr/bin/env python3
"""Bound temporary disk use after one ABI's validated assets are archived."""
from common import *
import shutil
import sys

profile = sys.argv[1]
if profile not in {'core', 'extended'}:
    raise ValueError('Unknown profile')
key = profile_key(profile)
base = f'hmos-ffmpeg-{PROJECT["version"]}-{profile}-{ABI}'
if HAR_ONLY:
    manifest = json.loads((DIST / key / 'manifest.json').read_text())
    libraries = {p.name: digest(p) for p in (DIST / key / 'runtime' / ABI).glob('*.so')}
    if len(libraries) != 9 or libraries != manifest['libraries'] or not all(
            manifest['validation'][g] for g in ['sourceIntegrity', 'licenseConfig', 'elfClosure']):
        raise ValueError('Refusing cleanup before runtime validation')
else:
    for suffix in ['.har', '-sdk.tar.gz', '-sources.tar.gz', '-manifest.json']:
        asset = DIST / 'assets' / (base + suffix)
        if not asset.is_file() or (asset.parent / (asset.name + '.sha256')).read_text().split() != [digest(asset), asset.name]:
            raise ValueError('Refusing cleanup before validated asset exists: ' + asset.name)
for category in ['build', 'prefix', 'har', 'consumer']:
    parent = (WORK / category).resolve()
    target = parent / key
    if target.resolve().parent != parent or not parent.is_relative_to(WORK.resolve()):
        raise ValueError('Cleanup outside temporary workspace')
    if target.exists(): shutil.rmtree(target)
# Keep runtime and license inputs for the universal HAR assembler.
package = (DIST / key).resolve()
if package.parent != DIST.resolve(): raise ValueError('Unsafe package path')
for target in package.iterdir():
    if target.name in ({'runtime', 'licenses', 'manifest.json'} if HAR_ONLY else {'runtime', 'licenses'}): continue
    if target.is_symlink() or target.is_file(): target.unlink()
    else: shutil.rmtree(target)
print('Cleaned temporary build products; universal HAR inputs retained:', key)
