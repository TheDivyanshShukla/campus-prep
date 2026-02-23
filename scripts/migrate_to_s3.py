import os
import sys
import django
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'apps'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
# Force S3 storage for the migration script
os.environ['USE_S3'] = 'True'
django.setup()

from django.core.files.storage import FileSystemStorage
from storages.backends.s3 import S3Storage
from apps.content.models import ParsedDocument, DocumentImage

def migrate_files():
    local_storage = FileSystemStorage()
    s3_storage = S3Storage()
    
    print("Starting migration to S3...")
    
    # List of (Model, field_name)
    targets = [
        (ParsedDocument, 'source_file'),
        (DocumentImage, 'image'),
    ]
    
    total_migrated = 0
    total_skipped = 0
    total_error = 0
    
    for model, field_name in targets:
        print(f"\nProcessing {model.__name__}...")
        queryset = model.objects.exclude(**{f"{field_name}": ""})
        
        for obj in queryset:
            file_field = getattr(obj, field_name)
            if not file_field:
                continue
                
            name = file_field.name
            
            # Check if already in S3
            if s3_storage.exists(name):
                print(f"  [SKIPPED] Already in S3: {name}")
                total_skipped += 1
                continue
                
            # Check if exists locally
            if local_storage.exists(name):
                try:
                    print(f"  [MIGRATING] Uploading {name}...")
                    with local_storage.open(name, 'rb') as f:
                        s3_storage.save(name, f)
                    print(f"  [SUCCESS] Uploaded {name}")
                    total_migrated += 1
                except Exception as e:
                    print(f"  [ERROR] Failed to upload {name}: {e}")
                    total_error += 1
            else:
                print(f"  [WARNING] Local file not found: {name}")
                total_error += 1
                
    print("\nMigration Summary:")
    print(f"  Successfully Migrated: {total_migrated}")
    print(f"  Already in S3 (Skipped): {total_skipped}")
    print(f"  Errors/Missing: {total_error}")

if __name__ == "__main__":
    migrate_files()
