"""
Single source of truth for insert-form column rules.

Background
----------
BG AI previously decided whether a column was auto-generated in two
different places, with two different rules:

* ``crud/router.py::_handle_create`` built the form fields, and
* ``crud/router.py::_handle_insert_form`` validated the submission.

Both relied on ``autoincrement`` and ``server_default`` keys that
SQLAlchemy's ``Inspector.get_columns()`` simply does not return for
SQLite. That method only exposes:

    name, type, nullable, default, primary_key

Because neither key was ever present, the "auto-generated" branch never
fired, and an ``INTEGER PRIMARY KEY`` column (``customer_id``) was
treated as a required user-supplied field. Every INSERT therefore failed
with ``missing_fields: ["customer_id"]``.

The rules below depend only on metadata the inspector actually
provides, so they behave identically on SQLite, MySQL and PostgreSQL.
"""

from __future__ import annotations


# Audit columns that the database (or an ORM hook) manages.
_AUDIT_COLUMNS = frozenset({
    "created_at",
    "updated_at",
    "deleted_at",
})

# Markers identifying integer-family types across the supported
# dialects: INTEGER, INT, BIGINT, SMALLINT, MEDIUMINT, TINYINT.
_INTEGER_TYPE_MARKERS = ("int",)

# Markers for non-integer numeric types.
_DECIMAL_TYPE_MARKERS = (
    "decimal",
    "numeric",
    "float",
    "double",
    "real",
    "money",
)

# Markers for temporal types.
_TEMPORAL_TYPE_MARKERS = (
    "date",
    "time",
)

# Markers for boolean types.
_BOOLEAN_TYPE_MARKERS = ("bool",)


def _type_text(metadata: dict) -> str:
    """Return the column's declared type as lowercase text."""

    if not isinstance(metadata, dict):
        return ""

    return str(metadata.get("type", "")).lower()


def _matches(column_type: str, markers: tuple[str, ...]) -> bool:
    return any(marker in column_type for marker in markers)


def is_integer_column(metadata: dict) -> bool:
    """True when the declared type belongs to the integer family."""

    return _matches(
        _type_text(metadata),
        _INTEGER_TYPE_MARKERS,
    )


def is_auto_generated_column(
    column_name: str,
    metadata: dict,
) -> bool:
    """
    True when the database supplies this value, so the user must not
    be asked for it.

    Signals, in order of reliability:

    1. Known audit columns.
    2. An explicit column default.
    3. An explicit server default (when the dialect reports one).
    4. An explicit autoincrement flag (when the dialect reports one).
    5. An integer primary key -- the surrogate-key convention used by
       SQLite, MySQL and PostgreSQL alike.

    Signal 5 is what makes this dialect-independent.
    """

    if not isinstance(metadata, dict):
        return False

    if column_name.lower() in _AUDIT_COLUMNS:
        return True

    if metadata.get("default") is not None:
        return True

    if metadata.get("server_default") is not None:
        return True

    if metadata.get("autoincrement") is True:
        return True

    return bool(
        metadata.get("primary_key")
        and is_integer_column(metadata)
    )


def is_required_column(
    column_name: str,
    metadata: dict,
) -> bool:
    """
    True when the user must supply a value for this column for an
    INSERT to succeed.
    """

    if is_auto_generated_column(column_name, metadata):
        return False

    if not isinstance(metadata, dict):
        return False

    return not metadata.get("nullable", True)


def required_insert_columns(
    table_schema: dict,
) -> list[str]:
    """Return the columns the user must provide, in schema order."""

    if not isinstance(table_schema, dict):
        return []

    return [
        column_name
        for column_name, metadata in table_schema.items()
        if is_required_column(column_name, metadata)
    ]


def field_type_for(
    column_name: str,
    metadata: dict,
) -> str:
    """
    Map a column to the input type used by the insert form.

    Returns one of: number, boolean, date, email, text.
    """

    column_type = _type_text(metadata)
    name = column_name.lower()

    if _matches(column_type, _INTEGER_TYPE_MARKERS):
        field_type = "number"
    elif _matches(column_type, _DECIMAL_TYPE_MARKERS):
        field_type = "number"
    elif _matches(column_type, _BOOLEAN_TYPE_MARKERS):
        field_type = "boolean"
    elif _matches(column_type, _TEMPORAL_TYPE_MARKERS):
        field_type = "date"
    else:
        field_type = "text"

    if "email" in name:
        field_type = "email"

    return field_type


def build_insert_form_fields(
    table_schema: dict,
) -> list[dict]:
    """
    Build the insert-form field descriptors for a table.

    Auto-generated columns are omitted entirely so the user is never
    asked for a value the database produces itself.
    """

    if not isinstance(table_schema, dict):
        return []

    fields: list[dict] = []

    for column_name, metadata in table_schema.items():

        if is_auto_generated_column(column_name, metadata):
            continue

        fields.append({
            "name": column_name,
            "label": column_name.replace("_", " ").title(),
            "type": field_type_for(column_name, metadata),
            "required": is_required_column(column_name, metadata),
        })

    return fields
