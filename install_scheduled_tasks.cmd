@echo off
setlocal
for %%F in ("%~dp0run_govee_mail_ingestion.cmd") do set "MAIL_TASK=%%~fF"
for %%F in ("%~dp0run_airguard_jobs.cmd") do set "PIPELINE_TASK=%%~fF"
schtasks.exe /Create /F /TN "AirGuard Govee Mail Ingestion" /SC HOURLY /MO 1 /ST 00:30 /TR "%MAIL_TASK%" || exit /b 1
schtasks.exe /Create /F /TN "AirGuard Data and Alerts" /SC MINUTE /MO 15 /TR "%PIPELINE_TASK%" || exit /b 1
echo AirGuard scheduled tasks installed.
