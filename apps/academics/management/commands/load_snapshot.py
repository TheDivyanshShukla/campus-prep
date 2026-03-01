import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.core.files.base import ContentFile
from apps.academics.models import Branch, Semester, Subject, Unit
from apps.content.models import ParsedDocument


class Command(BaseCommand):
    help = 'Loads the DB snapshot from data/snapshot/ (subjects + PYQ papers)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing Subjects, Units, and PYQ ParsedDocuments before loading',
        )

    def handle(self, *args, **options):
        snapshot_dir = os.path.join(settings.BASE_DIR, 'data', 'snapshot')
        subjects_file = os.path.join(snapshot_dir, 'subjects.json')
        papers_file = os.path.join(snapshot_dir, 'pyq_papers.json')

        if not os.path.exists(subjects_file) or not os.path.exists(papers_file):
            self.stdout.write(self.style.ERROR(
                f"Snapshot files not found in {snapshot_dir}. "
                "Run .temp/dump_snapshot.py to create them first."
            ))
            return

        if options['clear']:
            self.stdout.write(self.style.WARNING("Clearing existing data..."))
            Unit.objects.all().delete()
            ParsedDocument.objects.filter(document_type='UNSOLVED_PYQ').delete()
            Subject.objects.all().delete()

        # ── 1. Ensure semesters exist ──────────────────────────────────────────
        for i in range(1, 9):
            Semester.objects.get_or_create(number=i)
        semesters = {s.number: s for s in Semester.objects.all()}

        # ── 2. Load subjects ───────────────────────────────────────────────────
        self.stdout.write("Loading subjects...")
        with open(subjects_file, 'r', encoding='utf-8') as f:
            subjects_data = json.load(f)

        branches = {}
        subject_map = {}  # code -> Subject (for paper linking)
        subject_count = 0
        unit_count = 0

        with transaction.atomic():
            for item in subjects_data:
                b_code = item['branch_code']
                b_name = item.get('branch_name', b_code)
                sem_num = item['semester']

                # Ensure branch
                if b_code not in branches:
                    branch, _ = Branch.objects.get_or_create(
                        code=b_code, defaults={'name': b_name}
                    )
                    branches[b_code] = branch

                branch = branches[b_code]
                semester = semesters.get(sem_num)
                if not semester:
                    continue

                subject, created = Subject.objects.get_or_create(
                    code=item['code'],
                    branch=branch,
                    semester=semester,
                    defaults={'name': item['name']},
                )
                if not created and subject.name != item['name']:
                    subject.name = item['name']
                    subject.save()

                subject_map[item['code']] = subject
                if created:
                    subject_count += 1

                # Units
                existing_units = {u.number: u for u in subject.units.all()}
                for u_data in item.get('units', []):
                    unum = u_data['number']
                    uname = u_data.get('name', f"Unit {unum}")
                    utopics = u_data.get('topics', [])
                    if unum in existing_units:
                        u = existing_units[unum]
                        if u.name != uname or u.topics != utopics:
                            u.name = uname
                            u.topics = utopics
                            u.save()
                    else:
                        Unit.objects.create(
                            subject=subject, number=unum,
                            name=uname, topics=utopics
                        )
                        unit_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"  {subject_count} new subjects | {unit_count} new units"
        ))

        # ── 3. Load PYQ papers ─────────────────────────────────────────────────
        self.stdout.write("Loading PYQ papers...")
        with open(papers_file, 'r', encoding='utf-8') as f:
            papers_data = json.load(f)

        paper_count = 0

        with transaction.atomic():
            for item in papers_data:
                subject_codes = item.get('subject_codes', [])
                linked_subjects = [
                    subject_map[c] for c in subject_codes if c in subject_map
                ]
                if not linked_subjects:
                    continue

                doc, created = ParsedDocument.objects.get_or_create(
                    title=item['title'],
                    year=item.get('year'),
                    document_type='UNSOLVED_PYQ',
                    defaults={
                        'render_mode': item.get('render_mode', 'DIRECT_PDF'),
                        'is_published': item.get('is_published', True),
                    }
                )
                doc.subjects.set(linked_subjects)

                # Restore source_file path if file exists on disk and doc has none
                file_name = item.get('source_file')
                if file_name and not doc.source_file:
                    media_root = settings.MEDIA_ROOT
                    full_path = os.path.join(media_root, file_name)
                    if os.path.exists(full_path):
                        doc.source_file.name = file_name
                        doc.save(update_fields=['source_file'])

                if created:
                    paper_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"  {paper_count} new PYQ papers loaded"
        ))
        self.stdout.write(self.style.SUCCESS("Snapshot loaded successfully!"))
