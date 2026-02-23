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

echo "Checking for academic data..."
python manage.py shell -c "from apps.academics.models import Branch; import os; os.system('python manage.py seed_rgpv') if Branch.objects.count() == 0 else print('Academics data already exists.')"

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute the CMD
exec "$@"
