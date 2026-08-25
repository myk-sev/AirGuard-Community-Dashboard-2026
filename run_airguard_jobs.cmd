@echo off
setlocal
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
set "FAILED=0"
echo [%date% %time%] AirGuard pipeline started>>"logs\airguard-jobs.log"
".venv\Scripts\python.exe" manage.py evaluate_alerts >>"logs\airguard-jobs.log" 2>&1 || set "FAILED=1"
".venv\Scripts\python.exe" manage.py send_outbox >>"logs\airguard-jobs.log" 2>&1 || set "FAILED=1"
echo [%date% %time%] AirGuard pipeline finished with code %FAILED%>>"logs\airguard-jobs.log"
exit /b %FAILED%
