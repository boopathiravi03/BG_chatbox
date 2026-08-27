from sqlalchemy import inspect, text
from app.database.database_manager import get_engine


def get_relationship_graph():
    engine = get_engine()

    if engine is None:
        return {
            "nodes": [],
            "edges": [],
        }

    inspector = inspect(engine)

    try:
        tables = inspector.get_table_names()
    except Exception:
        tables = []

    nodes = []
    edges = []

    for table in tables:
        nodes.append({
            "id": table,
            "label": table
        })

        try:
            foreign_keys = inspector.get_foreign_keys(table)
            for fk in foreign_keys:
                referred_table = fk.get("referred_table")
                if referred_table:
                    edges.append({
                        "from": table,
                        "to": referred_table
                    })
        except Exception:
            pass

    return {
        "nodes": nodes,
        "edges": edges
    }
