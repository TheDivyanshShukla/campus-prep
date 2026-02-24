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
if [ "$DJANGO_SUPERUSER_USERNAME" != "" ] && [ "$DJANGO_SUPERUSER_PASSWORD" != "" ]; then
    python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); import os; User.objects.filter(username=os.getenv('DJANGO_SUPERUSER_USERNAME')).exists() or os.system('python manage.py createsuperuser --noinput')"
else
    echo "Superuser credentials not provided, skipping creation."
fi

echo "Checking for academic data..."
python manage.py shell -c "from apps.academics.models import Branch; import os; os.system('python manage.py seed_rgpv') if Branch.objects.count() == 0 else print('Academics data already exists.')"

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute the CMD
exec "$@"
