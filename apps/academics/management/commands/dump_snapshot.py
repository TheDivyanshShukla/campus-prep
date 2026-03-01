import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.academics.models import Subject
from apps.content.models import ParsedDocument


class Command(BaseCommand):
    help = 'Dumps current DB state into data/snapshot/ (subjects.json + pyq_papers.json)'

    def handle(self, *args, **options):
        out_dir = os.path.join(settings.BASE_DIR, 'data', 'snapshot')
        os.makedirs(out_dir, exist_ok=True)

        # ── 1. Subjects ────────────────────────────────────────────────────────
        self.stdout.write("Dumping subjects...")
        subjects_out = []

        for s in Subject.objects.select_related('branch', 'semester').prefetch_related('units').order_by('branch__code', 'semester__number', 'code'):
            units = [
                {"number": u.number, "name": u.name, "topics": u.topics or []}
                for u in s.units.order_by('number')
            ]
            subjects_out.append({
                "branch_code": s.branch.code if s.branch else None,
                "branch_name": s.branch.name if s.branch else None,
                "semester": s.semester.number if s.semester else None,
                "code": s.code,
                "name": s.name,
                "units": units,
            })

        with open(os.path.join(out_dir, 'subjects.json'), 'w', encoding='utf-8') as f:
            json.dump(subjects_out, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(f"  {len(subjects_out)} subjects saved."))

        # ── 2. PYQ Papers ──────────────────────────────────────────────────────
        self.stdout.write("Dumping PYQ papers...")
        papers_out = []

        for doc in ParsedDocument.objects.filter(document_type='UNSOLVED_PYQ').prefetch_related('subjects').order_by('year', 'title'):
            papers_out.append({
                "title": doc.title,
                "year": doc.year,
                "document_type": doc.document_type,
                "render_mode": doc.render_mode,
                "is_published": doc.is_published,
                "source_file": doc.source_file.name if doc.source_file else None,
                "subject_codes": list(doc.subjects.values_list('code', flat=True)),
            })

        with open(os.path.join(out_dir, 'pyq_papers.json'), 'w', encoding='utf-8') as f:
            json.dump(papers_out, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(f"  {len(papers_out)} PYQ papers saved."))
        self.stdout.write(self.style.SUCCESS(f"Snapshot saved to {out_dir}"))
