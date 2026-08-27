from sqlalchemy import inspect, text
from app.database.database_manager import get_engine


def generate_er_diagram():
    engine = get_engine()

    if engine is None:
        return "erDiagram\n"

    inspector = inspect(engine)

    try:
        tables = inspector.get_table_names()
    except Exception:
        tables = []

    mermaid = "erDiagram\n"

    for table in tables:
        mermaid += f"    {table.upper()} {{\n"

        try:
            columns = inspector.get_columns(table)
            for column in columns:
                col_name = column.get("name", "")
                col_type = str(column.get("type", ""))
                mermaid += f"        {col_type} {col_name}\n"
        except Exception:
            pass

        mermaid += "    }\n\n"

    for table in tables:
        try:
            foreign_keys = inspector.get_foreign_keys(table)
            for fk in foreign_keys:
                referred_table = fk.get("referred_table", "")
                constrained = fk.get("constrained_columns", [])
                referred_columns = fk.get("referred_columns", [])
                if referred_table and constrained:
                    mermaid += f"    {referred_table.upper()} ||--o{{ {table.upper()} : has\n"
        except Exception:
            pass

    return mermaid
