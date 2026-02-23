import os
import shutil
from pathlib import Path

def reset_migrations():
    base_dir = Path(__file__).resolve().parent.parent
    apps_dir = base_dir / 'apps'
    
    print(f"Base Directory: {base_dir}")
    
    # 1. Delete Migrations
    for app_path in apps_dir.iterdir():
        if app_path.is_dir():
            migration_dir = app_path / 'migrations'
            if migration_dir.exists():
                print(f"Cleaning migrations in: {app_path.name}")
                for file in migration_dir.iterdir():
                    if file.is_file() and file.name != '__init__.py':
                        print(f"  Deleting: {file.name}")
                        file.unlink()
                    elif file.is_dir() and file.name == '__pycache__':
                        print(f"  Deleting: {file.name}/")
                        shutil.rmtree(file)

    # 2. Delete Database
    db_path = base_dir / 'db.sqlite3'
    if db_path.exists():
        print(f"Deleting database: {db_path}")
        db_path.unlink()
    else:
        print("Database file not found, skipping...")

if __name__ == "__main__":
    reset_migrations()
