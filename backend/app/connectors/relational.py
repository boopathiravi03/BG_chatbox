"""backend/app/connectors/relational.py

Relational database connectors for BG AI 2.0 using SQLAlchemy:
- SQLiteConnector
- MySQLConnector
- PostgreSQLConnector
- MSSQLConnector
- MariaDBConnector
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    URL,
    Engine,
    create_engine,
    inspect,
    text,
)

from app.connectors.base import (
    BaseConnector,
    ConnectorCapabilities,
    ConnectorCategory,
    ConnectorStatus,
    QueryResult,
)

READ_ONLY_STARTERS = {"select", "with", "pragma", "show", "describe", "explain"}
MUTATION_STARTERS = {"insert", "update", "delete", "replace"}
DDL_STARTERS = {"drop", "alter", "truncate", "create"}


class RelationalConnector(BaseConnector):
    """Base class for all SQLAlchemy-backed relational database connectors."""

    def __init__(
        self,
        connection_id: str,
        name: str,
        connector_type: str,
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type=connector_type,
            category=ConnectorCategory.RELATIONAL,
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self._engine: Optional[Engine] = None

    @property
    def engine(self) -> Optional[Engine]:
        """Direct access to the connector's isolated SQLAlchemy engine."""
        return self._engine

    def disconnect(self) -> bool:
        """Safely dispose the engine and connection pool."""
        if self._engine is not None:
            try:
                self._engine.dispose()
            except Exception:
                pass
            self._engine = None

        self.status = ConnectorStatus.DISCONNECTED
        self.clear_schema_cache()
        return True

    def test_connection(self) -> Dict[str, Any]:
        """Test live connectivity."""
        if self._engine is None:
            ok = self.connect()
            if not ok:
                return {
                    "success": False,
                    "connected": False,
                    "error": self.last_error or "Failed to connect",
                }

        try:
            start = time.perf_counter()
            server_read_only = False
            privilege_info = "Read/Write"

            with self._engine.connect() as conn:
                res = conn.execute(text("SELECT 1"))
                val = res.scalar()

                if not self.is_read_only:
                    try:
                        if self.connector_type == "postgres":
                            ro_check = conn.execute(text("SELECT pg_is_in_recovery()")).scalar()
                            if ro_check:
                                server_read_only = True
                                privilege_info = "PostgreSQL Standby / Replica (Read-Only)"
                        elif self.connector_type in ("mysql", "mariadb"):
                            ro_check = conn.execute(text("SELECT @@read_only")).scalar()
                            if ro_check:
                                server_read_only = True
                                privilege_info = "MySQL Server global read_only=ON"
                    except Exception:
                        pass

            elapsed_ms = (time.perf_counter() - start) * 1000

            return {
                "success": True,
                "connected": True,
                "latency_ms": round(elapsed_ms, 2),
                "is_read_only": self.is_read_only or server_read_only,
                "server_read_only": server_read_only,
                "access_mode": "Read-Only" if (self.is_read_only or server_read_only) else "Read/Write",
                "message": f"Connection healthy ({privilege_info})",
                "capabilities": self.get_capabilities().to_dict(),
            }
        except Exception as e:
            self.mark_error(str(e))
            return {
                "success": False,
                "connected": False,
                "error": str(e),
            }

    def get_schema(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Inspect schema: tables, columns, primary keys, foreign keys."""
        now = time.time()
        if (
            not force_refresh
            and self._schema_cache is not None
            and (now - self._schema_cached_at) < self._cache_ttl_seconds
        ):
            return self._schema_cache

        if self._engine is None and not self.connect():
            return {}

        schema: Dict[str, Any] = {}
        try:
            inspector = inspect(self._engine)
            table_names = inspector.get_table_names()

            for table_name in table_names:
                try:
                    cols = inspector.get_columns(table_name)
                except Exception:
                    cols = []
                try:
                    fks = inspector.get_foreign_keys(table_name)
                except Exception:
                    fks = []
                fk_map = {fk.get("constrained_columns", [""])[0]: fk for fk in fks if fk.get("constrained_columns")}

                schema[table_name] = {}
                for col in cols:
                    col_name = col.get("name", "unknown")
                    fk_info = fk_map.get(col_name)
                    schema[table_name][col_name] = {
                        "type": str(col.get("type", "TEXT")),
                        "nullable": bool(col.get("nullable", True)),
                        "primary_key": bool(col.get("primary_key", False)),
                        "default": str(col.get("default")) if col.get("default") is not None else None,
                        "foreign_key": {
                            "referred_table": fk_info.get("referred_table"),
                            "referred_columns": fk_info.get("referred_columns"),
                        } if fk_info else None,
                    }

            self._schema_cache = schema
            self._schema_cached_at = now
            return schema
        except Exception as e:
            self.mark_error(f"Schema inspection failed: {str(e)}")
            return {}

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate statistical metadata for the database."""
        if self._engine is None and not self.connect():
            try:
                from app.database.database_manager import get_engine
                eng = get_engine()
                if eng is not None:
                    self._engine = eng
                    self.touch_connected()
            except Exception:
                pass
            if self._engine is None:
                return {"tables": 0, "rows": 0, "columns": 0}

        try:
            schema = self.get_schema()
            total_tables = len(schema)
            total_columns = sum(len(cols) for cols in schema.values())
            total_rows = 0

            with self._engine.connect() as conn:
                # Fast dialect-specific row count retrieval
                if self.connector_type in ("mysql", "mariadb"):
                    try:
                        db_name = (
                            getattr(self, "database", None)
                            or (getattr(self._engine.url, "database", None) if hasattr(self._engine, "url") else None)
                            or ""
                        )
                        if db_name:
                            r = conn.execute(
                                text(
                                    "SELECT COALESCE(SUM(TABLE_ROWS), 0) FROM information_schema.tables "
                                    "WHERE TABLE_SCHEMA = :db AND TABLE_TYPE = 'BASE TABLE'"
                                ),
                                {"db": db_name},
                            )
                            val = r.scalar()
                            if val is not None:
                                total_rows = int(val)
                    except Exception:
                        pass
                elif self.connector_type == "postgres":
                    try:
                        r = conn.execute(
                            text(
                                "SELECT COALESCE(SUM(n_live_tup), 0) FROM pg_stat_user_tables"
                            )
                        )
                        val = r.scalar()
                        if val is not None:
                            total_rows = int(val)
                    except Exception:
                        pass

                # Fallback: if total_rows is 0 and tables exist, query COUNT(*) on tables
                if total_rows == 0 and total_tables > 0:
                    for table in list(schema.keys())[:50]:
                        try:
                            t_quoted = (
                                f'"{table}"'
                                if self.connector_type in ("postgres", "sqlite")
                                else f"`{table}`"
                            )
                            r = conn.execute(text(f"SELECT COUNT(*) FROM {t_quoted}"))
                            cnt = r.scalar()
                            if cnt is not None:
                                total_rows += int(cnt)
                        except Exception:
                            pass

            return {
                "tables": total_tables,
                "columns": total_columns,
                "rows": total_rows,
            }
        except Exception:
            schema = self._schema_cache or {}
            col_count = sum(len(cols) for cols in schema.values()) if schema else 0
            return {
                "tables": len(schema),
                "columns": col_count,
                "rows": 0,
            }

    def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """Execute SQL query safely with dialect awareness and timeout."""
        if self._engine is None:
            if not self.connect():
                return QueryResult(
                    success=False,
                    error="Database is not connected.",
                    query_dialect=self.connector_type,
                    source_id=self.connection_id,
                    source_name=self.name,
                )

        clean = query.strip()
        first_word = clean.split()[0].lower() if clean else ""

        # Enforce read-only constraint
        if self.is_read_only and first_word in (MUTATION_STARTERS | DDL_STARTERS):
            return QueryResult(
                success=False,
                error=f"Connection '{self.name}' is configured as READ-ONLY. Mutation '{first_word.upper()}' is forbidden.",
                query_dialect=self.connector_type,
                source_id=self.connection_id,
                source_name=self.name,
            )

        start = time.perf_counter()
        try:
            with self._engine.connect() as conn:
                # Add statement timeout if supported
                if self.connector_type == "postgres":
                    try:
                        conn.execute(text("SET statement_timeout = 30000;"))
                    except Exception:
                        pass

                stmt = text(clean)
                result_proxy = conn.execute(stmt, params or {})

                elapsed_ms = (time.perf_counter() - start) * 1000

                if result_proxy.returns_rows:
                    cols = list(result_proxy.keys())
                    raw_rows = result_proxy.fetchmany(1000)  # Max bounded rows
                    rows = [dict(zip(cols, row)) for row in raw_rows]

                    return QueryResult(
                        success=True,
                        columns=cols,
                        rows=rows,
                        rows_returned=len(rows),
                        execution_time_ms=round(elapsed_ms, 2),
                        query_dialect=self.connector_type,
                        executed_query=clean,
                        source_id=self.connection_id,
                        source_name=self.name,
                    )
                else:
                    affected = result_proxy.rowcount
                    conn.commit()
                    return QueryResult(
                        success=True,
                        columns=[],
                        rows=[],
                        rows_returned=0,
                        affected_rows=affected,
                        execution_time_ms=round(elapsed_ms, 2),
                        query_dialect=self.connector_type,
                        executed_query=clean,
                        source_id=self.connection_id,
                        source_name=self.name,
                    )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return QueryResult(
                success=False,
                error=str(e),
                execution_time_ms=round(elapsed_ms, 2),
                query_dialect=self.connector_type,
                executed_query=clean,
                source_id=self.connection_id,
                source_name=self.name,
            )

    def _quote_id(self, ident: str) -> str:
        """Safely quotes SQL identifiers according to dialect."""
        clean = ident.replace('"', "").replace("`", "").replace("[", "").replace("]", "").strip()
        if self.connector_type in ("postgres", "sqlite"):
            return f'"{clean}"'
        elif self.connector_type in ("sqlserver", "mssql"):
            return f"[{clean}]"
        else:
            return f"`{clean}`"

    def get_records(
        self,
        entity: str,
        limit: int = 25,
        offset: int = 0,
        sort_by: Optional[str] = None,
        sort_dir: str = "asc",
        search: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch paginated, sortable, searchable records from SQL table."""
        if self._engine is None and not self.connect():
            raise RuntimeError(f"Database connection '{self.name}' is not established.")

        schema = self.get_schema()
        if entity not in schema:
            raise ValueError(f"Table '{entity}' does not exist in schema.")

        table_cols = schema[entity]
        col_names = list(table_cols.keys())
        pk_list = [c for c, meta in table_cols.items() if isinstance(meta, dict) and meta.get("primary_key")]

        safe_limit = min(max(1, limit), 200)
        safe_offset = max(0, offset)
        direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"

        t_quoted = self._quote_id(entity)
        where_clauses: List[str] = []
        params: Dict[str, Any] = {"limit": safe_limit, "offset": safe_offset}

        # 1. Text search across text/varchar columns
        if search and search.strip():
            params["search_param"] = f"%{search.strip()}%"
            text_col_quotes = [
                self._quote_id(c) for c in col_names
                if any(k in str(table_cols[c].get("type", "")).upper() for k in ("CHAR", "VARCHAR", "TEXT", "STRING", "CLOB"))
            ]
            if text_col_quotes:
                search_expr = " OR ".join(f"{c} LIKE :search_param" for c in text_col_quotes[:6])
                where_clauses.append(f"({search_expr})")

        # 2. Key-value exact or pattern filters
        if filters and isinstance(filters, dict):
            for i, (f_col, f_val) in enumerate(filters.items()):
                if f_col in table_cols and f_val is not None:
                    p_key = f"filter_{i}"
                    params[p_key] = f_val
                    where_clauses.append(f"{self._quote_id(f_col)} = :{p_key}")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Order by
        if sort_by and sort_by in col_names:
            order_sql = f"ORDER BY {self._quote_id(sort_by)} {direction}"
        elif pk_list:
            order_sql = f"ORDER BY {self._quote_id(pk_list[0])} {direction}"
        else:
            order_sql = ""

        # Fetch records & count
        with self._engine.connect() as conn:
            # Records
            fetch_sql = f"SELECT * FROM {t_quoted} {where_sql} {order_sql} LIMIT :limit OFFSET :offset"
            data_res = conn.execute(text(fetch_sql), params)
            keys = list(data_res.keys())
            raw_rows = data_res.fetchall()
            records = [dict(zip(keys, row)) for row in raw_rows]

            # Fast count optimization: if on first page and returned rows < safe_limit, exact total is known without COUNT(*) scan
            if safe_offset == 0 and len(records) < safe_limit:
                total_count = len(records)
            else:
                count_sql = f"SELECT COUNT(*) FROM {t_quoted} {where_sql}"
                count_res = conn.execute(text(count_sql), params)
                total_count = count_res.scalar() or 0

        return {
            "success": True,
            "entity": entity,
            "records": records,
            "columns": col_names,
            "total_count": total_count,
            "limit": safe_limit,
            "offset": safe_offset,
            "primary_keys": pk_list,
            "is_read_only": self.is_read_only,
        }

    def create_record(self, entity: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a row into table using safe parameterized SQL."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY. Creating records is forbidden.")
        if self._engine is None and not self.connect():
            raise RuntimeError(f"Database connection '{self.name}' is not established.")

        schema = self.get_schema()
        if entity not in schema:
            raise ValueError(f"Table '{entity}' does not exist.")

        valid_cols = [c for c in data.keys() if c in schema[entity]]
        if not valid_cols:
            raise ValueError("No valid columns provided for insertion.")

        t_quoted = self._quote_id(entity)
        cols_quoted = ", ".join(self._quote_id(c) for c in valid_cols)
        placeholders = ", ".join(f":{c}" for c in valid_cols)
        insert_params = {c: data[c] for c in valid_cols}

        sql = f"INSERT INTO {t_quoted} ({cols_quoted}) VALUES ({placeholders})"
        with self._engine.begin() as conn:
            res = conn.execute(text(sql), insert_params)
            affected = res.rowcount

        return {
            "success": True,
            "affected_rows": affected,
            "message": f"Record inserted into '{entity}' successfully.",
        }

    def update_record(self, entity: str, primary_key: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a row identified by primary key."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY. Updating records is forbidden.")
        if self._engine is None and not self.connect():
            raise RuntimeError(f"Database connection '{self.name}' is not established.")

        schema = self.get_schema()
        if entity not in schema:
            raise ValueError(f"Table '{entity}' does not exist.")

        if not primary_key or not isinstance(primary_key, dict):
            raise ValueError("Primary key identifier dictionary is required to update record.")

        update_cols = [c for c in data.keys() if c in schema[entity] and c not in primary_key]
        if not update_cols:
            raise ValueError("No valid columns to update.")

        t_quoted = self._quote_id(entity)
        set_exprs = [f"{self._quote_id(c)} = :val_{c}" for c in update_cols]
        where_exprs = [f"{self._quote_id(pk)} = :pk_{pk}" for pk in primary_key.keys()]

        params = {}
        for c in update_cols:
            params[f"val_{c}"] = data[c]
        for pk, pk_val in primary_key.items():
            params[f"pk_{pk}"] = pk_val

        sql = f"UPDATE {t_quoted} SET {', '.join(set_exprs)} WHERE {' AND '.join(where_exprs)}"
        with self._engine.begin() as conn:
            res = conn.execute(text(sql), params)
            affected = res.rowcount

        return {
            "success": True,
            "affected_rows": affected,
            "message": f"Record in '{entity}' updated successfully ({affected} row affected).",
        }

    def delete_record(self, entity: str, primary_key: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a row identified by primary key."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY. Deleting records is forbidden.")
        if self._engine is None and not self.connect():
            raise RuntimeError(f"Database connection '{self.name}' is not established.")

        schema = self.get_schema()
        if entity not in schema:
            raise ValueError(f"Table '{entity}' does not exist.")

        if not primary_key or not isinstance(primary_key, dict):
            raise ValueError("Primary key identifier dictionary is required to delete record.")

        t_quoted = self._quote_id(entity)
        where_exprs = [f"{self._quote_id(pk)} = :pk_{pk}" for pk in primary_key.keys()]
        params = {f"pk_{pk}": pk_val for pk, pk_val in primary_key.items()}

        sql = f"DELETE FROM {t_quoted} WHERE {' AND '.join(where_exprs)}"
        with self._engine.begin() as conn:
            res = conn.execute(text(sql), params)
            affected = res.rowcount

        return {
            "success": True,
            "affected_rows": affected,
            "message": f"Record deleted from '{entity}' successfully ({affected} row deleted).",
        }

    def create_entity(self, name: str, definition: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new SQL table."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY.")
        if self._engine is None and not self.connect():
            raise RuntimeError("Database is not connected.")

        table_name = name.strip()
        t_quoted = self._quote_id(table_name)
        columns_def = (definition or {}).get("columns", [])

        col_sql_parts = []
        if columns_def:
            for col in columns_def:
                c_name = self._quote_id(col.get("name", "col"))
                c_type = col.get("type", "VARCHAR(255)")
                c_pk = " PRIMARY KEY" if col.get("primary_key") else ""
                c_null = " NOT NULL" if not col.get("nullable", True) else ""
                col_sql_parts.append(f"{c_name} {c_type}{c_pk}{c_null}")
        else:
            # Default minimal table structure
            col_sql_parts.append(f"{self._quote_id('id')} INTEGER PRIMARY KEY")
            col_sql_parts.append(f"{self._quote_id('name')} VARCHAR(255)")
            col_sql_parts.append(f"{self._quote_id('created_at')} TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        sql = f"CREATE TABLE {t_quoted} ({', '.join(col_sql_parts)});"
        with self._engine.begin() as conn:
            conn.execute(text(sql))

        self.clear_schema_cache()
        return {"success": True, "message": f"Table '{table_name}' created successfully."}

    def rename_entity(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """Rename an existing SQL table."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY.")
        if self._engine is None and not self.connect():
            raise RuntimeError("Database is not connected.")

        sql = f"ALTER TABLE {self._quote_id(old_name)} RENAME TO {self._quote_id(new_name)};"
        with self._engine.begin() as conn:
            conn.execute(text(sql))

        self.clear_schema_cache()
        return {"success": True, "message": f"Table '{old_name}' renamed to '{new_name}'."}

    def drop_entity(self, name: str) -> Dict[str, Any]:
        """Drop a SQL table."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is READ-ONLY.")
        if self._engine is None and not self.connect():
            raise RuntimeError("Database is not connected.")

        sql = f"DROP TABLE {self._quote_id(name)};"
        with self._engine.begin() as conn:
            conn.execute(text(sql))

        self.clear_schema_cache()
        return {"success": True, "message": f"Table '{name}' dropped successfully."}

    def create_index(self, entity: str, fields: List[str], index_name: Optional[str] = None, unique: bool = False) -> Dict[str, Any]:
        """Create an index on specified columns of table."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is configured as READ-ONLY.")
        if self._engine is None and not self.connect():
            raise RuntimeError("Database is not connected.")
        if not fields:
            raise ValueError("At least one column is required to create an index.")

        idx = index_name or f"idx_{entity.lower()}_{'_'.join(f.lower() for f in fields)}"
        quoted_cols = ", ".join(self._quote_id(f) for f in fields)
        unique_clause = "UNIQUE " if unique else ""
        sql = f"CREATE {unique_clause}INDEX {self._quote_id(idx)} ON {self._quote_id(entity)} ({quoted_cols});"
        with self._engine.begin() as conn:
            conn.execute(text(sql))

        self.clear_schema_cache()
        return {"success": True, "index_name": idx, "message": f"{'Unique index' if unique else 'Index'} '{idx}' created on '{entity}' ({', '.join(fields)})."}

    def drop_index(self, entity: str, index_name: str) -> Dict[str, Any]:
        """Drop an index from table."""
        if self.is_read_only:
            raise PermissionError(f"Connection '{self.name}' is configured as READ-ONLY.")
        if self._engine is None and not self.connect():
            raise RuntimeError("Database is not connected.")

        if self.connector_type in ("mysql", "mariadb"):
            sql = f"DROP INDEX {self._quote_id(index_name)} ON {self._quote_id(entity)};"
        else:
            sql = f"DROP INDEX {self._quote_id(index_name)};"

        with self._engine.begin() as conn:
            conn.execute(text(sql))

        self.clear_schema_cache()
        return {"success": True, "index_name": index_name, "message": f"Index '{index_name}' dropped successfully."}

    def get_capabilities(self) -> ConnectorCapabilities:
        if self.is_read_only:
            return ConnectorCapabilities(
                can_read_data=True,
                can_insert_records=False,
                can_update_records=False,
                can_delete_records=False,
                can_create_entities=False,
                can_alter_schema=False,
                can_manage_indexes=False,
                can_execute_raw_queries=True,
                supports_transactions=True,
                read_only_reason=f"Connection '{self.name}' is explicitly configured as Read-Only.",
            )
        return ConnectorCapabilities(
            can_read_data=True,
            can_insert_records=True,
            can_update_records=True,
            can_delete_records=True,
            can_create_entities=True,
            can_alter_schema=True,
            can_manage_indexes=True,
            can_execute_raw_queries=True,
            supports_transactions=True,
            read_only_reason=None,
        )


