#!/usr/bin/env python3
from common import *
import re
import sys

PROFILE = sys.argv[1]
BUILD = WORK / 'build' / PROFILE
PREFIX = WORK / 'prefix' / PROFILE
SDK = Path(os.environ.get('OHOS_NATIVE', '.'))
READELF = SDK / 'llvm/bin/llvm-readelf'
SYSTEM = {'libc.so', 'libm.so', 'libdl.so', 'libpthread.so', 'librt.so', 'libace_napi.z.so', 'libc++_shared.so', 'libhilog_ndk.z.so'}


def inspect(files, report):
    available = {p.name for p in files}
    records = []
    for p in files:
        h = run([READELF, '-h', '-l', '-d', '--version-info', p], capture_output=True, text=True).stdout
        if 'AArch64' not in h or 'ELF64' not in h:
            raise ValueError('Wrong target: ' + str(p))
        if re.search(r'GLIBC_|libc\.so\.6|liblog\.so|TEXTREL', h):
            raise ValueError('Host/Android dependency or TEXTREL: ' + p.name)
        if re.search(r'\((?:RPATH|RUNPATH)\)', h):
            raise ValueError('Unexpected runtime search path: ' + p.name)
        needed = re.findall(r'\(NEEDED\).*?\[(.*?)\]', h)
        missing = set(needed) - available - SYSTEM
        if missing:
            raise ValueError(f'{p.name}: unresolved dependencies {missing}')
        soname = re.findall(r'\(SONAME\).*?\[(.*?)\]', h)
        if p.name.endswith('.so') and soname != [p.name]:
            raise ValueError('SONAME mismatch: ' + p.name)
        records.append({'file': p.name, 'sha256': digest(p), 'needed': needed, 'soname': soname, 'readelf': h})
    write_json(report, records)
    return records


def license_gate():
    config = (BUILD / 'ffmpeg/config.h').read_text()
    for name, value in [('GPL', 0), ('NONFREE', 0), ('VERSION3', 1)]:
        if not re.search(rf'^#define CONFIG_{name} {value}$', config, re.M):
            raise ValueError('License configuration mismatch: ' + name)
    if 'GNU Lesser General Public License' not in config:
        raise ValueError('Not an LGPL build')
    args = (BUILD / 'ffmpeg/configure-args.txt').read_text().splitlines()
    if set(args) & {'--enable-gpl', '--enable-nonfree'}:
        raise ValueError('Prohibited configuration')
    approved = {'LGPL-3.0-or-later','LGPL-2.0-or-later','BSD-3-Clause','BSD-2-Clause','Apache-2.0','Zlib'}
    for name, lock in SOURCES.items():
        if lock['license'] not in approved:
            raise ValueError('Unapproved dependency: ' + name)
    write_json(BUILD / 'license-gate.json', {'passed': True, 'license': 'LGPL-3.0-or-later', 'profile': PROFILE, 'sources': SOURCES})


if __name__ == '__main__':
    license_gate()
    libs = list((PREFIX / 'lib').glob('lib*-*.so'))
    if len(libs) != 7:
        raise ValueError('Expected seven FFmpeg shared libraries')
    files = libs + [PREFIX / 'bin' / p for p in ['ffmpeg','ffprobe']]
    inspect(files, BUILD / 'elf.json')
