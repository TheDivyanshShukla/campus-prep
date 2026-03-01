import os
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from apps.academics.models import Branch, Semester, Subject, Unit

class Command(BaseCommand):
    help = 'Clears and seeds the database with RGPV data from JSON files in data/seed/'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear existing Subjects and Units before seeding')

    def handle(self, *args, **options):
        self.stdout.write("Starting Clean RGPV Data Seeding Process...")

        if options['clear']:
            self.stdout.write(self.style.WARNING("Clearing existing Subjects and Units..."))
            Unit.objects.all().delete()
            Subject.objects.all().delete()

        # 1. Base Setup (Semesters and Branches)
        self.seed_base_academics()

        # 2. Seed First Year (Group A/B logic)
        self.seed_first_year()

        # 3. Seed Branch-Specific Years (3-8 Semester)
        self.seed_branch_specific_years()

        self.stdout.write(self.style.SUCCESS("RGPV Seeding Completed Successfully!"))

    def seed_base_academics(self):
        self.stdout.write("Ensuring Semesters exist...")
        for i in range(1, 9):
            Semester.objects.get_or_create(number=i)

        self.stdout.write("Ensuring Branches exist...")
        branches_data = [
            ("Computer Science & Engineering", "CSE"),
            ("Information Technology", "IT"),
            ("Electronics & Communication Engineering", "ECE"),
            ("Mechanical Engineering", "ME"),
            ("Civil Engineering", "CE"),
            ("Electrical & Electronics Engineering", "EX"),
            ("Artificial Intelligence & Data Science", "AD"),
            ("Artificial Intelligence & Machine Learning", "AIML"),
            ("Cyber Security", "CY"),
            ("Automobile Engineering", "AU"),
        ]
        for name, code in branches_data:
            Branch.objects.get_or_create(code=code, defaults={'name': name})

    def seed_first_year(self):
        self.stdout.write("Seeding First Year Subjects with precise Group A/B mapping...")
        
        # Group A: CSE, IT, EX
        group_a = ['CSE', 'IT', 'EX']
        # Group B: Everyone else
        all_branches = list(Branch.objects.values_list('code', flat=True))
        group_b = [b for b in all_branches if b not in group_a]

        # Subject Code Classifications
        PHYSICS_CODES = {'BT201', 'BT102', 'BT203', 'BT204', 'BT205', 'BT206'}
        CHEMISTRY_CODES = {'BT101', 'BT202', 'BT103', 'BT104', 'BT105', 'BT106', 'BT107', 'BT108'}

        data_path = os.path.join(settings.BASE_DIR, 'data', 'seed', 'first_year')
        
        sem1_file = os.path.join(data_path, '1 st Semester', 'AB_group.json')
        sem2_file = os.path.join(data_path, '2 nd Semester', 'AB_group.json')

        if not os.path.exists(sem1_file) or not os.path.exists(sem2_file):
            self.stdout.write(self.style.ERROR("First year data files missing!"))
            return

        with open(sem1_file, 'r', encoding='utf-8') as f:
            sem1_data = json.load(f)
        with open(sem2_file, 'r', encoding='utf-8') as f:
            sem2_data = json.load(f)

        semesters = {s.number: s for s in Semester.objects.all()}
        branches = {b.code: b for b in Branch.objects.all()}

        # Core logic:
        # Group A: Sem 1 -> Chemistry, Sem 2 -> Physics
        # Group B: Sem 1 -> Physics, Sem 2 -> Chemistry

        for sem_data, sem_num in [(sem1_data, 1), (sem2_data, 2)]:
            for subject_data in sem_data.get('subjects', []):
                code = subject_data['subject_code']
                
                target_branches = []
                # Check which group this subject belongs to
                if code in CHEMISTRY_CODES:
                    # Chemistry subjects are taken in Sem 1 by Group A, and Sem 2 by Group B
                    if sem_num == 1: target_branches = group_a
                    else: target_branches = group_b
                elif code in PHYSICS_CODES:
                    # Physics subjects are taken in Sem 1 by Group B, and Sem 2 by Group A
                    if sem_num == 1: target_branches = group_b
                    else: target_branches = group_a
                
                for b_code in target_branches:
                    if b_code in branches:
                        self.create_subject_with_units(subject_data, branches[b_code], semesters[sem_num])

    def seed_branch_specific_years(self):
        self.stdout.write("Seeding Branch-Specific Years (3-8)...")
        data_root = os.path.join(settings.BASE_DIR, 'data', 'seed')
        
        branches = {b.code: b for b in Branch.objects.all()}
        semesters = {s.number: s for s in Semester.objects.all()}

        for b_code, branch_instance in branches.items():
            branch_dir = os.path.join(data_root, b_code)
            if not os.path.exists(branch_dir):
                continue
            
            for sem_num in range(3, 9):
                # Handle directory naming variants
                possible_names = [f"{sem_num} rd Semester", f"{sem_num} th Semester", f"{sem_num}rd Semester", f"{sem_num}th Semester"]
                sem_dir = None
                for name in possible_names:
                    temp_dir = os.path.join(branch_dir, name)
                    if os.path.exists(temp_dir):
                        sem_dir = temp_dir
                        break
                
                if not sem_dir:
                    continue
                
                for file_name in os.listdir(sem_dir):
                    if file_name.endswith('.json'):
                        file_path = os.path.join(sem_dir, file_name)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        for subject_data in data.get('subjects', []):
                            # Filter out potentially duplicated first-year subjects if they leaked into branch folders
                            if subject_data['subject_code'].startswith('BT'):
                                continue
                            self.create_subject_with_units(subject_data, branch_instance, semesters[sem_num])

    def create_subject_with_units(self, subject_data, branch, semester):
        code = subject_data['subject_code']
        name = subject_data['subject_name']
        
        if len(code) > 20:
            self.stdout.write(self.style.WARNING(f"Truncating code: '{code}' -> '{code[:20]}'"))
            code = code[:20]

        with transaction.atomic():
            subject, created = Subject.objects.get_or_create(
                branch=branch,
                semester=semester,
                code=code,
                defaults={'name': name}
            )
            
            if not created and subject.name != name:
                subject.name = name
                subject.save()

            # Bulk operations for units
            existing_units = {u.number: u for u in subject.units.all()}
            units_to_create = []
            units_to_update = []

            for module in subject_data.get('modules', []):
                unit_num = module.get('unit')
                # Only seed units 1-5 for consistency unless more are specified
                if not unit_num: continue
                
                unit_name = module.get('title', f"Unit {unit_num}")
                topics = module.get('topics', [])
                
                if unit_num in existing_units:
                    unit = existing_units[unit_num]
                    if unit.name != unit_name or unit.topics != topics:
                        unit.name = unit_name
                        unit.topics = topics
                        units_to_update.append(unit)
                else:
                    units_to_create.append(Unit(
                        subject=subject,
                        number=unit_num,
                        name=unit_name,
                        topics=topics
                    ))

            if units_to_create:
                Unit.objects.bulk_create(units_to_create)
            if units_to_update:
                Unit.objects.bulk_update(units_to_update, ['name', 'topics'])

