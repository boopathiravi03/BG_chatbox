from app.tools.get_schema import get_schema
from app.database.database_manager import get_engine
from sqlalchemy import inspect


def _safe_name(name: str) -> str:
    """
    Make a database identifier safe for Mermaid.
    Mermaid entity names should not contain spaces or special characters.
    """
    name = str(name).strip()

    safe = ""
    for char in name:
        if char.isalnum() or char == "_":
            safe += char
        else:
            safe += "_"

    if not safe:
        safe = "table"

    if safe[0].isdigit():
        safe = "t_" + safe

    return safe


def _safe_type(value) -> str:
    """
    Convert SQLAlchemy column type to a Mermaid-safe type.
    """
    value = str(value).strip().upper()

    # Mermaid ER syntax is safer with simple type names.
    replacements = {
        "VARCHAR": "VARCHAR",
        "CHARACTER VARYING": "VARCHAR",
        "INTEGER": "INT",
        "BIGINTEGER": "BIGINT",
        "SMALLINTEGER": "SMALLINT",
        "BOOLEAN": "BOOLEAN",
        "DATETIME": "DATETIME",
        "TIMESTAMP": "TIMESTAMP",
        "DATE": "DATE",
        "FLOAT": "FLOAT",
        "DOUBLE": "DOUBLE",
        "DECIMAL": "DECIMAL",
        "NUMERIC": "DECIMAL",
        "TEXT": "TEXT",
    }

    for source, target in replacements.items():
        if value.startswith(source):
            return target

    # Remove problematic characters
    cleaned = ""

    for char in value:
        if char.isalnum() or char == "_":
            cleaned += char

    return cleaned or "STRING"


def generate_flowchart() -> str:
    """
    Generate a Mermaid ER diagram directly from the LIVE database.

    IMPORTANT:
    - Does NOT use AI to generate Mermaid.
    - Does NOT assume customers/products/students.
    - Reads the currently connected database.
    - Produces Mermaid syntax compatible with Mermaid 11.x.
    """

    try:
        engine = get_engine()

        if engine is None:
            return """erDiagram
    DATABASE {
        STRING status
    }
    """

        inspector = inspect(engine)

        tables = inspector.get_table_names()

        if not tables:
            return """erDiagram
    DATABASE {
        STRING status
    }
    """

        lines = ["erDiagram"]

        table_map = {}

        # ---------------------------------------------------------
        # TABLES + COLUMNS
        # ---------------------------------------------------------

        for table in tables:

            safe_table = _safe_name(table)
            table_map[table] = safe_table

            lines.append(f"    {safe_table} {{")

            try:
                columns = inspector.get_columns(table)
            except Exception:
                columns = []

            try:
                pk_info = inspector.get_pk_constraint(table)
                pk_columns = set(
                    pk_info.get("constrained_columns") or []
                )
            except Exception:
                pk_columns = set()

            try:
                foreign_keys = inspector.get_foreign_keys(table)
                fk_columns = set()

                for fk in foreign_keys:
                    for column in fk.get("constrained_columns") or []:
                        fk_columns.add(column)

            except Exception:
                fk_columns = set()

            for column in columns:

                column_name = column.get("name")

                if not column_name:
                    continue

                safe_column = _safe_name(column_name)

                column_type = _safe_type(
                    column.get("type", "STRING")
                )

                attributes = []

                if column_name in pk_columns:
                    attributes.append("PK")

                if column_name in fk_columns:
                    attributes.append("FK")

                attribute_text = ""

                if attributes:
                    attribute_text = " " + " ".join(attributes)

                lines.append(
                    f"        {column_type} {safe_column}{attribute_text}"
                )

            lines.append("    }")

        # ---------------------------------------------------------
        # FOREIGN KEY RELATIONSHIPS
        # ---------------------------------------------------------

        relationships = set()

        for table in tables:

            safe_table = table_map.get(
                table,
                _safe_name(table)
            )

            try:
                foreign_keys = inspector.get_foreign_keys(table)
            except Exception:
                foreign_keys = []

            for fk in foreign_keys:

                referred_table = fk.get(
                    "referred_table"
                )

                if not referred_table:
                    continue

                if referred_table not in table_map:
                    continue

                safe_referred = table_map[
                    referred_table
                ]

                # Avoid duplicate relationship lines
                relationship_key = (
                    safe_table,
                    safe_referred
                )

                if relationship_key in relationships:
                    continue

                relationships.add(
                    relationship_key
                )

                lines.append(
                    f"    {safe_referred} ||--o{{ {safe_table} : has"
                )

        return "\n".join(lines)

    except Exception as e:

        # Always return valid Mermaid instead of breaking frontend.
        return f"""erDiagram
    DATABASE {{
        STRING error
    }}
"""
