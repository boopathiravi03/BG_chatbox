import time
from sqlalchemy import text
from app.database.session import engine


def execute_query(sql: str):
    """
    Execute SQL query and return rows with execution stats.
    """

    start = time.perf_counter()

    with engine.connect() as conn:
        result = conn.execute(text(sql))

        rows = result.fetchall()

        columns = result.keys()

    end = time.perf_counter()

    execution_time_ms = round((end - start) * 1000, 2)

    return {
        "success": True,
        "columns": list(columns),
        "rows": [list(r) for r in rows],
        "execution_time_ms": execution_time_ms,
        "rows_returned": len(rows),
    }
