from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Project root (BG_AI)
BASE_DIR = Path(__file__).resolve().parents[3]

DATABASE_PATH = BASE_DIR / "database" / "ecommerce.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def set_database(db_path: Path):
    global engine, SessionLocal, Base, DATABASE_URL, DATABASE_PATH
    DATABASE_PATH = db_path
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
    engine.dispose()
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    Base = declarative_base()


def get_database_info():
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        table_count = len(tables)

        column_count = 0
        row_count = 0

        with engine.connect() as conn:
            for table in tables:
                columns = inspector.get_columns(table)
                column_count += len(columns)

                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                row_count += result.scalar()

        size_bytes = DATABASE_PATH.stat().st_size if DATABASE_PATH.exists() else 0

        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

        return {
            "database": DATABASE_PATH.name,
            "tables": table_count,
            "rows": row_count,
            "columns": column_count,
            "size": size_str,
        }
    except Exception as e:
        return {
            "database": DATABASE_PATH.name,
            "tables": 0,
            "rows": 0,
            "columns": 0,
            "size": "0 MB",
            "error": str(e),
        }


def get_dashboard_data():
    try:
        with engine.connect() as conn:
            customer_count = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()
            product_count = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()
            order_count = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
            revenue = conn.execute(text("SELECT COALESCE(SUM(quantity * price), 0) FROM orders JOIN products ON orders.product_id = products.product_id")).scalar()
            return {
                "customers": customer_count or 0,
                "products": product_count or 0,
                "orders": order_count or 0,
                "revenue": round(float(revenue), 2) if revenue else 0,
            }
    except Exception as e:
        print(f"Dashboard error: {e}")
        return {
            "customers": 0,
            "products": 0,
            "orders": 0,
            "revenue": 0,
        }


def get_database_path() -> Path:
    return DATABASE_PATH
