"""Delete only known generated directories inside this runner's checkout."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
for name in ['work', 'dist']:
    path = (root / name).resolve()
    if path.parent != root:
        raise RuntimeError('Refusing to clean outside checkout')
    if path.exists(): shutil.rmtree(path)
print('Temporary build files removed from runner')
