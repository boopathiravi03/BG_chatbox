from sqlalchemy import inspect, text
from app.database.database_manager import get_engine


def get_dashboard_data():
    try:
        from app.database.connection_context import get_request_user_id, get_request_connection_id
        uid = get_request_user_id()
        if uid:
            try:
                from app.connectors.registry import get_connection_registry, ConnectorStatus
                reg = get_connection_registry()
                target_cid = get_request_connection_id()
                conn = reg.get_connector(uid, target_cid) if target_cid else reg.get_active_connector(uid)

                if conn and conn.status == ConnectorStatus.CONNECTED:
                    schema = conn.get_schema()
                    entity_names = [k for k in schema.keys() if not k.startswith("system.")]
                    entity_stats = {}

                    if conn.connector_type == "mongodb":
                        if getattr(conn, "_client", None) is not None:
                            db = conn._client[conn.database]
                            for c in entity_names:
                                try:
                                    entity_stats[c] = db[c].estimated_document_count()
                                except Exception:
                                    entity_stats[c] = 0
                    elif hasattr(conn, "_engine") and conn._engine is not None:
                        with conn._engine.connect() as sql_conn:
                            for t in entity_names:
                                try:
                                    t_q = conn._quote_id(t) if hasattr(conn, "_quote_id") else f'"{t}"'
                                    r = sql_conn.execute(text(f"SELECT COUNT(*) FROM {t_q}"))
                                    entity_stats[t] = r.scalar() or 0
                                except Exception:
                                    entity_stats[t] = 0

                    if entity_stats:
                        return {
                            "cards": {
                                "table_count": len(entity_stats),
                                "total_rows": sum(entity_stats.values()),
                                "tables": entity_stats,
                            },
                            "bar": {
                                "labels": list(entity_stats.keys()),
                                "values": list(entity_stats.values()),
                            },
                            "line": {
                                "labels": list(entity_stats.keys()),
                                "values": list(entity_stats.values()),
                            },
                            "pie": {
                                "labels": list(entity_stats.keys()),
                                "values": list(entity_stats.values()),
                            },
                        }
            except Exception:
                pass

        engine = get_engine()
        if engine is None:
            return {
                "cards": {
                    "table_count": 0,
                    "total_rows": 0,
                    "tables": {},
                },
                "bar": {"labels": [], "values": []},
                "line": {"labels": [], "values": []},
                "pie": {"labels": [], "values": []},
            }

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        table_stats = {}
        with engine.connect() as conn:
            for table in tables:
                try:
                    row_count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar() or 0
                except Exception:
                    try:
                        row_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0
                    except Exception:
                        row_count = 0
                table_stats[table] = row_count

        cards = {
            "table_count": len(tables),
            "total_rows": sum(table_stats.values()),
            "tables": table_stats,
        }

        bar = {
            "labels": list(table_stats.keys()),
            "values": list(table_stats.values()),
        }

        line = {
            "labels": list(table_stats.keys()),
            "values": list(table_stats.values()),
        }

        pie = {
            "labels": list(table_stats.keys()),
            "values": list(table_stats.values()),
        }

        return {
            "cards": cards,
            "bar": bar,
            "line": line,
            "pie": pie,
        }
    except Exception as e:
        print(f"Dashboard data error: {e}")
        return {
            "cards": {
                "table_count": 0,
                "total_rows": 0,
                "tables": {},
            },
            "bar": {"labels": [], "values": []},
            "line": {"labels": [], "values": []},
            "pie": {"labels": [], "values": []},
        }
