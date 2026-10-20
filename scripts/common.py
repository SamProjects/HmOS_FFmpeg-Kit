"""Build utilities. No operation writes to the upstream source tree."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
DIST = ROOT / 'dist'
PROJECT = json.loads((ROOT / 'config/project.json').read_text())
SOURCES = json.loads((ROOT / 'config/sources.lock.json').read_text())
ABI = os.environ.get('HMOS_ABI', PROJECT['abi'])
if ABI not in PROJECT['abis']:
    raise ValueError('Unsupported HarmonyOS application ABI: ' + ABI)
TRIPLE = {'arm64-v8a':'aarch64-linux-ohos', 'x86_64':'x86_64-linux-ohos'}[ABI]


def profile_key(profile, abi=None):
    abi = abi or ABI
    return profile if abi == 'arm64-v8a' else profile + '-' + abi


def run(args, **kw):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kw)


def digest(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def download(url, path, expected=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and expected and digest(path) == expected:
        return path
    if not url.startswith('https://'):
        raise ValueError('HTTPS required')
    temp = path.with_suffix(path.suffix + '.part')
    try:
        for attempt in range(4):
            try:
                print(f'Download {url} (attempt {attempt + 1})', flush=True)
                request = urllib.request.Request(url, headers={'User-Agent':'HmOS-FFmpeg-Kit/0.1'})
                with urllib.request.urlopen(request, timeout=120) as r, temp.open('wb') as f:
                    import shutil
                    shutil.copyfileobj(r, f)
                break
            except (OSError, TimeoutError):
                if attempt == 3: raise
                time.sleep(2 ** attempt)
        if expected and digest(temp) != expected:
            raise ValueError(f'Checksum mismatch: {path.name}')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def extract(archive, dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as t:
        # Python 3.12+ data filter rejects escaping links/paths and devices.
        t.extractall(dest, filter='data')


def snapshot(directory):
    directory = Path(directory)
    result = {}
    for p in sorted(directory.rglob('*')):
        rel = p.relative_to(directory).as_posix()
        if p.is_symlink():
            result[rel] = {'link': os.readlink(p)}
        elif p.is_file():
            result[rel] = {'sha256': digest(p), 'mode': p.stat().st_mode & 0o777}
    return result


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
