#!/bin/sh
set -e

echo "==> Migrationlarni ishga tushiramiz..."
python manage.py migrate --noinput

echo "==> Static fayllarni yig'amiz..."
python manage.py collectstatic --noinput --clear

echo "==> Gunicorn ishga tushirilmoqda..."
exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    config.wsgi:application