class SQLiteConnector(RelationalConnector):
    """Connector for SQLite databases (local files or in-memory)."""

    def __init__(
        self,
        connection_id: str,
        name: str,
        database_path: str,
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="sqlite",
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.database_path = str(database_path)

    def connect(self) -> bool:
        try:
            # Handle in-memory or file path
            is_mem = self.database_path in (":memory:", "memory")
            if is_mem:
                url_str = "sqlite:///:memory:"
            else:
                p = Path(self.database_path).resolve()
                p.parent.mkdir(parents=True, exist_ok=True)
                url_str = f"sqlite:///{p}"

            self._engine = create_engine(
                url_str,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )

            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self.touch_connected()
            return True
        except Exception as e:
            self.mark_error(str(e))
            return False

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "sqlite",
            "database_path": str(Path(self.database_path).name) if self.database_path != ":memory:" else ":memory:",
            "full_path_redacted": True,
        }

    def get_stats(self) -> Dict[str, Any]:
        stats = super().get_stats()
        try:
            if self.database_path not in (":memory:", "memory") and os.path.exists(self.database_path):
                size_bytes = os.path.getsize(self.database_path)
                stats["size"] = f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes > 1024 * 1024 else f"{size_bytes / 1024:.1f} KB"
        except Exception:
            pass
        return stats


