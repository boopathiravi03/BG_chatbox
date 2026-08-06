from pathlib import Path
import shutil
from datetime import datetime
from fastapi import UploadFile, File
from app.database.db import get_database_path, set_database
from app.database.database_manager import connect_sqlite

BACKUP_DIR = Path(__file__).resolve().parents[3] / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def create_backup() -> dict:
    db_path = get_database_path()
    if not db_path.exists():
        return {"status": "error", "message": "Database file not found"}

    timestamp = datetime.now().strftime("%Y_%m_%d")
    backup_name = f"{db_path.stem}_backup_{timestamp}.db"
    backup_path = BACKUP_DIR / backup_name

    shutil.copy2(db_path, backup_path)

    size_bytes = backup_path.stat().st_size
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

    return {
        "status": "success",
        "message": "Backup created successfully",
        "filename": backup_name,
        "path": str(backup_path),
        "size": size_str,
    }


def restore_backup(backup_path: Path) -> dict:
    db_path = get_database_path()

    if not backup_path.exists():
        return {"status": "error", "message": "Backup file not found"}

    if not db_path.exists() or not db_path.samefile(backup_path):
        shutil.copy2(backup_path, db_path)

    try:
        connect_sqlite(str(db_path))
    except Exception as e:
        return {"status": "error", "message": f"Restore failed: {str(e)}"}

    size_bytes = db_path.stat().st_size if db_path.exists() else 0
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

    return {
        "status": "success",
        "message": "Database restored successfully",
        "database": db_path.name,
        "size": size_str,
    }


def get_backup_dir() -> Path:
    return BACKUP_DIR
