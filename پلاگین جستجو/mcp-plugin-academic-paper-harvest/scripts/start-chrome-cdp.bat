@echo off
REM Starts Chrome with remote debugging (CDP) enabled, using the current
REM user's profile so your paper-site login is preserved.
REM Overridable via env vars:
REM   CDP_PORT        (default 9222)
REM   CHROME_USER_DATA (default %USERPROFILE%\AppData\Local\Google\Chrome\User Data)
REM   CHROME_EXE      (auto-detected if unset)
setlocal
if "%CDP_PORT%"=="" set CDP_PORT=9222
if "%CHROME_USER_DATA%"=="" set CHROME_USER_DATA=%USERPROFILE%\AppData\Local\Google\Chrome\User Data
if "%CHROME_EXE%"=="" set CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe
if not exist "%CHROME_EXE%" set CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
taskkill /IM chrome.exe /F >nul 2>&1
timeout /t 3 /nobreak >nul
start "" "%CHROME_EXE%" --remote-debugging-port=%CDP_PORT% --user-data-dir="%CHROME_USER_DATA%"
echo Chrome started with CDP on port %CDP_PORT%. You can close this window.
