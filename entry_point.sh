#!/bin/sh
set -e

./manage.py migrate --noinput
./manage.py collectstatic --noinput --clear

django-admin compilemessages

# Check if `admin` user exists, if not create one with default password in DEFAULT_ADMIN_PASSWORD environment variable
./manage.py create_default_superuser

exec gunicorn config.wsgi:application --config gunicorn.conf.py
