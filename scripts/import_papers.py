import os
import django
import sys
import sqlite3
import httpx
from dotenv import load_dotenv
from django.core.files.base import ContentFile
from django.db import transaction

# Load environment variables
load_dotenv()

# Setup Django environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.academics.models import Subject
from apps.content.models import ParsedDocument
from django.core.files.storage import default_storage

EXT_DB_PATH = r'c:\Users\shukl\Desktop\code\rgpv-live\.me\datamine\rgpv_papers.db'

def import_papers():
    if not os.path.exists(EXT_DB_PATH):
        print(f"Error: External database not found at {EXT_DB_PATH}")
        return

    # Verify storage backend
    print(f"Using storage backend: {type(default_storage).__name__}")
    if os.getenv('USE_S3') == 'True':
         print(f"S3/B2 Mode Active: Files will be uploaded to {os.getenv('B2_BUCKET_NAME')}")
    else:
         print("Local Storage Mode Active.")

    conn = sqlite3.connect(EXT_DB_PATH)
    cursor = conn.cursor()

    # Get all papers with subject and branch information
    query = """
    SELECT 
        p.id, p.label, p.year, p.month, p.pdf_url,
        s.code as subject_code, s.name as subject_name
    FROM papers p
    JOIN subjects s ON p.subject_id = s.id
    """
    cursor.execute(query)
    papers = cursor.fetchall()
    
    print(f"Found {len(papers)} papers in external database.")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    client = httpx.Client(timeout=30.0, follow_redirects=True, headers=headers)

    for p_id, label, year, month, pdf_url, sub_code, sub_name in papers:
        subjects = Subject.objects.filter(code__iexact=sub_code)
        
        if not subjects.exists():
            continue

        title = f"{label} ({month} {year})" if month else label
        
        # Check if already imported AND has file in current storage
        existing_doc = ParsedDocument.objects.filter(title=title, document_type='UNSOLVED_PYQ').first()
        if existing_doc and existing_doc.source_file and existing_doc.source_file.storage.exists(existing_doc.source_file.name):
            print(f"⏩ Paper '{title}' already exists in storage. Skipping.")
            continue

        print(f"📥 Processing '{title}' for Subject {sub_code}...")

        try:
            response = client.get(pdf_url)
            if response.status_code != 200:
                print(f"❌ Failed to download PDF for {title}: HTTP {response.status_code}")
                continue

            with transaction.atomic():
                if existing_doc:
                    doc = existing_doc
                else:
                    doc = ParsedDocument(
                        document_type='UNSOLVED_PYQ',
                        title=title,
                        year=year,
                        parsing_status='COMPLETED',
                        render_mode='DIRECT_PDF',
                        is_published=True,
                        is_premium=False
                    )
                
                # Save/Save Over
                file_name = os.path.basename(pdf_url)
                doc.source_file.save(file_name, ContentFile(response.content), save=True)
                
                if not existing_doc:
                    doc.subjects.set(subjects)
                    doc.save()

            print(f"✅ Successfully {'updated' if existing_doc else 'imported'} '{title}'")

        except Exception as e:
            print(f"❌ Error processing {title}: {e}")

    client.close()
    conn.close()
    print("Import process completed.")

if __name__ == "__main__":
    import_papers()