class MySQLConnector(RelationalConnector):
    """Connector for MySQL databases using PyMySQL."""

    def __init__(
        self,
        connection_id: str,
        name: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="mysql",
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.host = host
        self.port = int(port)
        self.database = database
        self.username = username
        self._password = password

    def connect(self) -> bool:
        try:
            mysql_url = URL.create(
                drivername="mysql+pymysql",
                username=self.username,
                password=self._password,
                host=self.host,
                port=self.port,
                database=self.database,
            )
            self._engine = create_engine(
                mysql_url,
                pool_pre_ping=True,
                pool_recycle=1800,
            )
            with self._engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")

            self.touch_connected()
            return True
        except Exception as e:
            self.mark_error(str(e))
            return False

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "mysql",
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": "***",
        }


class MariaDBConnector(RelationalConnector):
    """Connector for MariaDB databases using MySQL protocol."""

    def __init__(
        self,
        connection_id: str,
        name: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="mariadb",
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.host = host
        self.port = int(port)
        self.database = database
        self.username = username
        self._password = password

    def connect(self) -> bool:
        try:
            mariadb_url = URL.create(
                drivername="mysql+pymysql",
                username=self.username,
                password=self._password,
                host=self.host,
                port=self.port,
                database=self.database,
            )
            self._engine = create_engine(
                mariadb_url,
                pool_pre_ping=True,
                pool_recycle=1800,
            )
            with self._engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")

            self.touch_connected()
            return True
        except Exception as e:
            self.mark_error(str(e))
            return False

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "mariadb",
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": "***",
        }


