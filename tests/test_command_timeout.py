"""Exercise the native timeout policy with a controlled clock, including >1h."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CommandTimeoutTest(unittest.TestCase):
    def test_deadline_and_js_number_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'command-timeout'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I'+str(ROOT/'native'), str(ROOT/'tests/command_timeout.cpp'),
                            '-o', str(output)], check=True, capture_output=True)
            subprocess.run([str(output)], check=True, capture_output=True)
