import sqlite3
import os
import re
import asyncio
import httpx
from django.core.management.base import BaseCommand
from apps.academics.models import Subject
from apps.content.models import ParsedDocument
from django.conf import settings
from django.core.files.base import ContentFile

CONCURRENCY = 200


class Command(BaseCommand):
    help = 'Sync PYQ papers from rgpv_papers.db into ParsedDocument model'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None, help='Limit the number of papers to sync')
        parser.add_argument('--download', action='store_true', help='Download PDFs from URLs')

    # ------------------------------------------------------------------ #
    # Parsing helpers                                                       #
    # ------------------------------------------------------------------ #

    def parse_label(self, label):
        """
        Parses labels like:
          CS-CT-CO-IT-CI-CSIT-302-DISCRETE-STRUCTURE-JUN-2025
          BT-204-BASIC-CIVIL-ENGINEERING-JUN-2022
          AD-AL-AI-304-ARTIFICIAL-INTELLIGENCE-JUN-2025
        """
        parts = label.split('-')

        year = None
        month = None
        remaining_parts = parts
        if len(parts) >= 2:
            try:
                year = int(parts[-1])
                month = parts[-2]
                remaining_parts = parts[:-2]
            except ValueError:
                pass

        subject_codes = []
        name_parts = []

        # Find the first pure-numeric suffix (e.g. 302, 401)
        suffix_index = -1
        for i, part in enumerate(remaining_parts):
            if part.isdigit() and len(part) >= 3:
                suffix_index = i
                break

        if suffix_index != -1:
            prefixes = remaining_parts[:suffix_index]
            suffix = remaining_parts[suffix_index]
            subject_codes = [f"{p}{suffix}" for p in prefixes]
            name_parts = remaining_parts[suffix_index + 1:]
        elif len(remaining_parts) >= 2:
            subject_codes = [f"{remaining_parts[0]}{remaining_parts[1]}"]
            name_parts = remaining_parts[2:]

        title = " ".join(name_parts)
        if month and year:
            title = f"{title} - {month} {year}"

        return {
            'subject_codes': subject_codes,
            'title': title,
            'year': year,
            'month': month,
        }

    def normalize_string(self, text):
        if not text:
            return ""
        return re.sub(r'[^a-z0-9]', '', text.lower())

    # ------------------------------------------------------------------ #
    # Async download                                                        #
    # ------------------------------------------------------------------ #

    async def _download_one(self, client, sem, doc_id, url, filename):
        """Download a single PDF and save it to the model."""
        async with sem:
            try:
                r = await client.get(url, follow_redirects=True, timeout=30)
                if r.status_code == 200:
                    return doc_id, filename, r.content
                else:
                    return doc_id, None, f"HTTP {r.status_code}"
            except httpx.TimeoutException:
                return doc_id, None, "timeout"
            except Exception as e:
                return doc_id, None, str(e)

    async def _download_all(self, tasks):
        """
        tasks: list of (doc_id, url, filename)
        Returns: list of (doc_id, filename, content_or_error)
        """
        sem = asyncio.Semaphore(CONCURRENCY)
        limits = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=50)
        async with httpx.AsyncClient(limits=limits) as client:
            coros = [self._download_one(client, sem, doc_id, url, fn) for doc_id, url, fn in tasks]
            return await asyncio.gather(*coros)

    # ------------------------------------------------------------------ #
    # Main handler                                                          #
    # ------------------------------------------------------------------ #

    def handle(self, *args, **options):
        db_path = os.path.join(settings.BASE_DIR, '.me', 'datamine', 'rgpv_papers.db')
        if not os.path.exists(db_path):
            self.stdout.write(self.style.ERROR(f"Database not found at {db_path}"))
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        self.stdout.write(self.style.NOTICE("Fetching papers from SQLite..."))

        query = "SELECT label, year, pdf_url FROM papers"
        if options['limit']:
            query += f" LIMIT {options['limit']}"
        cursor.execute(query)
        papers_data = cursor.fetchall()
        conn.close()

        self.stdout.write(f"Processing {len(papers_data)} papers...")

        sync_count = 0
        skip_count = 0
        download_tasks = []  # (doc_id, url, filename)
        synced_this_run = set()  # (title, year) -> guard against cleanup deleting freshly-synced docs

        # Pre-fetch all subjects → normalize name → list[Subject]
        all_subjects = list(Subject.objects.all())
        subject_cache = {}   # normalized_name -> [Subject]
        prefix_cache = {}    # normalized_bare_code -> [Subject]
        code_exact = {}      # normalized_code (no spaces/hyphens) -> [Subject]
        num_cache = {}       # (branch_code, '702') -> [Subject] for elective garbage codes
        for s in all_subjects:
            norm = self.normalize_string(s.name)
            subject_cache.setdefault(norm, []).append(s)
            # Normalized exact code (strip all spaces/hyphens)
            norm_code = re.sub(r'[\s\-]', '', s.code)
            code_exact.setdefault(norm_code, []).append(s)
            # Strip trailing parenthetical like " (A)" or "(B)"
            bare_raw = re.sub(r'\s*\([^)]*\)$', '', s.code).strip()
            bare = re.sub(r'[\s\-]', '', bare_raw)
            if bare != norm_code:
                prefix_cache.setdefault(bare, []).append(s)
            # num_cache: for elective subjects with garbage codes like 'Departmental Elective-702 (A)'
            # Key by (branch_code, number) to avoid cross-branch false matches
            m = re.search(r'(\d{3,})', s.code)
            if m and s.branch:
                num_cache.setdefault((s.branch.code, m.group(1)), []).append(s)


        for p_label, p_year, p_pdf_url in papers_data:
            parsed = self.parse_label(p_label)
            year = p_year if p_year and p_year > 0 else parsed['year']

            # 1. Exact code match (both raw and normalized - handles "EC- 503" -> "EC503")
            codes = [c.replace('-', '') for c in parsed['subject_codes']]
            django_subjects = list(Subject.objects.filter(code__in=codes))
            for code in codes:
                for nm in code_exact.get(code, []):
                    if nm not in django_subjects:
                        django_subjects.append(nm)

            # 2. Prefix match for elective codes like CY503(B) stored as CY503 in the label
            for code in codes:
                for nm in prefix_cache.get(code, []):
                    if nm not in django_subjects:
                        django_subjects.append(nm)

            # 3. num_cache: match by (branch_code, 3-digit-num) for garbage elective codes
            # e.g. paper 'AD702' -> branch prefix 'AD', num '702' -> finds 'Departmental Elective-702 (A)' in AD branch
            for code in codes:
                m = re.search(r'(\d{3,})$', code)
                alpha = re.match(r'^([A-Z]+)', code)
                if m and alpha:
                    branch_prefix = alpha.group(1)
                    num = m.group(1)
                    for nm in num_cache.get((branch_prefix, num), []):
                        if nm not in django_subjects:
                            django_subjects.append(nm)

            # 4. Name-based fallback
            title_norm = self.normalize_string(parsed['title'].split(' - ')[0])
            for nm in subject_cache.get(title_norm, []):
                if nm not in django_subjects:
                    django_subjects.append(nm)

            if not django_subjects:
                skip_count += 1
                # Clean up false doc from previous buggy run — but ONLY if we didn't sync it this run
                doc_key = (parsed['title'], year)
                if doc_key not in synced_this_run:
                    existing = ParsedDocument.objects.filter(
                        title=parsed['title'], year=year, document_type='UNSOLVED_PYQ'
                    ).first()
                    if existing:
                        if existing.source_file:
                            existing.source_file.delete(save=False)
                        existing.delete()
                continue


            doc, created = ParsedDocument.objects.update_or_create(
                title=parsed['title'],
                year=year,
                defaults={
                    'document_type': 'UNSOLVED_PYQ',
                    'render_mode': 'DIRECT_PDF',
                    'is_published': True,
                }
            )
            doc.subjects.set(django_subjects)
            synced_this_run.add((parsed['title'], year))

            if created:
                sync_count += 1

            # Queue download only if requested AND file not already saved
            if options['download'] and p_pdf_url and not doc.source_file:
                filename = f"{p_label}.pdf".lower()
                download_tasks.append((doc.id, p_pdf_url, filename))

        self.stdout.write(
            self.style.SUCCESS(f"Synced {sync_count} new | Skipped {skip_count} | "
                               f"Queued {len(download_tasks)} downloads")
        )

        # ---- async batch download ----
        if download_tasks:
            self.stdout.write(f"Downloading {len(download_tasks)} PDFs ({CONCURRENCY} concurrent)...")
            results = asyncio.run(self._download_all(download_tasks))

            ok = 0
            fail = 0
            for doc_id, filename, payload in results:
                if filename and isinstance(payload, bytes):
                    try:
                        doc = ParsedDocument.objects.get(id=doc_id)
                        doc.source_file.save(filename, ContentFile(payload), save=True)
                        ok += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Save error for {filename}: {e}"))
                        fail += 1
                else:
                    fail += 1
                    self.stdout.write(self.style.WARNING(f"Download failed [{doc_id}]: {payload}"))

            self.stdout.write(self.style.SUCCESS(f"Downloads: {ok} ok, {fail} failed"))
