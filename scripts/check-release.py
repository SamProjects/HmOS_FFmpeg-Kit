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


def validate_har_only(directory):
    directory = Path(directory)
    base = f'hmos-ffmpeg-{PROJECT["version"]}-extended-all' + HAR_SUFFIX
    har = directory / (base + '.har')
    if set(directory.iterdir()) != {har} or not har.is_file() or har.stat().st_size == 0:
        raise ValueError('Expected only the extended universal HAR')
    report = json.loads((directory.parent / 'extended-all/consumer-validation.json').read_text())
    if not report['consumerHapBuilt'] or report['harSha256'] != digest(har):
        raise ValueError('Universal HAR evidence mismatch')
    expected = {tuple([abi]) for abi in PROJECT['abis']} | {tuple(PROJECT['abis'])}
    if len(report['selections']) != len(expected) or {tuple(r['selectedAbis']) for r in report['selections']} != expected:
        raise ValueError('Incomplete universal consumer matrix')
    for r in report['selections']:
        if r['packagedAbis'] != sorted(r['selectedAbis']) or r['libraryCount'] != RUNTIME_LIBRARY_COUNT * len(r['selectedAbis']):
            raise ValueError('Consumer contains wrong architecture/library count')
    libraries = {}
    for abi in PROJECT['abis']:
        manifest = json.loads((directory.parent / profile_key('extended', abi) / 'manifest.json').read_text())
        if manifest['profile'] != 'extended' or manifest['project'] != PROJECT or manifest['abi'] != abi:
            raise ValueError('Wrong profile/version/ABI')
        if os.environ.get('GITHUB_SHA') and manifest['commit'] != os.environ['GITHUB_SHA']:
            raise ValueError('Artifact commit mismatch')
        if COMMAND_TEST and not manifest.get('commandExperimental'):
            raise ValueError('Missing command-test provenance')
        if len(manifest['libraries']) != RUNTIME_LIBRARY_COUNT or not all(manifest['validation'][g] for g in ['sourceIntegrity', 'licenseConfig', 'elfClosure']):
            raise ValueError('Build gates did not pass')
        libraries.update({f'libs/{abi}/{name}':sha for name,sha in manifest['libraries'].items()})
    with tarfile.open(har) as t:
        members = {m.name.removeprefix('./').removeprefix('package/'):m for m in t.getmembers()}
        actual = {name for name in members if name.startswith('libs/') and name.endswith('.so')}
        if actual != set(libraries) or 'Index.ets' not in members:
            raise ValueError('HAR ABI/library closure or ArkTS entry mismatch')
        for name, sha in libraries.items():
            if hashlib.sha256(t.extractfile(members[name]).read()).hexdigest() != sha:
                raise ValueError('HAR library changed: ' + name)
    print('Extended universal HAR, both ABI build gates and three consumer selections verified')


def validate(directory):
    if HAR_ONLY:
        return validate_har_only(directory)
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
            if r['packagedAbis'] != sorted(r['selectedAbis']) or r['libraryCount'] != RUNTIME_LIBRARY_COUNT * len(r['selectedAbis']):
                raise ValueError('Consumer contains wrong architecture/library count')
    print('All single-ABI and universal HAR packages, consumers and exact sources verified')


if __name__ == '__main__': validate(sys.argv[1])
