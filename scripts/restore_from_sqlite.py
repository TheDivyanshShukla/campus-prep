import os
import django
import sqlite3
import sys
import json
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'apps'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.academics.models import Branch, Semester, Subject, Unit
from django.db import transaction

def restore():
    sqlite_db = BASE_DIR / 'db.sqlite3'
    if not sqlite_db.exists():
        print(f"❌ Error: {sqlite_db} not found")
        return

    conn = sqlite3.connect(sqlite_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        with transaction.atomic():
            print("🧹 Preparing destination tables (ensuring they are empty)...")
            Unit.objects.all().delete()
            Subject.objects.all().delete()
            Semester.objects.all().delete()
            Branch.objects.all().delete()

            print("🏢 Restoring Branches (Bulk)...")
            cursor.execute("SELECT * FROM academics_branch")
            branches = [
                Branch(id=row['id'], name=row['name'], code=row['code'], is_active=row['is_active'])
                for row in cursor.fetchall()
            ]
            Branch.objects.bulk_create(branches)

            print("📅 Restoring Semesters (Bulk)...")
            cursor.execute("SELECT * FROM academics_semester")
            semesters = [
                Semester(id=row['id'], number=row['number'], is_active=row['is_active'])
                for row in cursor.fetchall()
            ]
            Semester.objects.bulk_create(semesters)

            print("📚 Restoring Subjects (Bulk)...")
            cursor.execute("SELECT * FROM academics_subject")
            subjects = [
                Subject(
                    id=row['id'],
                    branch_id=row['branch_id'],
                    semester_id=row['semester_id'],
                    code=row['code'],
                    name=row['name'],
                    description=row['description'],
                    is_active=row['is_active']
                )
                for row in cursor.fetchall()
            ]
            Subject.objects.bulk_create(subjects)

            print("📑 Restoring Units (Bulk)...")
            cursor.execute("SELECT * FROM academics_unit")
            units = []
            for row in cursor.fetchall():
                topics = row['topics']
                if isinstance(topics, str):
                    topics = json.loads(topics)
                
                units.append(Unit(
                    id=row['id'],
                    subject_id=row['subject_id'],
                    number=row['number'],
                    name=row['name'],
                    description=row['description'],
                    topics=topics
                ))
            Unit.objects.bulk_create(units)

            print("\n✨ Bulk Data Restoration successfully completed!")
            print(f"📊 Restored: {len(branches)} Branches, {len(semesters)} Semesters, {len(subjects)} Subjects, {len(units)} Units.")
            
    except Exception as e:
        print(f"❌ Error during restoration: {e}")
        # Transaction will naturally rollback on exception
    finally:
        conn.close()

if __name__ == "__main__":
    restore()

if __name__ == "__main__":
    restore()
