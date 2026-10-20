"""Validate timing, stream counts and output geometry, not only file existence."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
for name in ['scaled.mp4', 'remux.mkv', 'audio.wav']:
    data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-show_packets', '-of', 'json', str(root / name)]))
    duration = float(data['format']['duration'])
    assert 1.8 < duration < 2.2, (name, duration)
    previous = {}
    for packet in data['packets']:
        if 'dts' not in packet: continue
        index, value = packet['stream_index'], int(packet['dts'])
        assert index not in previous or value > previous[index], (name, index, value, previous.get(index))
        previous[index] = value
    if name == 'scaled.mp4':
        video = next(s for s in data['streams'] if s['codec_type'] == 'video')
        assert (video['width'], video['height']) == (96, 64)
    if name == 'audio.wav':
        assert len(data['streams']) == 1 and data['streams'][0]['codec_type'] == 'audio'
print('Durations, decode, geometry and DTS checks passed')
