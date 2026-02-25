import os
import boto3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def clear_s3_bucket():
    """
    Deletes all objects from the S3 bucket configured in environment variables.
    Works with S3-compatible storage like Backblaze B2.
    """
    key_id = os.getenv('B2_ACCESS_KEY_ID') or os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('B2_SECRET_ACCESS_KEY') or os.getenv('AWS_SECRET_ACCESS_KEY')
    bucket_name = os.getenv('B2_BUCKET_NAME') or os.getenv('AWS_STORAGE_BUCKET_NAME')
    region = os.getenv('B2_REGION') or os.getenv('AWS_S3_REGION_NAME')
    endpoint_url = os.getenv('B2_ENDPOINT') or os.getenv('AWS_S3_ENDPOINT_URL')

    if not all([key_id, secret_key, bucket_name]):
        print("❌ Error: Missing S3/B2 credentials in environment variables.")
        return

    print(f"🧹 Initializing cleanup for bucket: {bucket_name}")
    print(f"📍 Endpoint: {endpoint_url}")

    # Initialize S3 client
    s3 = boto3.client(
        's3',
        aws_access_key_id=key_id,
        aws_secret_access_key=secret_key,
        region_name=region,
        endpoint_url=endpoint_url
    )

    try:
        # List all objects in the bucket
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name)

        deleted_count = 0
        for page in pages:
            if 'Contents' in page:
                delete_batch = {'Objects': [{'Key': obj['Key']} for obj in page['Contents']]}
                s3.delete_objects(Bucket=bucket_name, Delete=delete_batch)
                batch_count = len(page['Contents'])
                deleted_count += batch_count
                print(f"✅ Deleted {batch_count} objects...")

        if deleted_count == 0:
            print("✨ Bucket is already empty.")
        else:
            print(f"🚀 Successfully cleared total {deleted_count} objects from {bucket_name}.")

    except Exception as e:
        print(f"❌ Failed to clear bucket: {str(e)}")

if __name__ == "__main__":
    confirm = input(f"⚠️  Are you sure you want to PERMANENTLY DELETE EVERYTHING from the S3 bucket? (y/N): ")
    if confirm.lower() == 'y':
        clear_s3_bucket()
    else:
        print("❌ Cleanup cancelled.")
