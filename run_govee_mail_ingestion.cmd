@echo off
setlocal
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
echo [%date% %time%] Govee mailbox ingestion started>>"logs\govee-mail-ingestion.log"
".venv\Scripts\python.exe" manage.py process_govee_mail >>"logs\govee-mail-ingestion.log" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] Govee mailbox ingestion finished with code %EXIT_CODE%>>"logs\govee-mail-ingestion.log"
exit /b %EXIT_CODE%
