@echo off
setlocal
set "JOZI_AWS_EXE=%ProgramFiles%\Amazon\AWSCLIV2\aws.exe"
if not exist "%JOZI_AWS_EXE%" set "JOZI_AWS_EXE=aws"
echo Jozi Buddy - AWS sign-in
echo Open the URL printed below in Chrome.
echo Enter the authorization code only in this terminal, never in chat.
echo This flow does not use a browser callback to localhost.
echo The default profile must use your project's home region for sign-in.
"%JOZI_AWS_EXE%" login --remote
if errorlevel 1 (
  echo AWS sign-in did not finish. Keep the error text for troubleshooting.
  pause
  exit /b 1
)
"%JOZI_AWS_EXE%" sts get-caller-identity --query Account --output text --no-cli-pager
pause
