"""Build a self-contained, offline single-file installer for Baraghe.

Produces dist/Baraghe-Setup.bat : a self-extracting Windows batch file that:
  1. Lets the user pick (or default) an install folder.
  2. Extracts the embedded base64 payload (app + bundled Python runtime + deps + fonts).
  3. Creates a desktop shortcut and launches the app.

No external tools (NSIS/Inno/PyInstaller) and no internet required at install time.
"""
import base64
import io
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
APP_NAME = 'Baraghe'
APP_DISPLAY = 'Baraghe — PDF Persian Translation Workbench'
DEFAULT_DEST = os.path.join(os.environ.get('LOCALAPPDATA', str(Path.home())), APP_NAME)


def stage_payload() -> Path:
    """Assemble the app payload (source + bundled runtime + fonts, no user data)."""
    stage = Path(tempfile.gettempdir()) / 'baraghe-stage'
    if stage.exists():
        shutil.rmtree(stage, ignore_errors=True)
    dest = stage / APP_NAME
    dest.mkdir(parents=True)

    # App source
    for name in ('app.py', 'start.py', 'start.bat', 'requirements.txt', 'README.md', 'test_app.py'):
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, dest / name)
    (dest / 'static').mkdir()
    shutil.copy2(ROOT / 'static' / 'index.html', dest / 'static' / 'index.html')
    (dest / 'static' / 'fonts').mkdir()
    for f in (ROOT / 'static' / 'fonts').glob('*'):
        shutil.copy2(f, dest / 'static' / 'fonts' / f.name)

    # Bundled Python runtime (the .runtime venv, renamed)
    runtime = ROOT / 'python-runtime'
    if (ROOT / '.runtime').exists() and not runtime.exists():
        shutil.copytree(ROOT / '.runtime', runtime, dirs_exist_ok=True)
    shutil.copytree(runtime, dest / 'python-runtime', dirs_exist_ok=True)

    # Safety: never ship user data or logs
    for junk in (dest / 'data', dest / 'setup.log', dest / 'dist'):
        if junk.exists():
            shutil.rmtree(junk, ignore_errors=True)
    return dest


def make_zip(payload: Path) -> Path:
    """Zip the payload so its files extract FLAT into the install dir (no nested folder)."""
    DIST.mkdir(exist_ok=True)
    zip_path = DIST / 'baraghe-payload.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in sorted(payload.rglob('*')):
            if p.is_file():
                zf.write(p, arcname=p.relative_to(payload))
    return zip_path


def make_bat(zip_path: Path) -> Path:
    b64 = base64.b64encode(zip_path.read_bytes()).decode('ascii')
    b64_lines = [b64[i:i + 4000] for i in range(0, len(b64), 4000)]
    marker = '@@@B64PAYLOAD@@@'

    head = r'''@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Baraghe Installer
echo ============================================================
echo  Baraghe - PDF to Persian Translation Workbench
echo  Self-contained offline installer (no Python needed)
echo ============================================================
echo.
set "DEST=%LOCALAPPDATA%\Baraghe"
echo  Default install location: %DEST%
set /p CUSTOM="Press ENTER for default, or type a folder path: "
rem Validate the input: must be empty or a valid drive path (e.g. D:\...).
if not "%CUSTOM%"=="" (
  if "%CUSTOM:~0,2%"=="\" (
    echo  [warning] A path without a drive letter (like %CUSTOM%) is not usable.
    echo  Using the default location instead.
  ) else (
    echo "%CUSTOM%" | findstr /r "^[A-Za-z]:" >nul
    if errorlevel 1 (
      echo  [warning] %CUSTOM% does not look like a drive path (e.g. D:\Baraghe).
      echo  Using the default location instead.
    ) else (
      set "DEST=%CUSTOM%"
    )
  )
)
echo.
echo  Installing to: %DEST%
if exist "%DEST%\app.py" echo  (Previous installation found - will be updated.)
if not exist "%DEST%" mkdir "%DEST%" 2>nul
if not exist "%DEST%" (
  echo  ERROR: cannot create install folder %DEST%. Pick a valid path.
  pause
  exit /b 1
)
echo.
echo  Extracting embedded payload... please wait.
set "SELF=%~f0"
set "ZIP=%TEMP%\baraghe-payload-%RANDOM%.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$bat = Get-Content -LiteralPath '%SELF%' -Raw; " ^
  "$ms = [regex]::Matches($bat, [regex]::Escape('@@@B64PAYLOAD@@@')) ; " ^
  "if ($ms.Count -lt 1) { exit 1 }; " ^
  "$m = $ms[$ms.Count-1] ; " ^
  "$b64 = ($bat.Substring($m.Index + $m.Length) -replace '[\s]','') ; " ^
  "try { [IO.File]::WriteAllBytes('%ZIP%', [Convert]::FromBase64String($b64)) ; exit 0 } catch { exit 2 }"
if errorlevel 1 ( echo  ERROR: could not decode the embedded payload. & pause & exit /b 1 )
echo  Unpacking files...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%DEST%' -Force"
if errorlevel 1 ( echo  ERROR: file extraction failed. & pause & exit /b 1 )
del "%ZIP%" 2>nul
echo.
echo  Installation complete.
set "PY=%DEST%\python-runtime\Scripts\pythonw.exe"
set "START=%DEST%\start.py"
if not exist "%PY%" (
  echo  ERROR: pythonw.exe was not found at:
  echo    %PY%
  echo  The payload may not have unpacked correctly. Re-run the installer.
  pause
  exit /b 1
)
set "LNK=%USERPROFILE%\Desktop\Baraghe.lnk"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');$s.TargetPath='%PY%';$s.Arguments='\"%START%\"';$s.WorkingDirectory='%DEST%';$s.IconLocation='%PY%,0';$s.Description='Baraghe - PDF Persian Translation';$s.Save()"
echo  A desktop shortcut "Baraghe" was created.
echo.
echo  Starting Baraghe now - a browser window will open.
start "" "%PY%" "%START%"
echo.
echo  The server is running in the background. To stop it, use Task Manager (pythonw.exe).
echo.
pause
exit /b 0
'''.replace('@@@B64PAYLOAD@@@', marker)

    # The payload is appended AFTER the executable batch section, after the marker line.
    full = head + "\r\n" + marker + "\r\n" + "\r\n".join(b64_lines) + "\r\n"
    out = DIST / 'Baraghe-Setup.bat'
    out.write_bytes(full.encode('ascii'))
    return out


def main():
    print('[1/3] Staging payload...')
    payload = stage_payload()
    n = sum(1 for _ in payload.rglob('*') if _.is_file())
    size = sum(f.stat().st_size for f in payload.rglob('*') if f.is_file())
    print(f'      {n} files, {size/1e6:.1f} MB')
    print('[2/3] Zipping payload...')
    zip_path = make_zip(payload)
    print(f'      {zip_path.name} = {zip_path.stat().st_size/1e6:.1f} MB')
    print('[3/3] Building self-extracting .bat...')
    bat = make_bat(zip_path)
    print(f'      {bat.name} = {bat.stat().st_size/1e6:.2f} MB')
    shutil.rmtree(payload.parent, ignore_errors=True)
    print('Done: ' + str(bat))


if __name__ == '__main__':
    main()
