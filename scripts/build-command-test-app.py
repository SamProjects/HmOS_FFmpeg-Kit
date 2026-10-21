#!/usr/bin/env python3
"""Build an offline emulator test HAP from the existing command-test HAR."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

from common import ROOT, WORK, DIST
from hap_validation import validate_hap


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inspect_har(har):
    libraries = {'arm64-v8a':{}, 'x86_64':{}}
    with tarfile.open(har) as archive:
        for member in archive.getmembers():
            name = member.name.removeprefix('./').removeprefix('package/')
            parts = name.split('/')
            if len(parts) == 3 and parts[0] == 'libs' and name.endswith('.so'):
                if parts[1] not in libraries or not member.isfile():
                    raise ValueError('Unexpected HAR ABI or library entry: ' + name)
                libraries[parts[1]][parts[2]] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    for abi, entries in libraries.items():
        if len(entries) != 10 or 'libhmosffmpegcmd.so' not in entries:
            raise ValueError('A command-test HAR with ten libraries per ABI is required: ' + abi)
    return libraries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--har', type=Path,
                        default=DIST / 'assets/hmos-ffmpeg-1.0.2-extended-all-command-test.har')
    parser.add_argument('--tools', type=Path, default=Path(os.environ.get(
        'HARMONY_TOOLS', str(WORK / 'sdk/command-line-tools'))))
    parser.add_argument('--video', type=Path, required=True, help='Private local input video, embedded only in generated artifacts')
    parser.add_argument('--output', type=Path, default=DIST / 'test-app')
    parser.add_argument('--abi', choices=['arm64-v8a','x86_64'], help='Optional test HAP ABI; the input HAR remains universal')
    args = parser.parse_args()
    har, tools, output = args.har.resolve(), args.tools.resolve(), args.output.resolve()
    if not har.is_file() or not (tools / 'sdk').is_dir():
        parser.error('Provide an existing command-test HAR and HarmonyOS Command Line Tools directory')
    if not args.video.is_file():
        parser.error('--video must point to an existing local media file')
    libraries = inspect_har(har)
    selected = [args.abi] if args.abi else list(libraries)
    output.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(exist_ok=True)
    env = os.environ.copy()
    env['HARMONY_TOOLS'] = str(tools)
    env['HOS_SDK_HOME'] = str(tools / 'sdk')
    env['DEVECO_SDK_HOME'] = str(tools / 'sdk')
    env['PATH'] = os.pathsep.join([str(tools / 'bin'), str(tools / 'tool/node/bin'), env['PATH']])
    with tempfile.TemporaryDirectory(prefix='command-test-app-', dir=WORK) as temporary:
        project = Path(temporary) / 'FFmpegCommandTest'
        shutil.copytree(ROOT / 'examples/consumer', project, ignore=shutil.ignore_patterns(
            'build', '.hvigor', 'oh_modules', 'node_modules', 'local.properties',
            'oh-package-lock.json5', '*.har'))
        raw = project / 'entry/src/main/resources/rawfile'
        fixture_manifest = None
        if args.video:
            original = args.video.resolve()
            shutil.copy2(original, raw / 'user-video.mp4')
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(original),
                            '-t', '8', '-vf', 'scale=320:180', '-c:v', 'mpeg4', '-q:v', '5',
                            '-c:a', 'aac', '-ar', '48000', str(raw / 'compatible-video.mp4')], check=True)
            fixture_manifest = {name:sha256(raw / name) for name in ['user-video.mp4','compatible-video.mp4']}
        (project / 'entry/libs').mkdir(exist_ok=True)
        shutil.copy2(har, project / 'entry/libs/hmos-ffmpeg.har')
        profile_path = project / 'entry/build-profile.json5'
        profile = json.loads(profile_path.read_text())
        profile['buildOption']['externalNativeOptions']['abiFilters'] = selected
        profile['buildOption']['nativeLib']['filter']['excludes'] = ['**/' + abi + '/**' for abi in libraries if abi not in selected]
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n')
        project_zip = output / 'ffmpeg-command-test-project.zip'
        with zipfile.ZipFile(project_zip, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(project.rglob('*')):
                if path.is_file():
                    archive.write(path, str(Path(project.name) / path.relative_to(project)))
        for command in [['ohpm', 'install', '--all'],
                        ['hvigorw', '--mode', 'module', '-p', 'product=default', '-p',
                         'module=entry@default', '-p', 'buildMode=debug', 'assembleHap', '--no-daemon']]:
            subprocess.run(command, cwd=project, env=env, check=True)
        candidates = list((project / 'entry/build/default/outputs').rglob('*-unsigned.hap'))
        if len(candidates) != 1:
            raise ValueError('Expected exactly one unsigned emulator HAP')
        hap = output / 'ffmpeg-command-test-emulator-unsigned.hap'
        shutil.copy2(candidates[0], hap)
        validation = validate_hap(hap, libraries, selected)
        with zipfile.ZipFile(hap) as archive:
            if archive.testzip() is not None:
                raise ValueError('Invalid HAP ZIP')
            if fixture_manifest:
                for name, expected in fixture_manifest.items():
                    if hashlib.sha256(archive.read('resources/rawfile/' + name)).hexdigest() != expected:
                        raise ValueError('Video fixture hash mismatch: ' + name)
            module = json.loads(archive.read('module.json'))
            if not any(name.endswith('modules.abc') for name in archive.namelist()):
                raise ValueError('Missing compiled ArkTS code')
            if 'resources/rawfile/command-input.wav' not in archive.namelist():
                raise ValueError('Missing offline test audio')
        record = {'hap':hap.name, 'sha256':sha256(hap), 'harSha256':sha256(har),
                  'bundleName':module['app']['bundleName'], 'signed':False,
                  'target':'DevEco local emulator permitting unsigned development HAPs',
                  'installedOrExecuted':False, 'nativeLibrariesMatchHar':True,
                  'validation':validation, 'videoFixtures':fixture_manifest, 'selectedAbis':selected, 'testCaseCount':len(json.loads((raw / 'command-cases.json').read_text()))}
        (output / 'validation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        shutil.copy2(ROOT / 'docs/TEST-APP.zh-CN.md', output / 'README.zh-CN.md')
        print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
