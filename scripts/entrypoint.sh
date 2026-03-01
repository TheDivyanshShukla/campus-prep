#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Support loading .env explicitly if needed, though load_dotenv in settings.py does it too
# export $(grep -v '^#' .env | xargs)

echo "--- Starting Entrypoint Script ---"
echo "DATABASE_URL is: $DATABASE_URL"

# Ensure data directory exists and is writable (crucial for SQLite)
mkdir -p /app/data
chmod 777 /app/data

# Wait for database if it's external (RDS/Postgres)
if [[ $DATABASE_URL == postgres* ]]; then
    echo "Waiting for PostgreSQL database..."
    # You could add a pg_isready check here if needed
fi

echo "Running migrations..."
# --fake-initial allows migration to succeed if tables already exist from a snapshot
python manage.py migrate --noinput --fake-initial

echo "Ensuring superuser exists..."
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); import os; User.objects.filter(username=os.getenv('DJANGO_SUPERUSER_USERNAME')).exists() or os.system('python manage.py createsuperuser --noinput')"
else
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
    print(f'Found snapshot {latest}. Checking if restoration is needed...')
    if Subject.objects.count() == 0:
        print(f'Database empty. Restoring {latest}...')
        subprocess.run(['python', 'manage.py', 'db_snapshot', 'recover', latest, '--no-input'], check=True)
    else:
        print('Data already present. Skipping snapshot restoration.')
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

echo "--- Entrypoint Completed, starting command ---"
# Execute the CMD
exec "$@"
