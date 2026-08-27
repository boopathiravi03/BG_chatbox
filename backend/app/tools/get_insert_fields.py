from sqlalchemy import inspect
from app.database.database_manager import get_engine


def get_insert_fields(table_name: str):
    """
    Get columns that can be supplied by the user during INSERT.

    Automatically excludes:
    - auto-increment primary keys
    - generated columns
    """
    engine = get_engine()

    if engine is None:
        return []

    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)

    fields = []

    for column in columns:
        name = column.get("name", "")
        column_type = str(column.get("type", ""))
        not_null = not column.get("nullable", True)
        default_value = column.get("default")
        primary_key = column.get("primary_key", False)

        if primary_key:
            continue

        fields.append({
            "name": name,
            "label": name.replace("_", " ").title(),
            "type": column_type,
            "required": bool(not_null and default_value is None),
            "default": default_value,
        })

    return fields
