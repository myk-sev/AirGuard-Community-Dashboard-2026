@echo off
setlocal
cd /d "%~dp0"
if "%DJANGO_DEBUG%"=="" set "DJANGO_DEBUG=False"
".venv\Scripts\python.exe" manage.py migrate || exit /b 1
".venv\Scripts\python.exe" manage.py collectstatic --noinput || exit /b 1
".venv\Scripts\waitress-serve.exe" --listen=127.0.0.1:8000 airguard.wsgi:application
