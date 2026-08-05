from sqlalchemy import inspect
from app.database.session import engine


def get_schema():

    inspector = inspect(engine)

    schema = {}

    for table in inspector.get_table_names():

        cols = {}

        for c in inspector.get_columns(table):
            cols[c["name"]] = str(c["type"])

        schema[table] = cols

    return schema
