#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Wait for database to be ready
if [ "$DATABASE_URL" != "" ]; then
    echo "Waiting for database..."
    # Simplified check using python's psycopg2 or similar if available/needed
    # or just assume depends_on healthcheck handles it in compose
fi

echo "Running migrations..."
python manage.py migrate

echo "Ensuring superuser exists..."
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); import os; User.objects.filter(username=os.getenv('DJANGO_SUPERUSER_USERNAME')).exists() or os.system('python manage.py createsuperuser --noinput')"
else
    if [ -z "$DJANGO_SUPERUSER_USERNAME" ]; then echo "DEBUG: DJANGO_SUPERUSER_USERNAME is empty"; fi
    if [ -z "$DJANGO_SUPERUSER_PASSWORD" ]; then echo "DEBUG: DJANGO_SUPERUSER_PASSWORD is empty"; fi
    echo "Superuser credentials missing or incomplete, skipping creation."
fi

echo "Checking for seeded data..."
python manage.py shell -c "
from apps.academics.models import Subject
if Subject.objects.count() == 0:
    print('No data found — loading snapshot...')
    import subprocess
    subprocess.run(['python', 'manage.py', 'load_snapshot'], check=True)
else:
    print(f'Data already seeded ({Subject.objects.count()} subjects). Skipping.')
"


echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute the CMD
exec "$@"
