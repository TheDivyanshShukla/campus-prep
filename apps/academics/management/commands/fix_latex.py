"""
Management command: fix_latex
Validates all LaTeX in ParsedDocument records using KaTeX, then uses LLM to fix broken math.
Fully async — processes ALL documents in parallel via asyncio.gather.

Usage:
    uv run manage.py fix_latex --doc-type SHORT_NOTES
    uv run manage.py fix_latex --subject CS-601
    uv run manage.py fix_latex --dry-run
    uv run manage.py fix_latex --force
"""
import asyncio
import re
from django.core.management.base import BaseCommand
from asgiref.sync import sync_to_async
from apps.content.models import ParsedDocument
from apps.content.services.ai_parser.latex_fixer import LatexFixer, extract_math_blocks, validate_with_katex


class Command(BaseCommand):
    help = 'Validate and fix LaTeX in ParsedDocument records using KaTeX + LLM'

    def add_arguments(self, parser):
        parser.add_argument('--subject', type=str, help='Filter by subject code (e.g. CS-601)')
        parser.add_argument('--doc-type', type=str, help='Filter by document type (e.g. SHORT_NOTES, IMPORTANT_Q)')
        parser.add_argument('--doc-id', type=int, help='Fix a single document by ID')
        parser.add_argument('--dry-run', action='store_true', help='Only report errors, do not fix')
        parser.add_argument('--force', action='store_true', help='Re-process already validated documents')

    def handle(self, *args, **options):
        asyncio.run(self._run(options))

    async def _run(self, options):
        # Build queryset synchronously, then fetch all docs
        docs = await sync_to_async(self._get_docs)(options)
        total = len(docs)
        self.stdout.write(f"Found {total} documents to process")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to process."))
            return

        dry_run = options.get('dry_run', False)
        fixer = LatexFixer()

        # Phase 1: Extract + KaTeX validate ALL documents (sync, fast)
        self.stdout.write("Phase 1: Extracting math blocks and running KaTeX validation...")
        doc_tasks = []
        for doc in docs:
            data = doc.structured_data
            if not data:
                continue
            content_pieces = self._extract_content(data, doc.document_type)
            if not content_pieces:
                continue

            broken_pieces = []
            for key, content in content_pieces:
                blocks = extract_math_blocks(content)
                if not blocks:
                    continue
                results = validate_with_katex(blocks)
                broken = [r for r in results if not r.get('valid')]
                if broken:
                    errors_by_id = {r['id']: r.get('error', '') for r in broken}
                    broken_piece_blocks = [b for b in blocks if b['id'] in errors_by_id]
                    broken_pieces.append({
                        'key': key,
                        'content': content,
                        'broken_blocks': broken_piece_blocks,
                        'errors_by_id': errors_by_id,
                    })
                    for b in broken:
                        block = next((bl for bl in blocks if bl['id'] == b['id']), None)
                        if block:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  [{doc.title}] Broken: {block['latex'][:80]}... → {b.get('error', '')[:60]}"
                                )
                            )

            if broken_pieces:
                doc_tasks.append({'doc': doc, 'data': data, 'broken_pieces': broken_pieces})
            else:
                # Clean doc — mark as validated
                if not dry_run:
                    doc.latex_validated = True
                    await sync_to_async(doc.save)(update_fields=['latex_validated'])

        total_broken_docs = len(doc_tasks)
        total_broken_blocks = sum(
            len(bp['broken_blocks']) for dt in doc_tasks for bp in dt['broken_pieces']
        )
        self.stdout.write(f"Phase 1 complete: {total_broken_docs} docs with errors, {total_broken_blocks} broken blocks total")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"\nDRY-RUN complete. {total_broken_blocks} broken blocks found across {total_broken_docs} documents."))
            return

        if not doc_tasks:
            self.stdout.write(self.style.SUCCESS("\nAll documents are clean!"))
            return

        # Phase 2: Fix ALL broken blocks in parallel via asyncio.gather
        self.stdout.write(f"Phase 2: Fixing {total_broken_blocks} broken blocks via LLM (fully parallel)...")

        async def fix_doc(dt, idx):
            doc = dt['doc']
            data = dt['data']
            doc_fixes = 0
            for bp in dt['broken_pieces']:
                fixed_content, num_fixes = await fixer.fix_content(bp['content'])
                doc_fixes += num_fixes
                if num_fixes > 0:
                    self._apply_fixed_content(data, doc.document_type, bp['key'], fixed_content)

            if doc_fixes > 0:
                doc.structured_data = data
                doc.latex_validated = True
                await sync_to_async(doc.save)(update_fields=['structured_data', 'latex_validated'])
            else:
                doc.latex_validated = True
                await sync_to_async(doc.save)(update_fields=['latex_validated'])

            total_errors = sum(len(bp['broken_blocks']) for bp in dt['broken_pieces'])
            self.stdout.write(f"[{idx + 1}/{total_broken_docs}] {doc.title} — FIXED {doc_fixes}/{total_errors}")
            return doc_fixes

        tasks = [fix_doc(dt, i) for i, dt in enumerate(doc_tasks)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_fixes = sum(r for r in results if isinstance(r, int))
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            self.stdout.write(self.style.ERROR(f"\n{len(errors)} documents failed with exceptions"))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {total_broken_blocks} broken blocks found, {total_fixes} fixes applied across {total_broken_docs} documents."
        ))

    def _get_docs(self, options):
        qs = ParsedDocument.objects.filter(parsing_status='COMPLETED')
        if options.get('doc_id'):
            qs = qs.filter(id=options['doc_id'])
        else:
            if options.get('doc_type'):
                qs = qs.filter(document_type=options['doc_type'])
            if options.get('subject'):
                code = re.sub(r'[\s\-]', '', options['subject']).upper()
                qs = qs.filter(subjects__code__iregex=rf'^{re.escape(code[:2])}\s*-?\s*{re.escape(code[2:])}')
        if not options.get('force'):
            qs = qs.exclude(latex_validated=True)
        return list(qs.distinct())

    def _extract_content(self, data, doc_type):
        """Extract (key, content_string) pairs from structured_data based on doc type."""
        pieces = []
        if doc_type == 'SHORT_NOTES':
            for idx, topic in enumerate(data.get('topics', [])):
                if topic.get('content'):
                    pieces.append((f'topics.{idx}.content', topic['content']))
        elif doc_type == 'IMPORTANT_Q':
            for idx, q in enumerate(data.get('questions', [])):
                if q.get('latex_answer'):
                    pieces.append((f'questions.{idx}.latex_answer', q['latex_answer']))
        elif doc_type in ('NOTES', 'QUESTION_PAPER', 'PYQ', 'UNSOLVED_PYQ'):
            for idx, section in enumerate(data.get('sections', [])):
                for bidx, block in enumerate(section.get('blocks', [])):
                    if block.get('content'):
                        pieces.append((f'sections.{idx}.blocks.{bidx}.content', block['content']))
        elif doc_type == 'FORMULA':
            for idx, f in enumerate(data.get('formulas', [])):
                if f.get('latex'):
                    pieces.append((f'formulas.{idx}.latex', f['latex']))
        return pieces

    def _apply_fixed_content(self, data, doc_type, key, fixed_content):
        """Write fixed content back into structured_data at the given key path."""
        parts = key.split('.')
        obj = data
        for p in parts[:-1]:
            if p.isdigit():
                obj = obj[int(p)]
            else:
                obj = obj[p]
        last = parts[-1]
        if last.isdigit():
            obj[int(last)] = fixed_content
        else:
            obj[last] = fixed_content
