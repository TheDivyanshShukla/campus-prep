import re
from django.core.management.base import BaseCommand
from apps.academics.models import Subject

class Command(BaseCommand):
    help = 'Normalizes all subject codes to a standard format: [DEPT]-[NUM] (SUFFIX)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show changes without saving.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        subjects = Subject.objects.all()
        
        count = 0
        for subject in subjects:
            old_code = subject.code
            new_code = self.normalize_code(old_code)
            
            if old_code != new_code:
                self.stdout.write(f"Normalize: '{old_code}' -> '{new_code}'")
                if not dry_run:
                    subject.code = new_code
                    subject.save()
                count += 1
        
        self.stdout.write(self.style.SUCCESS(f"Processed {count} subject codes. (Dry-run: {dry_run})"))

    def normalize_code(self, code: str) -> str:
        # 1. Basic cleaning: uppercase and remove weird characters
        code = code.upper().strip()
        
        # 2. Extract components
        # Pattern: Letters (optional hyphen/space) Numbers (optional suffix in parens)
        # Handle cases like "CE- 503 (B)", "CS301", "EX-702 (A)", "BT 205"
        match = re.match(r'^([A-Z]+)[-\s]*(\d+)\s*(?:\(?\s*([A-Z])\s*\)?)?$', code)
        
        if match:
            dept = match.group(1)
            num = match.group(2)
            suffix = match.group(3)
            
            normalized = f"{dept}-{num}"
            if suffix:
                normalized += f" ({suffix})"
            return normalized
        
        # Fallback for weird patterns: just preserve hyphen/space normalization
        return code.replace(" ", "")
