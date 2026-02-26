import os
import django
import json
import re
import sys
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'apps'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from apps.academics.models import Branch, Semester, Subject, Unit

ROMAN_TO_INT = {
    'I': 1, 'II': 2, 'III': 3, 'IV': 4,
    'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8
}

def get_semester_number(sem_name):
    """Extract Roman numeral and convert to integer."""
    match = re.search(r'\b([IVX]+)\b', sem_name.upper())
    if match:
        roman = match.group(1)
        return ROMAN_TO_INT.get(roman)
    return None

def get_branch_info(branch_name):
    """Split 'Mechanical Engineering(ME)' into ('Mechanical Engineering', 'ME')."""
    match = re.search(r'^(.*?)\((.*?)\)$', branch_name)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return branch_name.strip(), branch_name.strip()[:10]

def import_syllabus_data():
    json_path = BASE_DIR / '.me' / 'datamine' / 'rgpv_syllabus_data.json'
    
    if not json_path.exists():
        print(f"❌ Error: JSON file not found at {json_path}")
        return

    print("🚀 Starting Syllabus Import...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    branches_data = data.get('branches', [])
    print(f"📂 Found {len(branches_data)} branches.")

    total_subjects = 0
    total_units = 0

    for b_data in branches_data:
        full_name, b_code = get_branch_info(b_data['name'])
        branch, _ = Branch.objects.get_or_create(code=b_code, defaults={'name': full_name})
        print(f"\n🏢 Branch: {branch}")

        for s_data in b_data.get('semesters', []):
            sem_num = get_semester_number(s_data['name'])
            if not sem_num:
                print(f"  ⚠️  Warning: Could not parse semester number from '{s_data['name']}'")
                continue

            semester, _ = Semester.objects.get_or_create(number=sem_num)
            
            with transaction.atomic():
                for sub_data in s_data.get('subjects', []):
                    sub_code = sub_data.get('code', 'UNKNOWN').strip()
                    sub_name = sub_data.get('name', '').strip()
                    
                    if sub_code == 'UNKNOWN' or not sub_name:
                        continue

                    subject, created = Subject.objects.get_or_create(
                        branch=branch,
                        semester=semester,
                        code=sub_code,
                        defaults={'name': sub_name}
                    )
                    
                    if created:
                        total_subjects += 1
                    
                    # Import Units (Modules)
                    current_units = 0
                    for mod_idx, mod_data in enumerate(sub_data.get('modules', [])):
                        title = mod_data.get('title', '').strip()
                        if not title or "END OF UNITS" in title.upper():
                            continue
                        
                        # Extract unit number
                        unit_num_match = re.search(r'(?:Module|Unit)\s*[-:]?\s*(\d+)', title, re.IGNORECASE)
                        unit_num = int(unit_num_match.group(1)) if unit_num_match else (current_units + 1)
                        
                        unit, u_created = Unit.objects.get_or_create(
                            subject=subject,
                            number=unit_num,
                            defaults={
                                'name': title,
                                'topics': mod_data.get('topics', [])
                            }
                        )
                        if u_created:
                            current_units += 1
                            total_units += 1

                    if current_units > 0:
                        print(f"    ✅ [{subject.code}] {subject.name} ({current_units} units)")

    print(f"\n✨ Import Complete!")
    print(f"📊 Summary: {total_subjects} Subjects, {total_units} Units imported/checked.")

if __name__ == "__main__":
    import_syllabus_data()

if __name__ == "__main__":
    import_syllabus_data()
