@echo off
setlocal
python "%~dp0start.py" %*
exit /b %ERRORLEVEL%
