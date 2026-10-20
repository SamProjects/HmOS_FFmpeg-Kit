#!/usr/bin/env python3
"""Verify server-side asset names, sizes and SHA-256 before publishing."""
from common import *
import sys


def validate(directory, release):
    if not release['draft'] or release['tag_name'] != os.environ.get('RELEASE_TAG', 'local'):
        raise ValueError('发布草稿或标签不一致')
    local = {p.name:p for p in Path(directory).iterdir() if p.is_file()}
    remote = {a['name']:a for a in release['assets']}
    if set(local) != set(remote):
        raise ValueError('上传文件清单不完整或存在多余文件')
    for name, path in local.items():
        asset = remote[name]
        if asset['state'] != 'uploaded' or asset['size'] != path.stat().st_size or asset.get('digest') != 'sha256:' + digest(path):
            raise ValueError('远端文件校验失败：' + name)
    print('远端发布文件大小与 SHA-256 全部核对通过：', len(local))


if __name__ == '__main__': validate(sys.argv[1], json.loads(Path(sys.argv[2]).read_text()))
