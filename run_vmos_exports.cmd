@echo off
setlocal
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
echo [%date% %time%] VMOS export started>>"logs\vmos-exports.log"
if "%VMOS_GOVEE_WORKSPACE%"=="" (
  echo Set VMOS_GOVEE_WORKSPACE to the AirGuard data-pulls folder.>>"logs\vmos-exports.log"
  exit /b 1
)
pushd "%VMOS_GOVEE_WORKSPACE%" || exit /b 1
for %%S in (BGC-B6 BGC-B7 BGC-B8) do (
  ".venv\Scripts\python.exe" -m vmos_govee run ".\vmos_govee\govee_export.example.json" --set GOVEE_PACKAGE=com.govee.home --set GOVEE_DEVICE_NAME=%%S --allow-email-send >>"%~dp0logs\vmos-exports.log" 2>&1 || goto :failed
)
popd
echo [%date% %time%] VMOS export completed>>"logs\vmos-exports.log"
exit /b 0

:failed
popd
echo [%date% %time%] VMOS export failed>>"logs\vmos-exports.log"
exit /b 1
