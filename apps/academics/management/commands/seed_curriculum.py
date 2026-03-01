import os
from django.core.management.base import BaseCommand
from apps.academics.services.syllabus_mining import SyllabusMiningService
from django.conf import settings

class Command(BaseCommand):
    help = 'Seed the database using the cleaned syllabus data JSON'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', 
            type=str, 
            default='.me/datamine/cleaned_syllabus.json',
            help='Path to the cleaned JSON file'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        if not os.path.isabs(file_path):
            file_path = os.path.join(settings.BASE_DIR, file_path)

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Cleaned syllabus file not found at {file_path}"))
            self.stdout.write(self.style.NOTICE("Please run 'uv run scripts/transform_syllabus.py' first."))
            return

        self.stdout.write(self.style.NOTICE(f"Seeding curriculum from {file_path}..."))
        
        results = SyllabusMiningService.import_from_json(file_path)
        
        if "error" in results:
            self.stdout.write(self.style.ERROR(results["error"]))
            return

        for b_code in results.get("processed_branches", []):
            self.stdout.write(self.style.SUCCESS(f"Successfully seeded branch: {b_code}"))

        self.stdout.write(self.style.SUCCESS("Syllabus seeding completed successfully!"))
