"""Inspect the delivered package, not only the compiler ABI configuration."""
import hashlib
from pathlib import Path
import zipfile


def validate_hap(path, runtime, selected):
    expected = {f'libs/{abi}/{name}':sha for abi in selected for name,sha in runtime[abi].items()}
    with zipfile.ZipFile(path) as z:
        actual = {n for n in z.namelist() if n.startswith('libs/') and n.endswith('.so')}
        if actual != set(expected):
            raise ValueError(f'HAP ABI/library closure mismatch: missing={set(expected)-actual}, unexpected={actual-set(expected)}')
        for name, sha in expected.items():
            if hashlib.sha256(z.read(name)).hexdigest() != sha:
                raise ValueError('HAP library changed: ' + name)
        sizes = {abi:sum(z.getinfo(n).file_size for n in actual if n.startswith('libs/' + abi + '/')) for abi in selected}
    return {'selectedAbis':selected, 'packagedAbis':sorted({n.split('/')[1] for n in actual}),
            'hapBytes':Path(path).stat().st_size, 'nativeBytes':sizes, 'libraryCount':len(actual)}
