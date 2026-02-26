import os
import django
import sys
import re
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'apps'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.academics.models import Subject
from apps.content.models import ParsedDocument
from django.db import transaction

def recover_links():
    from collections import defaultdict
    docs = ParsedDocument.objects.all()
    print(f"🔍 Analyzing {docs.count()} documents...")

    # Index subjects by code (one code can belong to multiple branch variants)
    subjects_by_code = defaultdict(list)
    for s in Subject.objects.all():
        subjects_by_code[s.code.strip().upper()].append(s)
    
    print(f"📚 {len(subjects_by_code)} unique subject codes indexed.")

    new_links = []
    seen_links = set() # To prevent adding same (doc, sub) multiple times in one run
    failed_titles = []
    
    ThroughModel = ParsedDocument.subjects.through

    for doc in docs:
        title = doc.title
        # Extract code pattern: e.g., AU-ME-302, CS-301, BT-101
        match = re.match(r'^([A-Z-]+)-(\d+)', title)
        
        if match:
            prefixes_str = match.group(1) # e.g. "AU-ME"
            num = match.group(2)          # e.g. "302"
            
            prefixes = prefixes_str.split('-')
            found_subjects = []
            
            for p in prefixes:
                code_to_try = f"{p}-{num}".upper()
                matches = subjects_by_code.get(code_to_check := code_to_try.strip())
                if matches:
                    found_subjects.extend(matches)
            
            if found_subjects:
                for sub in found_subjects:
                    link_key = (doc.id, sub.id)
                    if link_key not in seen_links:
                        new_links.append(ThroughModel(parseddocument_id=doc.id, subject_id=sub.id))
                        seen_links.add(link_key)
                
                codes_found = ", ".join(set([s.code for s in found_subjects]))
                print(f"✅ Document {doc.id} mapped to subjects: {codes_found}")
            else:
                failed_titles.append(title)
        else:
            failed_titles.append(title)

    if new_links:
        print(f"\n🚀 Bulk creating {len(new_links)} subject links...")
        with transaction.atomic():
            ThroughModel.objects.bulk_create(new_links, ignore_conflicts=True)
        print("✨ Link recovery successful!")
    else:
        print("\nℹ️ No new links were identified.")

    if failed_titles:
        print(f"\n⚠️  Could not match {len(failed_titles)} titles. Samples:")
        for t in failed_titles[:5]:
            print(f"  - {t}")

    print(f"\n📊 Summary: {len(new_links)} new links created.")

if __name__ == "__main__":
    recover_links()
