import os
import django
import sys
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'apps'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.content.models import ParsedDocument
from apps.content.tasks import process_document_ai

def trigger_reparse_all():
    # We only re-parse documents that have a source_file or source_text
    docs = ParsedDocument.objects.filter(parsing_status__in=['COMPLETED', 'FAILED', 'PENDING', 'PROCESSING'])
    
    # Actually, we need a source file to re-parse (unless it's text-based)
    # If the user already cleared some source_files, those cannot be re-parsed.
    docs_with_source = docs.exclude(source_file='', source_text='')
    
    print(f"Resetting and queueing {docs_with_source.count()} documents for re-parsing...")
    
    for doc in docs_with_source:
        print(f"Queuing: {doc.title} (ID: {doc.id})")
        doc.parsing_status = 'PENDING'
        doc.save(update_fields=['parsing_status'])
        process_document_ai.delay(doc.id)

    print("\n✅ All eligible documents have been queued for re-parsing.")
    print("⚠️  Note: Documents without a source file (already cleared) were skipped.")

if __name__ == "__main__":
    trigger_reparse_all()
