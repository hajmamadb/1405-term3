"""One-click bootstrap: isolated environment, dependencies, local server, browser."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:4356'
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


def main():
    if healthy():
        webbrowser.open(URL)
        return
    environment = ROOT / '.runtime'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    requirements = (ROOT / 'requirements.txt').read_bytes()
    import hashlib
    fingerprint = hashlib.sha256(requirements).hexdigest()
    stamp = environment / 'installed.sha256'
    with (ROOT / 'setup.log').open('a', encoding='utf-8') as log:
        if not python.exists():
            print('Preparing application. Please wait...')
            subprocess.run([sys.executable, '-m', 'venv', str(environment)], stdout=log, stderr=log, check=True)
        if not stamp.exists() or stamp.read_text() != fingerprint:
            print('Installing requirements automatically. Internet access is required on first run...')
            subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')],
                           stdout=log, stderr=log, check=True)
            stamp.write_text(fingerprint)
        threading.Thread(target=open_when_ready, daemon=True).start()
        print('Application is starting. Keep this window open.')
        subprocess.run([str(python), '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', '4356'],
                       stdout=log, stderr=log, check=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError):
        print('Automatic setup could not finish. Check internet access and setup.log, then try again.')
        input('Press Enter to close...')
    except KeyboardInterrupt:
        pass