class PostgreSQLConnector(RelationalConnector):
    """Connector for PostgreSQL databases using psycopg2."""

    def __init__(
        self,
        connection_id: str,
        name: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="postgres",
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.host = host
        self.port = int(port)
        self.database = database
        self.username = username
        self._password = password

    def connect(self) -> bool:
        try:
            postgres_url = URL.create(
                drivername="postgresql+psycopg2",
                username=self.username,
                password=self._password,
                host=self.host,
                port=self.port,
                database=self.database,
            )
            self._engine = create_engine(
                postgres_url,
                pool_pre_ping=True,
                pool_recycle=1800,
            )
            with self._engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")

            self.touch_connected()
            return True
        except Exception as e:
            self.mark_error(str(e))
            return False

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "postgres",
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": "***",
        }


class MSSQLConnector(RelationalConnector):
    """Connector for Microsoft SQL Server databases."""

    def __init__(
        self,
        connection_id: str,
        name: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        driver: str = "ODBC Driver 18 for SQL Server",
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="sqlserver",
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.host = host
        self.port = int(port or 1433)
        self.database = database
        self.username = username
        self._password = password
        self.driver = driver

    def connect(self) -> bool:
        try:
            # Check pyodbc availability or fallback dialect
            try:
                import pyodbc
                has_pyodbc = True
            except ImportError:
                has_pyodbc = False

            if has_pyodbc:
                mssql_url = URL.create(
                    drivername="mssql+pyodbc",
                    username=self.username,
                    password=self._password,
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    query={"driver": self.driver, "TrustServerCertificate": "yes"},
                )
                self._engine = create_engine(mssql_url, pool_pre_ping=True)
                with self._engine.connect() as conn:
                    conn.exec_driver_sql("SELECT 1")
            else:
                # If pyodbc is not installed in the environment, record informative error
                raise RuntimeError(
                    "Python driver 'pyodbc' is not installed in the environment for Microsoft SQL Server. "
                    "Install pyodbc with: pip install pyodbc"
                )

            self.touch_connected()
            return True
        except Exception as e:
            self.mark_error(str(e))
            return False

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "sqlserver",
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "driver": self.driver,
            "password": "***",
        }

