from sqlalchemy import inspect
from app.database.database_manager import get_engine


def get_schema():
    engine = get_engine()

    if engine is None:
        return {}

    inspector = inspect(engine)

    schema = {}

    for table in inspector.get_table_names():
        columns = inspector.get_columns(table)

        schema[table] = {
            column["name"]: str(column["type"])
            for column in columns
        }

    return schema
