import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from common import digest, extract, snapshot, PROJECT, SOURCES, ROOT


class BuildToolsTests(unittest.TestCase):
    def test_snapshot_detects_mutation_and_addition(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'source.c'
            p.write_text('original')
            baseline = snapshot(d)
            p.write_text('modified')
            self.assertNotEqual(baseline, snapshot(d))
            p.write_text('original')
            self.assertEqual(baseline, snapshot(d))
            (Path(d) / 'injected.c').write_text('extra')
            self.assertNotEqual(baseline, snapshot(d))

    def test_extraction_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / 'bad.tar'
            with tarfile.open(archive, 'w') as t:
                info = tarfile.TarInfo('../escaped')
                info.size = 3
                t.addfile(info, io.BytesIO(b'bad'))
            with self.assertRaises(tarfile.FilterError): extract(archive, Path(d) / 'target')
            self.assertFalse((Path(d) / 'escaped').exists())

    def test_locks_are_pinned_and_consistent(self):
        self.assertEqual(PROJECT['ffmpeg'], SOURCES['ffmpeg']['version'])
        for s in SOURCES.values():
            self.assertRegex(s['sha256'], r'^[0-9a-f]{64}$')
            self.assertTrue(s['url'].startswith('https://'))
            self.assertNotIn('latest', s['url'])

    def test_workflow_does_not_retain_artifacts_or_caches(self):
        workflow = (ROOT / '.github/workflows/build-release.yml').read_text()
        for action in ['actions/upload-artifact@', 'actions/download-artifact@', 'actions/cache@', 'actions/cache/save@']:
            self.assertNotIn(action, workflow)
        self.assertIn('cleanup-actions-storage.sh', workflow)

    def test_license_gate_rejects_gpl(self):
        old_argv = sys.argv[:]
        sys.argv = ['test', 'core']
        try:
            spec = importlib.util.spec_from_file_location('gate', ROOT / 'scripts/verify-build.py')
            gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
        finally: sys.argv = old_argv
        with tempfile.TemporaryDirectory() as d:
            gate.BUILD = Path(d)
            f = gate.BUILD / 'ffmpeg'; f.mkdir()
            conf = '#define CONFIG_GPL 0\n#define CONFIG_NONFREE 0\n#define CONFIG_VERSION3 1\n#define FFMPEG_LICENSE "LGPL version 3 or later"\n'
            (f / 'configure-args.txt').write_text('--disable-gpl\n--disable-nonfree\n--enable-version3\n')
            (f / 'config.h').write_text(conf)
            gate.license_gate()
            (f / 'config.h').write_text(conf.replace('CONFIG_GPL 0', 'CONFIG_GPL 1'))
            with self.assertRaises(ValueError): gate.license_gate()
            (f / 'config.h').write_text(conf.replace('CONFIG_NONFREE 0', 'CONFIG_NONFREE 1'))
            with self.assertRaises(ValueError): gate.license_gate()

    def test_release_rejects_asset_tampering(self):
        spec = importlib.util.spec_from_file_location('release_gate', ROOT / 'scripts/check-release.py')
        gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            for profile in ['core','extended']:
                for abi in PROJECT['abis']:
                    base = f'hmos-ffmpeg-{PROJECT["version"]}-{profile}-{abi}'
                    (directory / (base + '.har')).write_bytes(b'checksum-test-fixture')
                    (directory / (base + '-sources.tar.gz')).write_bytes(b'source-test-fixture')
                    manifest = {'profile':profile,'project':PROJECT,'abi':abi,'commit':__import__('os').environ.get('GITHUB_SHA','local'),
                                'validation':dict(sourceIntegrity=True,licenseConfig=True,elfClosure=True)}
                    (directory / (base + '-manifest.json')).write_text(json.dumps(manifest))
                    with tarfile.open(directory / (base + '-sdk.tar.gz'), 'w:gz') as t:
                        info = tarfile.TarInfo(base + '/consumer-validation.json')
                        data = b'{"consumerHapBuilt":true}'
                        info.size = len(data); t.addfile(info, io.BytesIO(data))
                base = f'hmos-ffmpeg-{PROJECT["version"]}-{profile}-all'
                (directory / (base + '.har')).write_bytes(b'universal-fixture')
                report = {'harSha256':digest(directory / (base + '.har')), 'consumerHapBuilt':True,
                          'selections':[{'selectedAbis':a,'packagedAbis':sorted(a),'libraryCount':9*len(a)}
                                        for a in [[abi] for abi in PROJECT['abis']] + [PROJECT['abis']]]}
                (directory / (base + '-consumer-validation.json')).write_text(json.dumps(report))
            for path in list(directory.iterdir()):
                (directory / (path.name + '.sha256')).write_text(digest(path) + '  ' + path.name + '\n')
            gate.validate(directory)
            next(directory.glob('*.har')).write_bytes(b'modified')
            with self.assertRaises(ValueError): gate.validate(directory)

    def test_hap_rejects_unwanted_abi_missing_or_changed_library(self):
        from hap_validation import validate_hap
        import hashlib
        import zipfile
        blob = b'library-bytes'
        runtime = {abi:{'libexample.so':hashlib.sha256(blob).hexdigest()} for abi in PROJECT['abis']}
        with tempfile.TemporaryDirectory() as d:
            hap = Path(d) / 'test.hap'
            with zipfile.ZipFile(hap, 'w') as z:
                for abi in PROJECT['abis']: z.writestr('libs/' + abi + '/libexample.so', blob)
            with self.assertRaises(ValueError): validate_hap(hap, runtime, ['arm64-v8a'])
            validate_hap(hap, runtime, PROJECT['abis'])
            with zipfile.ZipFile(hap, 'w') as z: z.writestr('libs/arm64-v8a/libexample.so', blob)
            validate_hap(hap, runtime, ['arm64-v8a'])
            with self.assertRaises(ValueError): validate_hap(hap, runtime, PROJECT['abis'])
            with zipfile.ZipFile(hap, 'w') as z: z.writestr('libs/arm64-v8a/libexample.so', b'altered')
            with self.assertRaises(ValueError): validate_hap(hap, runtime, ['arm64-v8a'])

    def test_remote_upload_gate_rejects_mismatched_asset(self):
        spec = importlib.util.spec_from_file_location('upload_gate', ROOT / 'scripts/check-upload.py')
        gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'file.har'; p.write_bytes(b'validated-library')
            release = {'draft':True, 'tag_name':__import__('os').environ.get('RELEASE_TAG','local'),
                       'assets':[{'name':p.name,'state':'uploaded','size':p.stat().st_size,'digest':'sha256:'+digest(p)}]}
            gate.validate(d, release)
            release['assets'][0]['digest'] = 'sha256:' + '0'*64
            with self.assertRaises(ValueError): gate.validate(d, release)


if __name__ == '__main__': unittest.main()
