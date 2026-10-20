#!/usr/bin/env python3
from common import *
import sys


def check_asset(directory, name):
    path = directory / name
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError('Missing asset: ' + name)
    if (directory / (name + '.sha256')).read_text().split() != [digest(path), name]:
        raise ValueError('Asset checksum mismatch: ' + name)
    return path


def validate(directory):
    directory = Path(directory)
    for profile in ['core', 'extended']:
        for abi in PROJECT['abis']:
            base = f'hmos-ffmpeg-{PROJECT["version"]}-{profile}-{abi}'
            for suffix in ['.har','-sdk.tar.gz','-sources.tar.gz','-manifest.json']:
                check_asset(directory, base + suffix)
            manifest = json.loads((directory / (base + '-manifest.json')).read_text())
            if manifest['profile'] != profile or manifest['project'] != PROJECT or manifest['abi'] != abi:
                raise ValueError('Wrong profile/version/ABI')
            if os.environ.get('GITHUB_SHA') and manifest['commit'] != os.environ['GITHUB_SHA']:
                raise ValueError('Artifact commit mismatch')
            if not all(manifest['validation'][x] for x in ['sourceIntegrity','licenseConfig','elfClosure']):
                raise ValueError('Build gates did not pass')
            with tarfile.open(directory / (base + '-sdk.tar.gz')) as t:
                member = t.extractfile(base + '/consumer-validation.json')
                if not member or not json.load(member)['consumerHapBuilt']:
                    raise ValueError('Consumer build missing')
        base = f'hmos-ffmpeg-{PROJECT["version"]}-{profile}-all'
        har = check_asset(directory, base + '.har')
        report = json.loads(check_asset(directory, base + '-consumer-validation.json').read_text())
        if not report['consumerHapBuilt'] or report['harSha256'] != digest(har):
            raise ValueError('Universal HAR evidence mismatch')
        expected = {tuple([abi]) for abi in PROJECT['abis']} | {tuple(PROJECT['abis'])}
        if {tuple(r['selectedAbis']) for r in report['selections']} != expected:
            raise ValueError('Incomplete universal consumer matrix')
        for r in report['selections']:
            if r['packagedAbis'] != sorted(r['selectedAbis']) or r['libraryCount'] != 9 * len(r['selectedAbis']):
                raise ValueError('Consumer contains wrong architecture/library count')
    print('All single-ABI and universal HAR packages, consumers and exact sources verified')


if __name__ == '__main__': validate(sys.argv[1])
