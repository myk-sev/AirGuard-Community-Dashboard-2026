@echo off
setlocal
cd /d "%~dp0"
if "%AIRGUARD_INGEST_TOKEN%"=="" (
  echo Set AIRGUARD_INGEST_TOKEN before uploading measurements.
  exit /b 1
)
if "%AIRGUARD_UPLOAD_URL%"=="" set "AIRGUARD_UPLOAD_URL=http://127.0.0.1:8000/api/v1/measurements/govee/"
if not exist "emails\read" mkdir "emails\read"
for %%F in ("emails\*.csv") do if exist "%%~fF" (
  curl.exe --fail --show-error --silent --retry 3 -H "Authorization: Bearer %AIRGUARD_INGEST_TOKEN%" -F "file=@%%~fF" "%AIRGUARD_UPLOAD_URL%" || exit /b 1
  move /Y "%%~fF" "emails\read\" >nul
)
