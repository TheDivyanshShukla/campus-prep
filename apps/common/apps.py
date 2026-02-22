from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver

class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'
    verbose_name = 'Common Shared Layer'

    def ready(self):
        # Import is not needed here as the receiver is in the same file
        # or we could move it to a signals.py if it grows larger.
        pass

@receiver(connection_created)
def activate_sqlite_performance_pragmas(sender, connection, **kwargs):
    """
    Apply high-performance SQLite PRAGMA settings on every new connection.
    """
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        
        # Setting Journal Mode to WAL (Write-Ahead Logging)
        # Note: WAL is persistent, but setting it here ensures it's 
        # always active for the session.
        cursor.execute('PRAGMA journal_mode = WAL;')
        
        # synchronous = NORMAL: Balance between safety and speed. 
        # Dramatically faster than FULL in WAL mode.
        cursor.execute('PRAGMA synchronous = NORMAL;')
        
        # temp_store = MEMORY: Keep temporary tables/indices in RAM.
        cursor.execute('PRAGMA temp_store = MEMORY;')
        
        # mmap_size: Use memory-mapped I/O for faster data access (30GB limit).
        cursor.execute('PRAGMA mmap_size = 30000000000;')
        
        # cache_size: Set the number of pages to cache. 
        # Negative value specifies KB (-200000 = ~200MB).
        cursor.execute('PRAGMA cache_size = -200000;')
        
        # Set page size (defalut is 4096)
        cursor.execute('PRAGMA page_size = 4096;')
