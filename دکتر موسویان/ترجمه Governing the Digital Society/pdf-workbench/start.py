"""One-click launcher.

Two modes:
- Installed (bundled runtime present): just start the server. No internet, no setup.
- Source layout (no bundled runtime): create .runtime venv and install requirements
  on first run (internet needed once), then start.

Always opens the browser once the local server is healthy.
"""
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:4356'
PORT = 4356
os.chdir(ROOT)


def healthy():
    try:
        with urllib.request.urlopen(URL + '/api/health', timeout=1) as response:
            return response.status == 200 and b'"ok":true' in response.read()
    except Exception:
        return False


def open_when_ready():
    for _ in range(120):
        if healthy():
            webbrowser.open(URL)
            return
        time.sleep(.5)
    print('Server startup took too long. Check setup.log.')


def find_python():
    """Return (python, needs_setup). Uses the bundled runtime when present."""
    for rel in ('.runtime/Scripts/python.exe', 'python-runtime/Scripts/python.exe'):
        p = ROOT / rel
        if p.exists():
            return str(p), False
    return sys.executable, True


def main():
    if healthy():
        webbrowser.open(URL)
        return
    python, needs_setup = find_python()
    log = (ROOT / 'setup.log').open('a', encoding='utf-8')
    if needs_setup:
        # Source layout: build the venv and install deps (internet on first run).
        environment = ROOT / '.runtime'
        stamp = environment / 'installed.sha256'
        fingerprint = __import__('hashlib').sha256(
            (ROOT / 'requirements.txt').read_bytes()).hexdigest()
        if not (environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')).exists():
            print('Preparing application. Please wait...')
            subprocess.run([sys.executable, '-m', 'venv', str(environment)],
                           stdout=log, stderr=log, check=True)
        if not stamp.exists() or stamp.read_text() != fingerprint:
            print('Installing requirements automatically. Internet access is required on first run...')
            subprocess.run([python, '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')],
                           stdout=log, stderr=log, check=True)
            stamp.write_text(fingerprint)
        python = str(environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))
    threading.Thread(target=open_when_ready, daemon=True).start()
    print('Application is starting. Keep this window open (close it to stop the server).')
    subprocess.run([python, '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', str(PORT)],
                   stdout=log, stderr=log, check=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError):
        print('Could not finish starting. Check setup.log, then try again.')
        input('Press Enter to close...')
    except KeyboardInterrupt:
        pass
