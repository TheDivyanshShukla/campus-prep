import os
import django
import sys
import boto3
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Django environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.apps import apps
from django.db import models

def _extract_paths(data, paths):
    """Recursively extract strings that look like file paths from JSON data."""
    if isinstance(data, dict):
        for v in data.values():
            _extract_paths(v, paths)
    elif isinstance(data, list):
        for item in data:
            _extract_paths(item, paths)
    elif isinstance(data, str):
        # Specific check for our recreated images or other uploaded docs
        if "recreated/" in data or "raw_docs/" in data:
            # Strip query params and protocol/domain if present
            path = data.split('?')[0]
            if "://" in path:
                path = path.split("/", 3)[-1]
            elif path.startswith("/media/"):
                path = path.replace("/media/", "", 1)
            paths.add(path)

def get_db_files():
    """
    Collect all file paths stored in the Django database.
    """
    db_files = set()
    for model in apps.get_models():
        file_fields = [f for f in model._meta.fields if isinstance(f, models.FileField)]
        json_fields = [f for f in model._meta.fields if isinstance(f, models.JSONField)]
        
        if not file_fields and not json_fields:
            continue
            
        # 1. Standard FileFields
        for field in file_fields:
            queryset = model.objects.exclude(**{f"{field.name}": ""}).values_list(field.name, flat=True)
            for path in queryset:
                if path:
                    db_files.add(str(path))
        
        # 2. JSONFields (Recursive search)
        for field in json_fields:
            queryset = model.objects.exclude(**{f"{field.name}": None}).values_list(field.name, flat=True)
            for data in queryset:
                if data:
                    _extract_paths(data, db_files)
                    
    return db_files

def cleanup_orphans(delete=False):
    key_id = os.getenv('B2_ACCESS_KEY_ID') or os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('B2_SECRET_ACCESS_KEY') or os.getenv('AWS_SECRET_ACCESS_KEY')
    bucket_name = os.getenv('B2_BUCKET_NAME') or os.getenv('AWS_STORAGE_BUCKET_NAME')
    region = os.getenv('B2_REGION') or os.getenv('AWS_S3_REGION_NAME')
    endpoint_url = os.getenv('B2_ENDPOINT') or os.getenv('AWS_S3_ENDPOINT_URL')

    if not all([key_id, secret_key, bucket_name]):
        print("❌ Error: Missing S3/B2 credentials.")
        return

    print(f"🔍 Collecting database files...")
    db_files = get_db_files()
    print(f"✅ Found {len(db_files)} files in database.")

    print(f"☁️ Listing objects in S3 bucket: {bucket_name}...")
    s3 = boto3.client(
        's3',
        aws_access_key_id=key_id,
        aws_secret_access_key=secret_key,
        region_name=region,
        endpoint_url=endpoint_url
    )

    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name)

    orphans = []
    total_objects = 0
    
    for page in pages:
        if 'Contents' in page:
            for obj in page['Contents']:
                key = obj['Key']
                total_objects += 1
                if key not in db_files:
                    orphans.append(key)

    print(f"📊 Summary:")
    print(f"   Total objects in S3: {total_objects}")
    print(f"   Total tracked in DB: {len(db_files)}")
    print(f"   Total orphans found: {len(orphans)}")

    if not orphans:
        print("✨ No orphaned files found.")
        return

    if not delete:
        print("\n📝 Orphaned Files (Dry Run):")
        for orphan in orphans[:20]: # Show first 20
            print(f"   - {orphan}")
        if len(orphans) > 20:
            print(f"   ... and {len(orphans) - 20} more.")
        print("\n⚠️  Run with --delete to permanently remove these files.")
    else:
        print(f"\n🗑️  Deleting {len(orphans)} orphaned files...")
        # Delete in batches of 1000 (S3 limit)
        for i in range(0, len(orphans), 1000):
            batch = orphans[i:i+1000]
            s3.delete_objects(
                Bucket=bucket_name,
                Delete={'Objects': [{'Key': k} for k in batch]}
            )
            print(f"   ✅ Deleted batch {i // 1000 + 1}...")
        print(f"🚀 Successfully removed {len(orphans)} orphans.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup orphaned files in S3.")
    parser.add_argument("--delete", action="store_true", help="Actually delete the files.")
    args = parser.parse_args()

    cleanup_orphans(delete=args.delete)
