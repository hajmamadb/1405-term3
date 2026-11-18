@echo off
REM Closes Chrome (run this when the research session is done).
taskkill /IM chrome.exe /F
echo Chrome closed. Run start-chrome-cdp.bat again next time.
