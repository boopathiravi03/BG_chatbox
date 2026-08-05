import sqlite3
from app.database.db import get_database_path


def get_relationship_graph():
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )

    tables = [row[0] for row in cursor.fetchall()]

    nodes = []
    edges = []

    for table in tables:
        nodes.append({
            "id": table,
            "label": table
        })

        cursor.execute(f"PRAGMA foreign_key_list({table})")

        for fk in cursor.fetchall():
            edges.append({
                "from": table,
                "to": fk[2]
            })

    conn.close()

    return {
        "nodes": nodes,
        "edges": edges
    }
