#!/usr/bin/env python3
"""Linux CI bootstrap. Local SDKs are supported without any download."""
from common import *
import shutil

sdk = os.environ.get('OHOS_NATIVE')
if not sdk:
    lock = json.loads((ROOT / 'config/sdk.lock.json').read_text())
    archives = [download(lock['baseUrl'] + n, WORK / 'sdk-downloads' / n, h)
                for n, h in lock['parts'].items()]
    combined = WORK / 'sdk-downloads/sdk.tar.gz'
    with combined.open('wb') as out:
        for part in archives:
            with part.open('rb') as f:
                shutil.copyfileobj(f, out)
    sdk_root = WORK / 'sdk'
    extract(combined, sdk_root)
    combined.unlink()
    for part in archives:
        part.unlink()
    tools = sdk_root / 'command-line-tools'
    sdk = str(tools / 'sdk/default/openharmony/native')
else:
    tools = Path(os.environ['HARMONY_TOOLS'])
sdk = Path(sdk).resolve()
metadata = json.loads((sdk / 'oh-uni-package.json').read_text())
if int(metadata['apiVersion']) < PROJECT['minimumApi']:
    raise SystemExit('SDK too old')
write_json(WORK / 'sdk.json', {'native': str(sdk), 'metadata': metadata,
    'toolchainSha256': digest(sdk / 'build/cmake/ohos.toolchain.cmake')})
if 'GITHUB_ENV' in os.environ:
    with open(os.environ['GITHUB_ENV'], 'a') as f:
        f.write(f'OHOS_NATIVE={sdk}\nHOS_SDK_HOME={tools / "sdk"}\nHARMONY_TOOLS={tools}\n')
    with open(os.environ['GITHUB_PATH'], 'a') as f:
        for x in [tools / 'bin', tools / 'tool/node/bin', sdk / 'build-tools/cmake/bin']:
            f.write(str(x) + '\n')
print(sdk)
