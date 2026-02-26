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
from django.db import transaction

def set_native_render():
    docs = ParsedDocument.objects.all()
    print(f"Analyzing {docs.count()} documents...")

    # Filter for documents that are NOT already in NATIVE mode
    docs_to_update = list(ParsedDocument.objects.exclude(render_mode='NATIVE'))
    
    if not docs_to_update:
        print("No documents need a render mode update.")
        return

    print(f"Updating {len(docs_to_update)} documents to 'NATIVE' render mode...")
    
    for doc in docs_to_update:
        doc.render_mode = 'NATIVE'

    try:
        with transaction.atomic():
            ParsedDocument.objects.bulk_update(docs_to_update, ['render_mode'])
        print(f"Successfully updated {len(docs_to_update)} documents to NATIVE mode.")
    except Exception as e:
        print(f"Error during update: {e}")

if __name__ == "__main__":
    set_native_render()
