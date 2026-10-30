@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.12 -m venv .venv
  if errorlevel 1 py -3.11 -m venv .venv
  if errorlevel 1 goto :fail
)
.venv\Scripts\python.exe -m pip install -r requirements.lock
if errorlevel 1 goto :fail
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe -m jitd.launch
if errorlevel 1 goto :fail
exit /b 0
:fail
 echo Setup or startup failed. See the message above. Install Python 3.12 or 3.11 and try again.
 pause
 exit /b 1
