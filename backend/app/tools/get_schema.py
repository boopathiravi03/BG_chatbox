"""backend/app/tools/get_schema.py

Schema introspection tool for BG AI 2.0 with multi-database support.
"""

from typing import Any, Dict, Optional
from sqlalchemy import inspect
from app.database.database_manager import get_engine
from app.database.connection_context import get_request_user_id


def get_schema(connection_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns the schema dictionary for the active or specified connection.
    If multi-database connector is present, uses its schema discovery.
    Otherwise inspects the active SQLAlchemy engine.
    """
    from app.database.connection_context import get_request_connection_id
    target_cid = connection_id or get_request_connection_id()

    user_id = get_request_user_id()
    if user_id:
        try:
            from app.connectors.registry import get_connection_registry
            reg = get_connection_registry()
            connector = None
            if target_cid:
                connector = reg.get_connector(user_id, target_cid)
            if not connector:
                connector = reg.get_active_connector(user_id)

            if connector:
                return connector.get_schema()
        except Exception:
            pass

    engine = get_engine()
    if engine is None:
        raise RuntimeError("No database is currently connected.")

    inspector = inspect(engine)
    schema: Dict[str, Any] = {}

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
