#!/usr/bin/env python3
from common import *
import sys


def validate(directory):
    directory = Path(directory)
    for profile in ['core', 'extended']:
        base = f'hmos-ffmpeg-{PROJECT["version"]}-{profile}-arm64-v8a'
        for suffix in ['.har','-sdk.tar.gz','-sources.tar.gz','-manifest.json']:
            path = directory / (base + suffix)
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError('Missing asset: ' + path.name)
            checksum = (directory / (path.name + '.sha256')).read_text().split()
            if checksum != [digest(path), path.name]:
                raise ValueError('Asset checksum mismatch: ' + path.name)
        manifest = json.loads((directory / (base + '-manifest.json')).read_text())
        if manifest['profile'] != profile or manifest['project'] != PROJECT:
            raise ValueError('Wrong profile/version')
        if os.environ.get('GITHUB_SHA') and manifest['commit'] != os.environ['GITHUB_SHA']:
            raise ValueError('Artifact commit mismatch')
        if not all(manifest['validation'][x] for x in ['sourceIntegrity','licenseConfig','elfClosure']):
            raise ValueError('Build gates did not pass')
        with tarfile.open(directory / (base + '-sdk.tar.gz')) as t:
            member = t.extractfile(base + '/consumer-validation.json')
            if not member or not json.load(member)['consumerHapBuilt']:
                raise ValueError('Consumer build missing')
    print('Both HAR packages and exact corresponding sources verified')


if __name__ == '__main__': validate(sys.argv[1])
