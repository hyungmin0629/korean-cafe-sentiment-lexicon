@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
set "collector_python=python"
if exist ".venv\Scripts\python.exe" set "collector_python=.venv\Scripts\python.exe"
%collector_python% -u tools\collect_naver_reviews.py --browser chrome %*
set "collector_exit_code=%errorlevel%"
pause
exit /b %collector_exit_code%
