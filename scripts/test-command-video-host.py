#!/usr/bin/env python3
"""Exercise the actual C++ in-process adapter, not the system ffmpeg CLI."""
import argparse, importlib.util, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--executable',type=Path,required=True);p.add_argument('--original',type=Path,required=True);p.add_argument('--compatible',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('matrix',ROOT/'scripts/generate-command-test-cases.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cases=m.cases()
def resolve(value):
 return value.replace('{ORIGINAL}',str(a.original.resolve())).replace('{VIDEO}',str(a.compatible.resolve())).replace('{DIR}',str(a.output.resolve()))
lines=[]
decode_count=0
for c in cases:
 args=[resolve(x) for x in c['args']]
 lines.append(f"{c['id']} {c['timeout']} {c['cancelMs']} {int(c['repeatCancel'])} {int(c['concurrent'])} {len(args)} "+' '.join(json.dumps(x,ensure_ascii=False) for x in args)+' '+json.dumps(resolve(c['output']) if c['output'] else '',ensure_ascii=False))
 if c['verifyDecode']:
  verify=['-v','error','-xerror','-i',resolve(c['output']),'-f','null',resolve('{DIR}/verify.null')]
  lines.append(f"{c['id']}v 45 -1 0 0 {len(verify)} "+' '.join(json.dumps(x,ensure_ascii=False) for x in verify)+' ""')
  decode_count+=1
process=subprocess.run([str(a.executable.resolve())],input='\n'.join(lines)+'\n',capture_output=True,text=True,timeout=240)
(a.output/'driver-stdout.log').write_text(process.stdout)
(a.output/'driver-stderr.log').write_text(process.stderr)
if 'runtime error:' in process.stderr or 'ERROR: AddressSanitizer' in process.stderr or 'ERROR: LeakSanitizer' in process.stderr:
 raise RuntimeError(process.stderr[-6000:])
if process.returncode: raise RuntimeError(f'Adapter exited {process.returncode}: {process.stderr[-3000:]}')
records=[json.loads(line.removeprefix('HMOS_RESULT ')) for line in process.stdout.splitlines() if line.startswith('HMOS_RESULT ')]
assert len(records)==len(cases)+decode_count,(len(records),len(cases)+decode_count)
by_id={r['id']:r for r in records}
report=[]
for c in cases:
 r=by_id[c['id']]
 state='passed';error='';v=r['result']
 try:
  assert c['id']==r['id']
  if c['expected']=='reject': assert v is None and 'disabled in this test API' in r['error']
  else:
   assert not r['error'],r['error']
   assert v is not None
   (a.output/f"test-{c['id']}.log").write_text(v['logs'])
   assert len(v['logs'].encode())<=256*1024
   if c['expected']=='cancel':
    assert v['cancelled'] and not v['timedOut'] and v['exitCode']!=0,v
    assert r['elapsedMs']-c['cancelMs']<5000
   elif c['expected']=='timeout':
    assert v['timedOut'] and not v['cancelled'] and v['exitCode']!=0
    assert r['elapsedMs']<6000
   elif c['expected']=='error': assert v['exitCode']!=0 and v['logs'] and not v['cancelled'] and not v['timedOut']
   elif c['expected']=='capability' and v['exitCode']!=0:
    assert 'hardware accelerated AV1' in v['logs'] or 'Function not implemented' in v['logs'] or 'Decoder (codec av1) not found' in v['logs']
    state='unsupported'
   else:
    assert v['exitCode']==0 and not v['cancelled'] and not v['timedOut'],v['logs'][-1500:]
    if c['args']==['-version']: assert '9.0.2' in v['logs']
    if c['args']==['-L']: assert 'Lesser General Public License' in v['logs'] and 'version 3' in v['logs']
    if c['requireLive']: assert r['liveReads']>1 and r['liveUpdates']>1 and 'frame=' in v['logs']
    if c['requireProgress']: assert r['progressUs']>0
    if c['requireTruncated']: assert v['logsTruncated'] and len(v['logs'])>100000
    if c['concurrent']: assert r['busyRejected']
    if c['output']:
     output=Path(resolve(c['output']));assert output.stat().st_size>0
     assert not r['probeError'],r['probeError']
     info=r['media']; assert info is not None
     for kind in ['video','audio']:
      expected=c[kind+'Codec']
      if not expected:continue
      stream=next(s for s in info['streams'] if s['type']==kind)
      assert stream['codec']==expected,stream
      if kind=='video' and c['width']:assert stream['width']==c['width'] and stream['height']==c['height'],stream
      if kind=='audio' and c['sampleRate']:assert stream['sampleRate']==c['sampleRate']
      if kind=='audio' and c['channels']:assert stream['channels']==c['channels']
     duration=info['durationUs']/1000000
     if c['minDuration']:assert duration>=c['minDuration'],duration
     if c['maxDuration']:assert duration<=c['maxDuration'],duration
     if c['label']=='视频去音轨':assert not any(s['type']=='audio' for s in info['streams'])
     if c['verifyDecode']:
      decoded=by_id[c['id']+'v']
      assert not decoded['error'] and decoded['result']['exitCode']==0,decoded['error'] or decoded['result']['logs'][-2000:]
 except Exception as e:state='failed';error=str(e)
 entry={k:v for k,v in r.items() if k not in ['result']}
 entry.update(label=c['label'],state=state,detail=error,logBytes=len(v['logs'].encode()) if v else 0)
 if v:entry.update({k:v[k] for k in ['exitCode','cancelled','timedOut','logsTruncated']})
 report.append(entry)
 print(c['id'],state,c['label'],error[:300],flush=True)
summary={'scope':'Linux in-process FFmpeg 9.0.2 adapter; selected codecs match test cases; not HarmonyOS device execution',
 'harmonyDeviceTested':False,'commandCalls':len(records),'outputDecodeCalls':decode_count,'outputMetadataMethod':'same native engine.probe with pinned FFmpeg 9.0.2','cases':report,'passed':sum(x['state']=='passed' for x in report),'failed':sum(x['state']=='failed' for x in report),'unsupported':sum(x['state']=='unsupported' for x in report)}
(a.output/'report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='cases'},ensure_ascii=False))
raise SystemExit(bool(summary['failed']))
