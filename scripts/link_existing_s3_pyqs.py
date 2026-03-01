import os
import django
import sys
import boto3
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Django environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.content.models import ParsedDocument

def normalize_string(text):
    if not text:
        return ""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def parse_label(label):
    parts = label.split('-')
    year = None
    month = None
    remaining_parts = list(parts)
    if len(parts) >= 2:
        try:
            # Handle cases like JUN-2025 or DEC-2024
            if parts[-1].isdigit() and len(parts[-1]) == 4:
                year = int(parts[-1])
                month = parts[-2]
                remaining_parts = parts[:-2]
        except ValueError:
            pass

    suffix_index = -1
    for i, part in enumerate(remaining_parts):
        if part.isdigit() and len(part) >= 3:
            suffix_index = i
            break

    if suffix_index != -1:
        name_parts = remaining_parts[suffix_index + 1:]
    elif len(remaining_parts) >= 2:
        # Fallback if no 3-digit number found
        name_parts = remaining_parts[2:]
    else:
        name_parts = remaining_parts

    title = " ".join(name_parts).strip()
    return title, year, month

def link_s3_files():
    key_id = os.getenv('B2_ACCESS_KEY_ID') or os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('B2_SECRET_ACCESS_KEY') or os.getenv('AWS_SECRET_ACCESS_KEY')
    bucket_name = os.getenv('B2_BUCKET_NAME') or os.getenv('AWS_STORAGE_BUCKET_NAME')
    region = os.getenv('B2_REGION') or os.getenv('AWS_S3_REGION_NAME')
    endpoint_url = os.getenv('B2_ENDPOINT') or os.getenv('AWS_S3_ENDPOINT_URL')

    if not all([key_id, secret_key, bucket_name]):
        print("❌ Error: Missing S3/B2 credentials.")
        return

    s3 = boto3.client(
        's3',
        aws_access_key_id=key_id,
        aws_secret_access_key=secret_key,
        region_name=region,
        endpoint_url=endpoint_url
    )

    print(f"☁️ Listing objects in S3 bucket: {bucket_name}...")
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name, Prefix='raw_docs/')

    print("📊 Loading ParsedDocuments into memory...")
    all_docs = list(ParsedDocument.objects.filter(document_type='UNSOLVED_PYQ'))
    doc_cache = {} # (normalized_title, year) -> list[ParsedDocument]
    for d in all_docs:
        # Normalize the title for comparison
        norm_title = normalize_string(d.title)
        key = (norm_title, d.year)
        doc_cache.setdefault(key, []).append(d)

    linked_count = 0
    total_files = 0
    already_linked = 0
    no_match = 0

    for page in pages:
        if 'Contents' in page:
            for obj in page['Contents']:
                key = obj['Key']
                if not key.lower().endswith('.pdf'):
                    continue
                
                total_files += 1
                # Extract label from key: raw_docs/LABEL.pdf -> LABEL
                label = os.path.basename(key).rsplit('.', 1)[0]
                title_part, year, month = parse_label(label)
                
                # Reconstruct the full title string as it appears in DB
                full_title = f"{title_part}"
                if month and year:
                    full_title = f"{title_part} - {month} {year}"
                
                norm_full_title = normalize_string(full_title)
                match_key = (norm_full_title, year)
                
                docs = doc_cache.get(match_key, [])
                
                if docs:
                    for doc in docs:
                        if not doc.source_file:
                            doc.source_file = key
                            doc.save(update_fields=['source_file'])
                            linked_count += 1
                        else:
                            already_linked += 1
                else:
                    no_match += 1
                
    print(f"\n📊 Final Summary:")
    print(f"   Total S3 PDFs found: {total_files}")
    print(f"   Successfully linked: {linked_count}")
    print(f"   Already linked:      {already_linked}")
    print(f"   No match found:      {no_match}")

if __name__ == "__main__":
    link_s3_files()
