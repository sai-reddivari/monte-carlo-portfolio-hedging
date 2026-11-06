"""Fresh-kernel notebook execution with an explicit interpreter and repository root."""
from pathlib import Path
import sys
import os

def execute(source, destination, *, root=None, python=None):
    root=Path(root or Path(__file__).resolve().parents[1])
    python=python or sys.executable
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client import KernelManager
    import tempfile
    source, destination = root/source, root/destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    nb = nbformat.read(source, as_version=4)
    # Same transport and interpreter as the repository's notebook runner.
    with tempfile.TemporaryDirectory(prefix='phase0-kernel-', dir='/tmp') as runtime:
        runtime = Path(runtime)
        env = dict(os.environ, IPYTHONDIR=str(runtime/'ipython'), JUPYTER_RUNTIME_DIR=str(runtime),
                   MPLBACKEND='module://matplotlib_inline.backend_inline')
        km = KernelManager(kernel_name='python3', transport='ipc', connection_file=str(runtime/'k.json'))
        km.kernel_spec.argv = [str(python), '-m', 'ipykernel_launcher', '-f', '{connection_file}']
        client = NotebookClient(nb, timeout=1200, kernel_name='python3', km=km,
                                resources={'metadata': {'path': str(root)}})
        try:
            client.execute(env=env)
        finally:
            if km.has_kernel:
                km.shutdown_kernel(now=True)
            nbformat.write(nb, destination)

if __name__ == '__main__':
    execute(sys.argv[1],sys.argv[2])
