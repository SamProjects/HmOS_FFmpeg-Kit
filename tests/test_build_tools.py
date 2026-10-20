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
            conf = '#define CONFIG_GPL 0\n#define CONFIG_NONFREE 0\n#define CONFIG_VERSION3 1\n#define FFMPEG_LICENSE "GNU Lesser General Public License v3 or later"\n'
            (f / 'configure-args.txt').write_text('--disable-gpl\n--disable-nonfree\n--enable-version3\n')
            (f / 'config.h').write_text(conf)
            gate.license_gate()
            (f / 'config.h').write_text(conf.replace('CONFIG_GPL 0', 'CONFIG_GPL 1'))
            with self.assertRaises(ValueError): gate.license_gate()
            (f / 'config.h').write_text(conf.replace('CONFIG_NONFREE 0', 'CONFIG_NONFREE 1'))
            with self.assertRaises(ValueError): gate.license_gate()


if __name__ == '__main__': unittest.main()
