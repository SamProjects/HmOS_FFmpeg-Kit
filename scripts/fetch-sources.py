#!/usr/bin/env python3
from common import *
import argparse
import shutil

p = argparse.ArgumentParser()
p.add_argument('--verify-only', action='store_true')
args = p.parse_args()
WORK.mkdir(exist_ok=True)
for name, lock in SOURCES.items():
    source = WORK / 'src' / name
    evidence = WORK / 'integrity' / (name + '.json')
    if args.verify_only:
        if snapshot(source) != json.loads(evidence.read_text()):
            raise SystemExit('Upstream source changed: ' + name)
        continue
    archive = download(lock['url'], WORK / 'downloads' / lock['url'].split('/')[-1], lock['sha256'])
    if name == 'ffmpeg':
        sig = download(lock['url'] + '.asc', str(archive) + '.asc')
        home = WORK / 'gnupg'
        home.mkdir(exist_ok=True, mode=0o700)
        run(['gpg', '--batch', '--homedir', home, '--import', ROOT / 'config/ffmpeg-release.asc'])
        result = run(['gpg', '--batch', '--homedir', home, '--status-fd', '1', '--verify', sig, archive], capture_output=True, text=True)
        if '[GNUPG:] VALIDSIG ' + PROJECT['signingFingerprint'] + ' ' not in result.stdout:
            raise SystemExit('Unexpected signing key')
        (WORK / 'signature.txt').write_text(result.stdout + result.stderr)
    if source.exists():
        if snapshot(source) != json.loads(evidence.read_text()):
            raise SystemExit('Refusing to reuse modified source: ' + name)
        continue
    staging = WORK / 'extract' / name
    extract(archive, staging)
    children = list(staging.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise SystemExit('Expected a single source root: ' + name)
    source.parent.mkdir(exist_ok=True, parents=True)
    shutil.move(str(children[0]), str(source))
    write_json(evidence, snapshot(source))
print('Verified exact sources and pristine source trees')
