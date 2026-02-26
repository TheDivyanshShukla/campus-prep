import os
import django
import sys
import asyncio
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'apps'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.content.models import ParsedDocument
from apps.content.services.image_recreator import ImageRecreationService
from asgiref.sync import sync_to_async

async def heal_documents():
    docs = await sync_to_async(lambda: list(ParsedDocument.objects.filter(parsing_status='COMPLETED')))()
    print(f"🚀 Starting Image Healing for {len(docs)} documents...")

    for doc in docs:
        if not doc.structured_data:
            continue
        
        recreator = ImageRecreationService(doc_obj=doc)
        print(f"📦 Processing '{doc.title}' (ID: {doc.id})")
        
        # The process_structured_data method recursively finds and processes CANVAS/SEARCH
        # It updates the data in-place
        old_data = doc.structured_data
        updated_data = await recreator.process_structured_data(old_data)
        
        # Save the updated data
        doc.structured_data = updated_data
        await sync_to_async(doc.save)(update_fields=['structured_data', 'recreation_completed_images', 'recreation_total_images'])
        
        print(f"✅ Finished '{doc.title}'")

if __name__ == "__main__":
    try:
        asyncio.run(heal_documents())
        print("\n✨ Healing process completed successfully!")
    except Exception as e:
        print(f"❌ Error during healing: {e}")
