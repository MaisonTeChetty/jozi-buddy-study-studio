@echo off
setlocal
"%~dp0.venv\Scripts\python.exe" -u "%~dp0voice_agent.py"
exit /b %errorlevel%
