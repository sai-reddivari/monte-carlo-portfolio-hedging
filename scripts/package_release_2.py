"""Guard the existing publication snapshot; original packager is archived."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def package_release():
    raise FileExistsError('The immutable Research Release 2 package already exists. Original packaging code is preserved in results/pre_refactor/tools/package_release_2.py; Phase 1 does not create another economic release.')
if __name__ == '__main__':
    package_release()
