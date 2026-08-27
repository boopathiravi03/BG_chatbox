from sqlalchemy import inspect, text
from app.database.database_manager import get_engine


def get_dashboard_data():
    try:
        engine = get_engine()

        if engine is None:
            return {
                "cards": {
                    "table_count": 0,
                    "total_rows": 0,
                    "tables": {},
                },
                "bar": {"labels": [], "values": []},
                "line": {"labels": [], "values": []},
                "pie": {"labels": [], "values": []},
            }

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        table_stats = {}
        with engine.connect() as conn:
            for table in tables:
                try:
                    row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
                except Exception:
                    row_count = 0
                table_stats[table] = row_count

        cards = {
            "table_count": len(tables),
            "total_rows": sum(table_stats.values()),
            "tables": table_stats,
        }

        bar = {
            "labels": list(table_stats.keys()),
            "values": list(table_stats.values()),
        }

        line = {
            "labels": list(table_stats.keys()),
            "values": list(table_stats.values()),
        }

        pie = {
            "labels": list(table_stats.keys()),
            "values": list(table_stats.values()),
        }

        return {
            "cards": cards,
            "bar": bar,
            "line": line,
            "pie": pie,
        }
    except Exception as e:
        print(f"Dashboard data error: {e}")
        return {
            "cards": {
                "table_count": 0,
                "total_rows": 0,
                "tables": {},
            },
            "bar": {"labels": [], "values": []},
            "line": {"labels": [], "values": []},
            "pie": {"labels": [], "values": []},
        }
