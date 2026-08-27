from pathlib import Path
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.database.database_manager import (
    get_engine,
    connect_sqlite,
)

BASE_DIR = Path(__file__).resolve().parents[3]

DATABASE_PATH: Path | None = None
DATABASE_URL: str | None = None

SessionLocal = None

Base = declarative_base()


def _active_engine():
    active = get_engine()

    if active is not None:
        return active

    raise RuntimeError(
        "No database is currently connected. "
        "Please connect or upload a database first."
    )


def set_database(db_path: Path):
    """
    Set a user-selected SQLite database as the active database.
    """
    global SessionLocal
    global Base
    global DATABASE_URL
    global DATABASE_PATH

    DATABASE_PATH = Path(db_path)
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

    connect_sqlite(str(DATABASE_PATH))

    engine = get_engine()

    if engine is not None:
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )

        Base = declarative_base()


def get_database_info():
    try:
        active_engine = _active_engine()
        inspector = inspect(active_engine)
        tables = inspector.get_table_names()

        column_count = 0
        row_count = 0

        with active_engine.connect() as conn:
            for table in tables:
                columns = inspector.get_columns(table)
                column_count += len(columns)

                try:
                    result = conn.execute(
                        text(f"SELECT COUNT(*) FROM `{table}`")
                    )
                    row_count += result.scalar() or 0
                except Exception:
                    try:
                        result = conn.execute(
                            text(f'SELECT COUNT(*) FROM "{table}"')
                        )
                        row_count += result.scalar() or 0
                    except Exception:
                        pass

        url = active_engine.url
        driver = url.drivername.lower()

        # SQLite
        if driver.startswith("sqlite"):
            database_name = (
                DATABASE_PATH.name
                if DATABASE_PATH is not None and DATABASE_PATH.exists()
                else active_engine.url.database or "SQLite Database"
            )

            size_bytes = (
                DATABASE_PATH.stat().st_size
                if DATABASE_PATH is not None and DATABASE_PATH.exists()
                else 0
            )

            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

        # MySQL / PostgreSQL
        else:
            database_name = url.database or "Connected Database"
            size_str = "Remote Database"

        return {
            "connected": True,
            "db_type": (
                "sqlite"
                if driver.startswith("sqlite")
                else "mysql"
                if driver.startswith("mysql")
                else "postgres"
                if driver.startswith("postgresql")
                else driver
            ),
            "database": database_name,
            "tables": len(tables),
            "rows": row_count,
            "columns": column_count,
            "size": size_str,
        }

    except Exception as e:
        return {
            "connected": False,
            "db_type": "none",
            "database": "Not Connected",
            "tables": 0,
            "rows": 0,
            "columns": 0,
            "size": "0 MB",
            "error": str(e),
        }


def get_dashboard_data():
    try:
        active_engine = _active_engine()
        inspector = inspect(active_engine)
        tables = inspector.get_table_names()

        table_stats = {}
        with active_engine.connect() as conn:
            for table in tables:
                try:
                    row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
                except Exception:
                    row_count = 0
                table_stats[table] = row_count

        return {
            "tables": table_stats,
            "table_count": len(tables),
            "total_rows": sum(table_stats.values()),
        }
    except Exception as e:
        print(f"Dashboard error: {e}")
        return {
            "tables": {},
            "table_count": 0,
            "total_rows": 0,
        }


def get_database_path() -> Path:
    if DATABASE_PATH is not None:
        return DATABASE_PATH
    raise RuntimeError("No database is currently connected.")
