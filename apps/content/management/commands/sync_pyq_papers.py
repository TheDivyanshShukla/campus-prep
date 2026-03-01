
import sqlite3
import os
from django.core.management.base import BaseCommand
from apps.academics.models import Subject, Branch
from apps.content.models import ParsedDocument
from django.conf import settings

class Command(BaseCommand):
    help = 'Sync PYQ papers from rgpv_papers.db into ParsedDocument model'

    def handle(self, *args, **options):
        db_path = os.path.join(settings.BASE_DIR, '.me', 'datamine', 'rgpv_papers.db')
        if not os.path.exists(db_path):
            self.stdout.write(self.style.ERROR(f"Database not found at {db_path}"))
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        self.stdout.write(self.style.NOTICE("Fetching papers and subjects from SQLite..."))
        
        # Get all papers with their subject and branch info
        query = """
        SELECT 
            p.label, p.year, p.pdf_url, s.code, s.name as subject_name, b.code as branch_code
        FROM papers p
        JOIN subjects s ON p.subject_id = s.id
        JOIN branches b ON s.branch_id = b.id
        """
        cursor.execute(query)
        papers_data = cursor.fetchall()
        
        self.stdout.write(f"Found {len(papers_data)} papers in SQLite database.")

        sync_count = 0
        skip_count = 0
        
        for p_label, p_year, p_pdf_url, s_code, s_name, b_code in papers_data:
            # Map branch code if necessary (e.g., AD in SQLite to AD in Django)
            # Find the matching subject in Django
            subjects = Subject.objects.filter(code=s_code, branch__code=b_code)
            
            if not subjects.exists():
                # Try finding by code only as a fallback
                subjects = Subject.objects.filter(code=s_code)
            
            if not subjects.exists():
                self.stdout.write(self.style.WARNING(f"Skipping {p_label}: No subject found for code {s_code} in branch {b_code}"))
                skip_count += 1
                continue

            # Create or update ParsedDocument
            # Note: A single paper might apply to multiple semester/branch variants of the same subject code
            doc, created = ParsedDocument.objects.update_or_create(
                title=p_label,
                year=p_year,
                defaults={
                    'document_type': 'UNSOLVED_PYQ',
                    'render_mode': 'DIRECT_PDF',
                    'source_text': p_pdf_url, # Storing URL in source_text for now
                    'is_published': True
                }
            )
            
            # Link to all matching subjects
            doc.subjects.set(subjects)
            
            if created:
                sync_count += 1
            
        self.stdout.write(self.style.SUCCESS(f"Successfully synced {sync_count} papers. Skipped {skip_count}."))
        conn.close()
