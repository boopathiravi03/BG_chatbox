from sqlalchemy import inspect
from app.database.db import engine


def get_schema():
    inspector = inspect(engine)

    schema = {}

    for table in inspector.get_table_names():
        columns = inspector.get_columns(table)

        schema[table] = {
            column["name"]: str(column["type"])
            for column in columns
        }

    return schema
