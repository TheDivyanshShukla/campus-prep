import os
from django.core.management.base import BaseCommand
from apps.academics.services.syllabus_mining import SyllabusMiningService
from django.conf import settings

class Command(BaseCommand):
    help = 'Import syllabus data from mined JSON file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', 
            type=str, 
            default='.me/datamine/rgpv_syllabus_data.json',
            help='Path to the JSON file'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        if not os.path.isabs(file_path):
            file_path = os.path.join(settings.BASE_DIR, file_path)

        self.stdout.write(self.style.NOTICE(f"Starting import from {file_path}..."))
        
        results = SyllabusMiningService.import_from_json(file_path)
        
        if "error" in results:
            self.stdout.write(self.style.ERROR(results["error"]))
            return

        self.stdout.write(self.style.SUCCESS("Bulk import completed successfully!"))
