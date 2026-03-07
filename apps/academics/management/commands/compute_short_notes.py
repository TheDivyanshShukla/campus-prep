import asyncio
from django.core.management.base import BaseCommand
from asgiref.sync import sync_to_async
from apps.academics.models import Subject
from apps.content.models import ParsedDocument
from apps.content.services.ai_parser.short_notes import ShortNotesParser

class Command(BaseCommand):
    help = 'Computes and saves high-impact Short Notes for all active subjects.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Delete existing Short Notes and re-generate.')
        parser.add_argument('--unit-wise', action='store_true', help='Generate per-unit short notes.')
        parser.add_argument('--complete', action='store_true', help='Generate a single subject-wide short note bank.')
        parser.add_argument('--subject', type=str, help='Filter by subject code (e.g. CS-601).')
        parser.add_argument('--unit', type=int, help='Filter by unit number (1-5).')

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(options))

    async def async_handle(self, options):
        force_reprocess = options.get('force', False)
        unit_wise = options.get('unit_wise', False)
        complete = options.get('complete', False)
        subject_filter = options.get('subject')
        unit_filter = options.get('unit')
        
        if not unit_wise and not complete:
            complete = True

        @sync_to_async
        def get_all_subjects():
            qs = Subject.objects.filter(is_active=True)
            if subject_filter:
                qs = qs.filter(code__iexact=subject_filter)
            
            subjects = list(qs.prefetch_related('units'))
            unique_subjects = []
            seen_codes = set()
            for s in subjects:
                norm_code = s.code.replace(' ', '').replace('-', '').upper()
                if norm_code not in seen_codes:
                    unique_subjects.append(s)
                    seen_codes.add(norm_code)
            return unique_subjects

        subjects = await get_all_subjects()
        
        if not subjects:
            self.stdout.write(self.style.ERROR("No active subjects found."))
            return

        semaphore = asyncio.Semaphore(5000)
        parser = ShortNotesParser()

        async def process_task(subject, unit_number=None, module_title=None):
            async with semaphore:
                try:
                    title_suffix = f"Unit {unit_number}: {module_title}" if unit_number and module_title else (f"Unit {unit_number}" if unit_number else "Subject-wide")
                    doc_title = f"{subject.code} Short Notes - {title_suffix}"
                    
                    @sync_to_async
                    def handle_existing():
                        query = ParsedDocument.objects.filter(subjects=subject, document_type='SHORT_NOTES')
                        if unit_number:
                            query = query.filter(title__contains=f"Unit {unit_number}")
                        else:
                            query = query.exclude(title__contains="Unit ")
                        
                        if query.exists():
                            if force_reprocess:
                                query.delete()
                                return False
                            return True
                        return False
                    
                    if await handle_existing():
                        return

                    self.stdout.write(f"Generating {title_suffix} Short Notes for {subject.code}...")

                    @sync_to_async
                    def create_doc():
                        doc = ParsedDocument.objects.create(
                            document_type='SHORT_NOTES',
                            title=doc_title,
                            parsing_status='PROCESSING',
                            is_published=True,
                            render_mode='NATIVE'
                        )
                        doc.subjects.add(subject)
                        return doc

                    doc_obj = await create_doc()

                    try:
                        parse_kwargs = {"unit_number": unit_number} if unit_number else {}
                        result = await parser.parse(doc_obj, **parse_kwargs)
                        
                        @sync_to_async
                        def save_doc(data):
                            doc_obj.structured_data = data
                            doc_obj.parsing_status = 'COMPLETED'
                            doc_obj.save()

                        await save_doc(result)
                        self.stdout.write(self.style.SUCCESS(f"Finished {subject.code} - {title_suffix}"))

                    except Exception as e:
                        @sync_to_async
                        def mark_failed():
                            doc_obj.parsing_status = 'FAILED'
                            doc_obj.save()
                        await mark_failed()
                        self.stdout.write(self.style.ERROR(f"Failed {subject.code} {title_suffix}: {str(e)[:100]}"))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Outer error for {subject.code}: {str(e)}"))

        all_tasks = []
        for s in subjects:
            if complete and not unit_filter:
                all_tasks.append(process_task(s))
            
            if unit_wise:
                @sync_to_async
                def get_syllabus():
                    return ParsedDocument.objects.filter(
                        subjects=s,
                        document_type='SYLLABUS',
                        parsing_status='COMPLETED'
                    ).first()
                
                syllabus = await get_syllabus()
                if syllabus and syllabus.structured_data and 'modules' in syllabus.structured_data:
                    for module in syllabus.structured_data['modules']:
                        u_num = module.get('unit')
                        if unit_filter and str(u_num) != str(unit_filter):
                            continue
                        u_title = module.get('title', f"Unit {u_num}")
                        all_tasks.append(process_task(s, unit_number=u_num, module_title=u_title))
                else:
                    self.stdout.write(self.style.WARNING(f"No syllabus for {s.code}. Units 1-5 fallback."))
                    for unit_num in range(1, 6):
                        if unit_filter and unit_num != unit_filter:
                            continue
                        all_tasks.append(process_task(s, unit_num))

        if not all_tasks:
            self.stdout.write(self.style.WARNING("No tasks created."))
            return

        self.stdout.write(f"Launching {len(all_tasks)} parallel tasks...")
        await asyncio.gather(*all_tasks)
        self.stdout.write(self.style.SUCCESS("Short Notes processing finished."))
