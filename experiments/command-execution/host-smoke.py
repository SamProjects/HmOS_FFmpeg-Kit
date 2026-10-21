#!/usr/bin/env python3
"""Host-only CLI smoke test. This does not test a HarmonyOS HAP or HAR."""
import argparse
import json
from pathlib import Path
import platform
import signal
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', required=True, type=Path)
    parser.add_argument('--ffprobe', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    ffmpeg, ffprobe = str(args.ffmpeg.resolve()), str(args.ffprobe.resolve())
    checks = []

    def run(argv, success=True):
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        if (result.returncode == 0) != success:
            raise RuntimeError(f'Unexpected exit {result.returncode}: {argv}\n{result.stderr}')
        return result

    version = run([ffmpeg, '-version']).stdout.splitlines()[0]
    if not version.startswith('ffmpeg version 9.0.2'):
        raise RuntimeError('This experiment requires the project-pinned FFmpeg 9.0.2')
    checks.append({'name':'pinned-version', 'passed':True, 'version':version})
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        # An argv element is a filename, even when it contains shell punctuation.
        source = root / 'input ; not a shell command.wav'
        run([ffmpeg, '-nostdin', '-hide_banner', '-f', 'lavfi', '-i',
             'sine=frequency=440:sample_rate=48000', '-t', '0.25',
             '-c:a', 'pcm_s16le', str(source)])
        checks.append({'name':'command-parser-and-filename-with-spaces', 'passed':True})
        output = root / 'copy.wav'
        converted = run([ffmpeg, '-nostdin', '-hide_banner', '-progress', 'pipe:1',
                         '-i', str(source), '-c:a', 'copy', str(output)])
        metadata = json.loads(run([ffprobe, '-v', 'error', '-show_streams',
                                   '-show_format', '-of', 'json', str(output)]).stdout)
        if metadata['streams'][0]['codec_name'] != 'pcm_s16le' or not 0.24 <= float(metadata['format']['duration']) <= 0.26:
            raise RuntimeError('Output metadata mismatch')
        if 'progress=end' not in converted.stdout:
            raise RuntimeError('Missing final progress event')
        checks.append({'name':'remux-probe-and-progress', 'passed':True})
        run([ffmpeg, '-this_option_must_not_exist'], success=False)
        run([ffmpeg, '-version'])
        checks.append({'name':'invalid-command-does-not-terminate-parent', 'passed':True})
        for index in range(2):
            run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(source),
                 '-c:a', 'copy', str(root / f'repeat-{index}.wav')])
        checks.append({'name':'sequential-independent-command-processes', 'passed':True})
        child = subprocess.Popen([ffmpeg, '-nostdin', '-v', 'error', '-re', '-f',
                                  'lavfi', '-i', 'sine=frequency=440', '-t', '60',
                                  '-c:a', 'pcm_s16le', str(root / 'cancel.wav')],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            time.sleep(1)
            if child.poll() is not None:
                raise RuntimeError('Cancellation target exited before signal')
            child.send_signal(signal.SIGINT)
            _, stderr = child.communicate(timeout=10)
            if child.returncode == 0:
                raise RuntimeError('Cancellation unexpectedly reported success')
            checks.append({'name':'interrupt-and-reap-child', 'passed':True,
                           'exitCode':child.returncode})
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()
    report = {'scope':'Linux host processes only; not HarmonyOS runtime validation',
              'platform':platform.platform(), 'version':version,
              'harmonyDeviceTested':False, 'harCommandEntryTested':False, 'checks':checks}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
