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

echo "Checking for seeded data or snapshots..."
cat << 'EOF' | python manage.py shell
import os
import glob
import subprocess
from apps.academics.models import Subject

# Check for snapshots first
snapshot_dir = 'data/snapshots'
snapshots = glob.glob(os.path.join(snapshot_dir, 'snapshot_*.json'))

if snapshots:
    # Sort and get the latest
    snapshots.sort(key=os.path.getmtime)
    latest = os.path.basename(snapshots[-1])
    print(f'Found snapshot {latest}. Restoring...')
    subprocess.run(['python', 'manage.py', 'db_snapshot', 'recover', latest, '--no-input'], check=True)
elif Subject.objects.count() == 0:
    print('No snapshots and no data found. Running initial seed...')
    subprocess.run(['python', 'manage.py', 'seed_rgpv'], check=True)
    print('Downloading PYQs...')
    subprocess.run(['python', 'manage.py', 'sync_pyq_papers', '--download'], check=True)
else:
    print(f'Data already seeded ({Subject.objects.count()} subjects). Skipping.')
EOF


echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute the CMD
exec "$@"
