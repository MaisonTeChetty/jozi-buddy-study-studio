@echo off
setlocal
cd /d "%~dp0"
if not exist "web\dist\index.html" (
  echo Building the study studio...
  call npm.cmd --prefix web run build
  if errorlevel 1 exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -m studio.server
exit /b %errorlevel%
