import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
from io import BytesIO

# Load environment variables from .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

def get_db_urls():
    """Reads local and remote database URLs from environment variables.

    Required .env vars:
        DATABASE_URL          – local PostgreSQL connection string
        REMOTE_DATABASE_URL   – remote PostgreSQL connection string
    """
    local_url = os.getenv('DATABASE_URL')
    remote_url = os.getenv('REMOTE_DATABASE_URL')

    if not local_url:
        print("❌ DATABASE_URL not set in .env")
        sys.exit(1)
    if not remote_url:
        print("❌ REMOTE_DATABASE_URL not set in .env")
        sys.exit(1)

    return local_url, remote_url

def get_tables(cursor):
    """Fetches all public tables from the database."""
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    return [row[0] for row in cursor.fetchall()]

def table_exists(cursor, table_name):
    """Checks if a table exists in the destination database."""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = %s
        );
    """, (table_name,))
    return cursor.fetchone()[0]

def sync_databases(local_url, remote_url):
    """Syncs databases using pure Python streaming, creating missing tables."""
    print(f"\n🚀 Pure Python Database Sync")
    print(f"----------------------------")
    print(f"Source (Local):  {local_url}")
    print(f"Target (Server): {remote_url}")
    print(f"----------------------------")
    
    confirm = input("\n⚠️  WARNING: This will OVERWRITE the server database tables with local data. Proceed? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Sync aborted.")
        return

    try:
        print("\n⏳ Establishing connections...")
        src_conn = psycopg2.connect(local_url)
        dst_conn = psycopg2.connect(remote_url)
        
        src_cur = src_conn.cursor()
        dst_cur = dst_conn.cursor()

        tables = get_tables(src_cur)
        print(f"📊 Found {len(tables)} tables to sync.")

        # First pass: ensure all tables exist
        missing_tables = []
        for table in tables:
            if not table_exists(dst_cur, table):
                missing_tables.append(table)
        
        if missing_tables:
            print(f"⚠️  {len(missing_tables)} tables are missing on the server.")
            auto_migrate = input("👉 Would you like to automatically run Django migrations on the server? (y/N): ")
            
            if auto_migrate.lower() == 'y':
                print("\n⚙️  Running 'uv run manage.py migrate' for remote database...")
                import subprocess
                
                # Clone current env and set DATABASE_URL to remote
                env = os.environ.copy()
                env['DATABASE_URL'] = remote_url
                
                try:
                    # Run migrate command
                    subprocess.run(
                        ["uv", "run", "manage.py", "migrate"], 
                        env=env, 
                        check=True,
                        cwd=str(BASE_DIR)
                    )
                except subprocess.CalledProcessError:
                    print("\n⚠️  Migration failed. This often happens if tables already exist but aren't tracked.")
                    retry = input("👉 Try again with '--fake-initial'? (y/N): ")
                    if retry.lower() == 'y':
                        try:
                            subprocess.run(
                                ["uv", "run", "manage.py", "migrate", "--fake-initial"], 
                                env=env, 
                                check=True,
                                cwd=str(BASE_DIR)
                            )
                        except subprocess.CalledProcessError as e:
                            print(f"❌ Migration failed even with --fake-initial: {e}")
                            return
                    else:
                        print("❌ Migration aborted.")
                        return

                print("✅ Migrations completed on server.")
                
                # CRITICAL: Reopen the destination connection to see the new tables
                # PostgreSQL transactions started before the migration won't see the new tables.
                dst_conn.close()
                dst_conn = psycopg2.connect(remote_url)
                dst_cur = dst_conn.cursor()
            else:
                print("\n❌ Error: Remote database is not initialized. Please run migrations on the server first.")
                return

        for table in tables:
            # Re-check if it exists now after migration
            if not table_exists(dst_cur, table):
                print(f"⏩ Skipping table {table} (still missing on server after migration check)")
                continue
            
            # Note: We still use TRUNCATE CASCADE to be safe and clear existing data correctly
            print(f"🧹 Truncating table: {table}...", end="", flush=True)
            dst_cur.execute(f'TRUNCATE TABLE "{table}" CASCADE;')
            print(" ✅")

        print("\n⏳ Disabling constraints on destination for sync...")
        dst_cur.execute("SET session_replication_role = 'replica';")

        for table in tables:
            if not table_exists(dst_cur, table):
                continue

            print(f"📦 Syncing data: {table}...", end="", flush=True)
            buffer = BytesIO()
            src_cur.copy_expert(f'COPY "{table}" TO STDOUT BINARY', buffer)
            buffer.seek(0)
            dst_cur.copy_expert(f'COPY "{table}" FROM STDIN BINARY', buffer)
            print(" ✅")

        print("\n⏳ Re-enabling constraints...")
        dst_cur.execute("SET session_replication_role = 'origin';")
        dst_conn.commit()

        print("\n✨ Database Synchronization Successful!")

    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        if 'dst_conn' in locals():
            dst_conn.rollback()
    finally:
        if 'src_conn' in locals(): src_conn.close()
        if 'dst_conn' in locals(): dst_conn.close()

if __name__ == "__main__":
    local_db, remote_db = get_db_urls()
    sync_databases(local_db, remote_db)
