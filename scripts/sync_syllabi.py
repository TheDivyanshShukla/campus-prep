import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.content.models import ParsedDocument
from apps.content.services.syllabus_processor import SyllabusProcessor

def retroactive_sync():
    """
    Finds all successfully parsed syllabi and syncs them to Unit models.
    """
    syllabi = ParsedDocument.objects.filter(document_type='SYLLABUS', parsing_status='COMPLETED')
    print(f"Found {syllabi.count()} completed syllabi to sync.")
    
    processor = SyllabusProcessor()
    for doc in syllabi:
        print(f"Syncing syllabus: {doc.title} (ID: {doc.id})...")
        try:
            processor.sync_to_units(doc)
            print(f"✅ Successfully synced {doc.title}")
        except Exception as e:
            print(f"❌ Failed to sync {doc.title}: {e}")

if __name__ == "__main__":
    retroactive_sync()
