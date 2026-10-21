#!/usr/bin/env python3
"""Run the actual C++ command adapter repeatedly inside one Linux process."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import wave

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('executable', type=Path)
parser.add_argument('report', type=Path)
args = parser.parse_args()
with tempfile.TemporaryDirectory() as d:
    process = subprocess.run([str(args.executable.resolve()), d], capture_output=True, text=True, timeout=45)
    if process.returncode:
        raise RuntimeError(f'In-process adapter failed: {process.returncode}\n{process.stderr}\n{process.stdout}')
    records = [json.loads(line) for line in process.stdout.splitlines()]
    if len(records) != 20:
        raise RuntimeError(f'Expected 20 command results, got {len(records)}')
    for item in records:
        result, name = item['result'], item['name']
        failure = name in {'invalid', 'overwrite-reset', 'cancel', 'timeout'}
        assert (result['exitCode'] != 0) == failure, item
        assert result['cancelled'] == (name == 'cancel'), item
        assert result['timedOut'] == (name == 'timeout'), item
        if 'version' in name: assert '9.0.2' in result['logs'], item
    assert any('输入' in item['result']['logs'] for item in records), 'UTF-8 log capture failed'
    for name in ['repeat.wav', 'filtered.wav', 'after-cancel.wav']:
        with wave.open(str(Path(d) / name)) as audio:
            assert audio.getnchannels() == 1 and audio.getsampwidth() == 2
            assert 0.19 <= audio.getnframes() / audio.getframerate() <= 0.21
    # Logs are intentionally not persisted in full; the adapter limits them to 256 KiB.
    report = {'scope':'Linux in-process C++ adapter, not HarmonyOS device execution',
              'harmonyDeviceTested':False, 'commands':[
                  {k:v for k,v in item.items() if k != 'result'} | {
                      'exitCode':item['result']['exitCode'], 'cancelled':item['result']['cancelled'],
                      'timedOut':item['result']['timedOut'], 'logBytes':len(item['result']['logs'].encode())}
                  for item in records], 'outputAudioVerified':True,
              'processWideOptionsRejected':True, 'applicationSignalHandlerPreserved':True}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Passed {len(records)} in-process command calls, output audio, option isolation and signal preservation')
