#!/usr/bin/env python3
from common import *
import shutil
import sys

profile = sys.argv[1]
package = DIST / profile_key(profile)
assets = DIST / 'assets'
assets.mkdir(exist_ok=True)
base = f'hmos-ffmpeg-{PROJECT["version"]}-{profile}-{ABI}'
har = package / (base + '.har')
if not har.exists() or not json.loads((package / 'consumer-validation.json').read_text())['consumerHapBuilt']:
    raise SystemExit('Missing validated HAR')
shutil.copy2(har, assets / har.name)
# Native headers/libs, CLI, symbols, license/SBOM/build evidence accompany the HAR.
with tarfile.open(assets / (base + '-sdk.tar.gz'), 'w:gz') as t:
    for p in sorted(package.iterdir()):
        if p != har: t.add(p, arcname=base + '/' + p.name)
with tarfile.open(assets / (base + '-sources.tar.gz'), 'w:gz') as t:
    for name, lock in SOURCES.items():
        if profile == 'core' and name != 'ffmpeg': continue
        archive = WORK / 'downloads' / lock['url'].split('/')[-1]
        t.add(archive, arcname='sources/' + archive.name)
        sig = Path(str(archive) + '.asc')
        if sig.exists(): t.add(sig, arcname='sources/' + sig.name)
    for dirname in ['scripts','config','native','harmony','docs','examples','tests','.github']:
        t.add(ROOT / dirname, arcname='recipe/' + dirname)
    for filename in ['LICENSE', 'README.md']:
        t.add(ROOT / filename, arcname='recipe/' + filename)
    t.add(WORK / 'signature.txt', arcname='evidence/signature.txt')
    t.add(WORK / 'integrity', arcname='evidence/integrity')
shutil.copy2(package / 'manifest.json', assets / (base + '-manifest.json'))
for p in assets.glob(base + '*'):
    with (assets / (p.name + '.sha256')).open('w') as f:
        f.write(digest(p) + '  ' + p.name + '\n')
