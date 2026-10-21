#!/usr/bin/env python3
"""Build LGPLv3-compatible external codec libraries in private source copies."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from common import ROOT, WORK, SOURCES

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('build',type=Path);p.add_argument('prefix',type=Path)
p.add_argument('--only',nargs='+');p.add_argument('--keep-going',action='store_true')
p.add_argument('--resume',action='store_true',help='Reuse matching stamps in this local build tree')
a=p.parse_args();build=a.build.resolve();prefix=a.prefix.resolve()
abi=os.environ.get('HMOS_ABI','arm64-v8a');native=os.environ.get('HMOS_CODEC_HOST')=='1'
arch='aarch64' if abi=='arm64-v8a' else 'x86_64'
cc=os.environ['CC'];cxx=os.environ['CXX'];ar=os.environ['AR'];ranlib=os.environ['RANLIB']
jobs=os.environ.get('JOBS','3')
config=json.loads((ROOT/'config/codec-dependencies.json').read_text())
names=a.only or list(config)
for path in [build,build/'sources',prefix/'lib/pkgconfig',prefix/'include']:path.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();env['GIT_CEILING_DIRECTORIES']=str(build/'sources');env['CFLAGS']='-O2 -fPIC';env['CXXFLAGS']='-O2 -fPIC';env['LDFLAGS']=''
env['PKG_CONFIG_PATH']='';env['PKG_CONFIG_LIBDIR']=str(prefix/'lib/pkgconfig');env.pop('PKG_CONFIG_SYSROOT_DIR',None)
cmake=shutil.which('cmake');meson=shutil.which('meson')
if not cmake or not meson:raise SystemExit('cmake, ninja, meson and nasm must be installed on the build host')
cmake_common=['-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=OFF',
 '-DCMAKE_POSITION_INDEPENDENT_CODE=ON','-DCMAKE_INSTALL_LIBDIR=lib',
 '-DCMAKE_INSTALL_PREFIX='+str(prefix),'-DCMAKE_PREFIX_PATH='+str(prefix),
 '-DCMAKE_C_COMPILER='+cc,'-DCMAKE_CXX_COMPILER='+cxx,'-DCMAKE_AR='+ar,'-DCMAKE_RANLIB='+ranlib,
 '-DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF','-DCMAKE_DISABLE_FIND_PACKAGE_Git=OFF']
if not native:cmake_common+=['-DCMAKE_SYSTEM_NAME=Linux','-DCMAKE_SYSTEM_PROCESSOR='+arch]
cross=build/'meson-cross.ini'
cross.write_text("[binaries]\nc = "+repr(cc)+"\ncpp = "+repr(cxx)+"\nar = "+repr(ar)+"\nstrip = "+repr(env.get('STRIP','strip'))+"\npkg-config = 'pkg-config'\n[properties]\nneeds_exe_wrapper = true\n[host_machine]\nsystem = 'linux'\ncpu_family = '"+arch+"'\ncpu = '"+arch+"'\nendian = 'little'\n")
results=[]
for name in names:
 source=build/'sources'/name;dest=build/name;dest.mkdir(exist_ok=True)
 stamp=build/(name+'-complete.json');identity={'abi':'host' if native else abi,'sourceSha256':SOURCES[name]['sha256'],'cc':cc}
 if stamp.exists() and json.loads(stamp.read_text()).get('identity',{}).get('sourceSha256') != identity['sourceSha256']:
  shutil.rmtree(source,ignore_errors=True);shutil.rmtree(dest);dest.mkdir();stamp.unlink()
 if a.resume and stamp.exists() and json.loads(stamp.read_text()).get('identity')==identity:
  results.append(json.loads(stamp.read_text()));print('reuse',name,flush=True);continue
 if not source.exists():shutil.copytree(WORK/'src'/name,source,symlinks=True)
 log_path=build/(name+'.log');start=time.monotonic()
 print('building',name,abi,'host' if native else 'OHOS',flush=True)
 with log_path.open('w') as log:
  def run(args,cwd=dest):
   log.write('+ '+repr(list(map(str,args)))+'\n');log.flush()
   subprocess.run(list(map(str,args)),cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
  def cmake_build(options=(),target=None,component=None):
   run([cmake,'-S',source,'-B',dest,*cmake_common,*options])
   run([cmake,'--build',dest,'--parallel',jobs,*(['--target',target] if target else [])])
   run([cmake,'--install',dest,*(['--component',component] if component else [])])
  def meson_build(options=()):
   run([meson,'setup',dest,source,'--prefix',prefix,'--libdir','lib','--default-library=static',
        '--buildtype=release','--wrap-mode=nodownload','-Db_lto=false','-Db_staticpic=true',
        *([] if native else ['--cross-file',cross]),*options])
   run([meson,'compile','-C',dest,'-j',jobs]);run([meson,'install','-C',dest])
  def autotools(options=()):
   run([source/'configure','--prefix='+str(prefix),'--disable-shared','--enable-static',
        *([] if native else ['--host='+('aarch64-linux' if arch=='aarch64' else 'x86_64-linux')]),*options])
   run(['make','-j'+jobs]);run(['make','install'])
  try:
   if name=='aom':cmake_build(['-DENABLE_APPS=OFF','-DENABLE_TESTS=OFF','-DENABLE_EXAMPLES=OFF','-DENABLE_TOOLS=OFF','-DENABLE_DOCS=OFF'])
   elif name=='dav1d':meson_build(['-Denable_tools=false','-Denable_tests=false','-Denable_examples=false','-Denable_docs=false'])
   elif name=='svtav1':cmake_build(['-DBUILD_APPS=OFF','-DBUILD_TESTING=OFF','-DSVT_AV1_LTO=OFF','-DNATIVE=OFF','-DEXCLUDE_HASH=ON'])
   elif name=='openh264':meson_build(['-Dtests=disabled'])
   elif name=='ogg':cmake_build(['-DBUILD_TESTING=OFF'])
   elif name=='vorbis':cmake_build(['-DBUILD_TESTING=OFF'])
   elif name=='openjpeg':cmake_build(['-DBUILD_CODEC=OFF','-DBUILD_TESTING=OFF'])
   elif name=='kvazaar':cmake_build(['-DBUILD_TESTS=OFF','-DBUILD_KVAZAAR_BINARY=OFF','-DUSE_CRYPTO=OFF','-DGIT_SUBMODULE=OFF'])
   elif name=='speex':autotools(['--disable-binaries','--disable-examples','--disable-oggtest'])
   elif name=='theora':autotools(['--disable-examples','--disable-spec','--disable-doc','--disable-oggtest','--disable-vorbistest'])
   elif name=='twolame':autotools(['--disable-sndfile','--disable-doxygen'])
   elif name=='shine':
    # This release assumes its symbol list is in cwd; use the private source copy.
    run([source/'configure','--prefix='+str(prefix),'--disable-shared','--enable-static',
         *([] if native else ['--host='+('aarch64-linux' if arch=='aarch64' else 'x86_64-linux')])],source)
    run(['make','-j'+jobs,'libshine.la'],source)
    run(['make','install-libLTLIBRARIES','install-libshine_laHEADERS','install-pkgconfigDATA'],source)
   elif name in ['opencore-amr','vo-amrwbenc']:autotools(['--disable-examples'])
   elif name=='ilbc':cmake_build()
   elif name=='lc3':meson_build(['-Dtools=false','-Dpython=false'])
   elif name=='gsm':
    run(['make','-j'+jobs,'lib/libgsm.a','CC='+cc,'AR='+ar,'RANLIB='+ranlib,
         'CCFLAGS=-c -O2 -fPIC -DNeedFunctionPrototypes=1 -Wall -Wno-comment'],source)
    shutil.copy2(source/'lib/libgsm.a',prefix/'lib/libgsm.a');shutil.copy2(source/'inc/gsm.h',prefix/'include/gsm.h')
   elif name=='codec2':
    # Upstream builds its codebook generator natively using ExternalProject.
    saved_cc, saved_cxx = env.get('CC'), env.get('CXX')
    env['CC']='/usr/bin/cc';env['CXX']='/usr/bin/c++'
    try:cmake_build(['-DUNITTEST=OFF','-DLPCNET=OFF',
      '-DCMAKE_C_FLAGS=-O2 -fPIC -Dlpc_to_lsp=codec2_lpc_to_lsp -Dlsp_to_lpc=codec2_lsp_to_lpc'])
    finally:env['CC']=saved_cc;env['CXX']=saved_cxx
   elif name=='oapv':
    # Older releases install below lib/oapv; discard an obsolete flat archive.
    (prefix/'lib/liboapv.a').unlink(missing_ok=True)
    cmake_build(['-DCMAKE_C_FLAGS=-O2 -fPIC -Dsad_16b_neon_8x2n=oapv_sad_16b_neon_8x2n','-DOAPV_BUILD_APPS=OFF','-DOAPV_BUILD_SHARED_LIB=OFF','-DOAPV_BUILD_STATIC_LIB=ON'])
   elif name=='uavs3d':cmake_build(['-DCOMPILE_10BIT=ON'])
   elif name=='jxl':
    for sub in ['brotli','highway','skcms']:
     shutil.copytree(WORK/'src'/('jxl-'+sub),source/'third_party'/sub,dirs_exist_ok=True,symlinks=True)
    cmake_build(['-DBUILD_TESTING=OFF','-DJPEGXL_ENABLE_TOOLS=OFF','-DJPEGXL_ENABLE_DEVTOOLS=OFF',
     '-DJPEGXL_ENABLE_DOXYGEN=OFF','-DJPEGXL_ENABLE_MANPAGES=OFF','-DJPEGXL_ENABLE_BENCHMARK=OFF',
     '-DJPEGXL_ENABLE_EXAMPLES=OFF','-DJPEGXL_ENABLE_JNI=OFF','-DJPEGXL_ENABLE_SJPEG=OFF',
     '-DJPEGXL_ENABLE_OPENEXR=OFF','-DJPEGXL_ENABLE_SKCMS=ON','-DJPEGXL_ENABLE_VIEWERS=OFF',
     '-DJPEGXL_ENABLE_PLUGINS=OFF','-DJPEGXL_ENABLE_LTO=OFF'])
   elif name=='vvenc':cmake_build(['-DVVENC_LIBRARY_ONLY=ON','-DVVENC_ENABLE_LINK_TIME_OPT=OFF','-DVVENC_ENABLE_WERROR=OFF','-DVVENC_ENABLE_THIRDPARTY_JSON=OFF'])
   elif name in ['xeve','xevd']:
    run([cmake,'-S',source,'-B',dest,*cmake_common,'-DSET_PROF=MAIN'])
    run([cmake,'--build',dest,'--parallel',jobs,'--target',name])
    # Upstream's Development install also expects an unwanted shared target.
    # Install only these unmodified static build outputs and public headers.
    archives=list(dest.rglob('lib'+name+'.a'))
    if len(archives)!=1:raise ValueError('Ambiguous static '+name+' archive')
    shutil.copy2(archives[0],prefix/'lib'/archives[0].name)
    includes=prefix/'include'/name;includes.mkdir(exist_ok=True)
    shutil.copy2(source/'inc'/(name+'.h'),includes)
    shutil.copy2(dest/(name+'_exports.h'),includes)
    shutil.copy2(dest/(name+'.pc'),prefix/'lib/pkgconfig')
   else:raise ValueError('No audited build recipe: '+name)
   # Build/install metadata is generated output; normalize Linux C++ runtime naming for OHOS.
   for pc in (prefix/'lib/pkgconfig').glob('*.pc'):
    text=pc.read_text()
    # OpenJPEG 2.5.4 prefixes CMake's '-lpthread' with a second '-l'.
    updated=text.replace('-l-lpthread','-lpthread')
    if not native:updated=updated.replace('-lstdc++','-lc++')
    if updated!=text:pc.write_text(updated)
   record={'name':name,'identity':identity,'seconds':round(time.monotonic()-start,2),'success':True}
   stamp.write_text(json.dumps(record,indent=2)+'\n');results.append(record);print('built',name,record['seconds'],'s',flush=True)
  except Exception as e:
   record={'name':name,'identity':identity,'seconds':round(time.monotonic()-start,2),'success':False,'error':str(e),'log':str(log_path)}
   results.append(record);print('FAILED',name,log_path,flush=True);print(log_path.read_text(errors='replace')[-3500:],flush=True)
   if not a.keep_going:raise
(build/'results.json').write_text(json.dumps(results,indent=2)+'\n')
if any(not r['success'] for r in results):raise SystemExit(1)
