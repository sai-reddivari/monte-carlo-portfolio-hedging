"""Compile the research paper from LaTeX; no data acquisition or experiments."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tectonic',default=os.environ.get('TECTONIC') or shutil.which('tectonic'))
    args=parser.parse_args()
    if not args.tectonic:parser.error('Install Tectonic or pass --tectonic /path/to/tectonic.')
    with tempfile.TemporaryDirectory(prefix='hedging-paper-',dir='/tmp') as tmp:
        subprocess.run([args.tectonic,'--keep-logs','--outdir',tmp,'research_study.tex'],cwd=ROOT/'docs/latex',check=True)
        log=(Path(tmp)/'research_study.log').read_text()
        if 'Overfull' in log or 'undefined references' in log.lower():
            raise RuntimeError('Resolve layout/reference warnings before publishing the PDF.')
        shutil.copy2(Path(tmp)/'research_study.pdf',ROOT/'docs/research_study.pdf')
    print('Built docs/research_study.pdf. Inspect rendered pages before publication.')

if __name__=='__main__':main()
