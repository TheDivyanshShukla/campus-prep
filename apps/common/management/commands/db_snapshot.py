import os
import glob
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings

class Command(BaseCommand):
    help = 'Manage database snapshots (create, list, recover). Maintains last 10 snapshots.'
    
    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', required=True)

        # 1. CREATE Subcommand
        parser_create = subparsers.add_parser('create', help='Create a new complete database snapshot.')

        # 2. LIST Subcommand
        subparsers.add_parser('list', help='List available snapshots.')

        # 3. RECOVER Subcommand
        parser_recover = subparsers.add_parser('recover', help='Restore the database from a snapshot.')
        parser_recover.add_argument('filename', type=str, help='The snapshot file name (e.g., snapshot_20260302_120000.json)')
        parser_recover.add_argument('--no-input', action='store_true', help='Skip the confirmation prompt.')


    def handle(self, *args, **options):
        self.snapshots_dir = os.path.join(settings.BASE_DIR, 'data', 'snapshots')
        os.makedirs(self.snapshots_dir, exist_ok=True)
        
        action = options['action']

        if action == 'create':
            self.create_snapshot()
        elif action == 'list':
            self.list_snapshots()
        elif action == 'recover':
            self.recover_snapshot(options['filename'], options.get('no_input', False))


    def _get_snapshot_files(self):
        """Returns a list of snapshot files sorted by creation time (oldest first)."""
        pattern = os.path.join(self.snapshots_dir, 'snapshot_*.json')
        files = glob.glob(pattern)
        # Sort by modification time
        files.sort(key=os.path.getmtime)
        return files

    def create_snapshot(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"snapshot_{timestamp}_full.json"
        filepath = os.path.join(self.snapshots_dir, filename)

        self.stdout.write(f"🔄 Creating full snapshot: {filename}")
        
        dumpdata_args = []
        
        try:
            # We output to a file instead of stdout using the standard dumpdata argument
            with open(filepath, 'w', encoding='utf-8') as f:
                call_command('dumpdata', *dumpdata_args, indent=2, stdout=f)
            
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully created snapshot: {filename}"))
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            raise CommandError(f"Failed to create snapshot: {e}")

        # Enforce max 10 snapshots rule
        self._enforce_snapshot_limit()


    def _enforce_snapshot_limit(self, limit=10):
        files = self._get_snapshot_files()
        if len(files) > limit:
            files_to_delete = files[:-limit] # Everything before the last 10
            for f in files_to_delete:
                try:
                    os.remove(f)
                    self.stdout.write(self.style.WARNING(f"🗑️ Removed old snapshot to maintain limit: {os.path.basename(f)}"))
                except OSError as e:
                    self.stdout.write(self.style.ERROR(f"Error removing {f}: {e}"))


    def list_snapshots(self):
        files = self._get_snapshot_files()
        
        if not files:
            self.stdout.write("📂 No snapshots found.")
            return

        self.stdout.write(f"📂 Found {len(files)} snapshots:")
        self.stdout.write("-" * 50)
        
        for idx, f in enumerate(files, 1):
            name = os.path.basename(f)
            size_mb = os.path.getsize(f) / (1024 * 1024)
            mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
            self.stdout.write(f"{idx:2d}. {name} ({size_mb:.2f} MB) - {mtime}")
        
        self.stdout.write("-" * 50)


    def recover_snapshot(self, filename, no_input=False):
        filepath = os.path.join(self.snapshots_dir, filename)
        
        if not os.path.exists(filepath):
            raise CommandError(f"Snapshot not found: {filename} in {self.snapshots_dir}")
        
        self.stdout.write(self.style.WARNING(f"⚠️  WARNING: You are about to restore the database from {filename}."))
        self.stdout.write(self.style.WARNING("This will OVERWRITE existing matching data (though it won't delete newer records unless flushed)."))
        
        if not no_input:
            confirm = input("Are you sure you want to proceed? [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write(self.style.ERROR("Recovery aborted."))
                return
            
        self.stdout.write("⏳ Restoring data...")
        try:
            call_command('loaddata', filepath)
            self.stdout.write(self.style.SUCCESS(f"✨ Successfully restored database from {filename}"))
        except Exception as e:
            raise CommandError(f"Failed to recover snapshot: {e}")
