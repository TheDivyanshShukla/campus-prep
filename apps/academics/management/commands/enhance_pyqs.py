import asyncio
from django.core.management.base import BaseCommand
from django.db import transaction
from asgiref.sync import sync_to_async
from apps.academics.models import Subject
from apps.content.models import ParsedDocument
from apps.content.services.ai_parser.enhancer import PYQEnhancer

class Command(BaseCommand):
    help = 'Enhance and re-label PYQ questions using the syllabus as ground truth.'

    def add_arguments(self, parser):
        parser.add_argument('--subject', type=str, help='Filter by subject code')
        parser.add_argument('--force', action='store_true', help='Force re-enhancement even if already enhanced')

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))

    async def async_handle(self, *args, **options):
        subject_code = options.get('subject')
        force = options.get('force')
        
        enhancer = PYQEnhancer()
        
        # 1. Get Subjects
        @sync_to_async
        def get_all_subjects():
            qs = Subject.objects.all()
            if subject_code:
                qs = qs.filter(code=subject_code)
            return list(qs)
        
        subjects = await get_all_subjects()
        self.stdout.write(f"Gathering documents for {len(subjects)} subjects...")

        all_doc_tasks = []

        async def _process_subject(s):
            # Fetch Syllabus for this subject
            @sync_to_async
            def get_syllabus():
                doc = ParsedDocument.objects.filter(
                    subjects=s,
                    document_type='SYLLABUS',
                    parsing_status__in=['COMPLETED', 'PENDING'],
                    structured_data__isnull=False
                ).first()
                if not doc:
                    doc = ParsedDocument.objects.filter(
                        subjects__code=s.code,
                        document_type='SYLLABUS',
                        parsing_status__in=['COMPLETED', 'PENDING'],
                        structured_data__isnull=False
                    ).first()
                return doc
            
            syllabus_doc = await get_syllabus()
            if not syllabus_doc:
                return
            
            # Fetch UNSOLVED_PYQ documents for this subject
            @sync_to_async
            def get_pyqs():
                return list(ParsedDocument.objects.filter(
                    subjects=s,
                    document_type='UNSOLVED_PYQ',
                    parsing_status='COMPLETED'
                ))
            
            pyq_docs = await get_pyqs()
            
            for doc in pyq_docs:
                async def _process_single_doc(d, subj, syll):
                    data = d.structured_data or {}
                    questions = data.get('questions', [])
                    
                    if not force and questions and all(q.get('topic_name') for q in questions):
                        return
                    
                    self.stdout.write(f"    Queueing: {d.title} ({subj.code})")
                    
                    ctx = {
                        'subject_code': subj.code,
                        'subject_name': subj.name,
                    }
                    
                    try:
                        enhanced_data = await enhancer.enhance_questions(
                            questions=questions,
                            syllabus_data=syll.structured_data,
                            subject_context=ctx,
                            is_solved=False
                        )
                        
                        @sync_to_async
                        def save_doc(doc_obj, new_data):
                            doc_obj.structured_data = new_data
                            doc_obj.save()
                        
                        await save_doc(d, enhanced_data)
                        self.stdout.write(self.style.SUCCESS(f"      Success: {d.title}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"      Error {d.title}: {str(e)}"))

                all_doc_tasks.append(_process_single_doc(doc, s, syllabus_doc))

        # Build task list per subject
        subject_tasks = [_process_subject(s) for s in subjects]
        await asyncio.gather(*subject_tasks)

        if not all_doc_tasks:
            self.stdout.write(self.style.WARNING("No documents to enhance."))
            return

        self.stdout.write(f"Launching {len(all_doc_tasks)} parallel enhancement tasks...")
        
        await asyncio.gather(*all_doc_tasks)
        self.stdout.write(self.style.SUCCESS("Global PYQ Enhancement finished."))
