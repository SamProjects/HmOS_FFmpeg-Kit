#!/usr/bin/env python3
"""Compress a test HAP and produce verified Windows-friendly volumes below 20 MB."""
import argparse
import hashlib
import io
from pathlib import Path
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('hap',type=Path);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
archive=a.output/'ffmpeg-video-test.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 z.write(a.hap,a.hap.name)
readme=a.hap.parent/'README.zh-CN.md'
if readme.exists():
 with zipfile.ZipFile(archive,'a',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:z.write(readme,readme.name)
parts=[]
with archive.open('rb') as stream:
 while data:=stream.read(19_000_000):
  dest=a.output/f'{archive.name}.{len(parts)+1:03d}';dest.write_bytes(data);parts.append(dest)
joined=b''.join(x.read_bytes() for x in parts)
assert joined==archive.read_bytes()
with zipfile.ZipFile(io.BytesIO(joined)) as z:
 assert z.testzip() is None
 assert hashlib.sha256(z.read(a.hap.name)).digest()==hashlib.sha256(a.hap.read_bytes()).digest()
expected=hashlib.sha256(joined).hexdigest()
script='\r\n'.join(['@echo off','setlocal','cd /d "%~dp0"',
 'copy /b '+'+'.join('"'+x.name+'"' for x in parts)+' "'+archive.name+'"','if errorlevel 1 goto fail',
 'powershell -NoProfile -Command "if ((Get-FileHash -Algorithm SHA256 -LiteralPath '+archive.name+").Hash.ToLower() -ne '"+expected+"') { Write-Error 'Archive checksum mismatch'; exit 1 }; Expand-Archive -LiteralPath "+archive.name+' -DestinationPath ffmpeg-video-test -Force"',
 'if errorlevel 1 goto fail','echo Done. HAP is in the ffmpeg-video-test folder.','pause','exit /b 0',
 ':fail','echo Failed. Download all parts into the same folder and try again.','pause','exit /b 1',''])
(a.output/'merge-and-extract.cmd').write_bytes(script.encode('ascii'))
(a.output/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.name+'\n' for x in [a.hap,archive,*parts]))
for x in parts:print(x.name,x.stat().st_size)
print('Reassembled archive CRC, archive hash and original HAP hash verified.')
