from sqlalchemy import inspect
from app.database.database_manager import get_engine


def get_schema():
    engine = get_engine()

    if engine is None:
        raise RuntimeError(
            "No database is currently connected."
        )

    inspector = inspect(engine)

    schema = {}

    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)

        schema[table_name] = {}

        for column in columns:
            schema[table_name][column["name"]] = {
                "type": str(column.get("type", "")),
                "nullable": column.get("nullable", True),
                "primary_key": column.get("primary_key", False),
                "default": column.get("default"),
            }

    return schema
