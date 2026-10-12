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
            with self._engine.connect() as conn:
                res = conn.execute(text("SELECT 1"))
                val = res.scalar()
            elapsed_ms = (time.perf_counter() - start) * 1000

            return {
                "success": True,
                "connected": True,
                "latency_ms": round(elapsed_ms, 2),
                "message": "Connection healthy and responsive",
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

        if self._engine is None:
            if not self.connect():
                return {}

        schema: Dict[str, Any] = {}
        try:
            inspector = inspect(self._engine)
            table_names = inspector.get_table_names()

            for table_name in table_names:
                cols = inspector.get_columns(table_name)
                fks = inspector.get_foreign_keys(table_name)
                fk_map = {fk.get("constrained_columns", [""])[0]: fk for fk in fks if fk.get("constrained_columns")}

                schema[table_name] = {}
                for col in cols:
                    col_name = col["name"]
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
        if self._engine is None:
            return {"tables": 0, "rows": 0, "columns": 0}

        try:
            schema = self.get_schema()
            total_tables = len(schema)
            total_columns = sum(len(cols) for cols in schema.values())
            total_rows = 0

            with self._engine.connect() as conn:
                for table in list(schema.keys())[:50]:  # Cap check to first 50 tables
                    try:
                        # Dialect quoting fallback
                        t_quoted = f'"{table}"' if self.connector_type in ("postgres", "sqlite") else f"`{table}`"
                        r = conn.execute(text(f"SELECT COUNT(*) FROM {t_quoted}"))
                        total_rows += r.scalar() or 0
                    except Exception:
                        pass

            return {
                "tables": total_tables,
                "columns": total_columns,
                "rows": total_rows,
            }
        except Exception:
            return {"tables": 0, "rows": 0, "columns": 0}

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

