web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn airguard.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile -
