from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Switch render_mode to NATIVE for UNSOLVED_PYQ docs with parsing_status COMPLETED and render_mode DIRECT_PDF'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show matching document IDs and count without updating')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of documents to update (0 = no limit)')

    def handle(self, *args, **options):
        from apps.content.models import ParsedDocument

        qs = ParsedDocument.objects.filter(
            document_type='UNSOLVED_PYQ',
            parsing_status='COMPLETED',
            render_mode='DIRECT_PDF',
        ).order_by('id')

        total = qs.count()
        dry = options.get('dry_run')
        limit = options.get('limit') or 0

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No matching documents found.'))
            return

        self.stdout.write(f'Found {total} matching documents.')

        if dry:
            ids = list(qs.values_list('id', flat=True)[:limit or None])
            self.stdout.write('Dry run - matching document IDs:')
            for i in ids:
                self.stdout.write(str(i))
            return

        if limit:
            qs = qs[:limit]

        updated = qs.update(render_mode='NATIVE')
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} documents to render_mode=\'NATIVE\''))
