from sqlalchemy import text
from app.database.database_manager import get_engine


def execute_query(query: str):
    try:
        engine = get_engine()

        if engine is None:
            return {
                "success": False,
                "error": "No database is currently connected.",
            }

        with engine.connect() as connection:
            result = connection.execute(text(query))

            rows = result.fetchall()

            columns = result.keys()

            return {
                "success": True,
                "columns": list(columns),
                "rows": [list(row) for row in rows]
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
