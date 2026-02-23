import os
import sys
import django
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'apps'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['USE_S3'] = 'True'
django.setup()

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

def test_upload():
    import time
    filename = f'test_b2_{int(time.time())}.txt'
    try:
        path = default_storage.save(filename, ContentFile('Hello Backblaze B2!'))
        print(f"Successfully uploaded to: {path}")
        url = default_storage.url(path)
        print(f"Public URL: {url}")
        
        # Verify existence
        if default_storage.exists(path):
            print("Verified: File exists in storage.")
            # Clean up
            default_storage.delete(path)
            print("Successfully deleted test file.")
        else:
            print("Error: File does not exist in storage after upload.")
            
    except Exception as e:
        import traceback
        print(f"Error during storage test: {e}")
        traceback.print_exc()

def test_boto3_direct():
    import boto3
    from botocore.config import Config
    
    print("\n--- Direct Boto3 Test ---")
    key_id = os.getenv('B2_ACCESS_KEY_ID')
    secret_key = os.getenv('B2_SECRET_ACCESS_KEY')
    print(f"Key ID Length: {len(key_id) if key_id else 'None'}")
    print(f"Secret Key Length: {len(secret_key) if secret_key else 'None'}")
    
    s3 = boto3.client(
        's3',
        endpoint_url=os.getenv('B2_ENDPOINT'),
        aws_access_key_id=os.getenv('B2_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('B2_SECRET_ACCESS_KEY'),
        region_name=os.getenv('B2_REGION'),
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
    )
    
    try:
        bucket = os.getenv('B2_BUCKET_NAME')
        print(f"Testing bucket: {bucket}")
        # Try listing objects instead of HeadObject
        response = s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        print("Successfully listed objects (at least the request worked).")
        
        # Try a simple put
        s3.put_object(Bucket=bucket, Key='boto3_test.txt', Body='Hello from Boto3')
        print("Successfully put object.")
        
        # Try head
        s3.head_object(Bucket=bucket, Key='boto3_test.txt')
        print("Successfully headed object.")
        
        # Cleanup
        s3.delete_object(Bucket=bucket, Key='boto3_test.txt')
        print("Successfully deleted object.")
        
    except Exception as e:
        print(f"Boto3 Direct Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_boto3_direct()
    # test_upload() # Disabled for now
