"""backend/app/connectors/file_connectors.py

File-based Data Source Connectors for BG AI 2.0:
- CSVConnector: loads CSV files into isolated relational SQLite engine
- ExcelConnector: loads Excel sheets into relational tables
- JSONConnector: loads JSON documents into structured tables with schema inference
"""

from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text

from app.connectors.base import (
    BaseConnector,
    ConnectorCategory,
    ConnectorStatus,
    QueryResult,
)
from app.connectors.relational import RelationalConnector


def _sanitize_table_name(name: str) -> str:
    """Sanitize file/sheet name to safe SQL table identifier."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_").lower()
    if not clean or clean[0].isdigit():
        clean = f"tbl_{clean}"
    return clean


def _infer_type(val: str) -> str:
    """Infer SQLite column type from string sample."""
    if val is None or val == "":
        return "TEXT"
    val = val.strip()
    if val.lower() in ("true", "false"):
        return "INTEGER"
    # Integer check
    if re.match(r"^-?\d+$", val):
        return "INTEGER"
    # Float check
    if re.match(r"^-?\d*\.\d+$", val):
        return "REAL"
    # Date check
    if re.match(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?$", val):
        return "TIMESTAMP"
    return "TEXT"


class CSVConnector(RelationalConnector):
    """
    Connects to CSV file(s) and provides full SQL querying via an isolated
    in-memory/file-backed SQLite relational engine.
    """

    def __init__(
        self,
        connection_id: str,
        name: str,
        file_path: str,
        delimiter: str = ",",
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="csv",
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.file_path = str(file_path)
        self.delimiter = delimiter
        self.category = ConnectorCategory.FILE

    def connect(self) -> bool:
        try:
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"CSV file not found: {self.file_path}")

            # Create an in-memory SQLite engine
            self._engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
            )

            # Load CSV into table
            table_name = _sanitize_table_name(Path(self.file_path).stem)
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f, delimiter=self.delimiter)
                headers = next(reader, None)
                if not headers:
                    raise ValueError("CSV file is empty or has no header row.")

                clean_cols = [_sanitize_table_name(h) for h in headers]
                # Ensure unique columns
                seen: set[str] = set()
                final_cols: List[str] = []
                for c in clean_cols:
                    col_name = c
                    idx = 2
                    while col_name in seen:
                        col_name = f"{c}_{idx}"
                        idx += 1
                    seen.add(col_name)
                    final_cols.append(col_name)

                # Read sample rows to infer column types
                sample_rows: List[List[str]] = []
                for _ in range(50):
                    try:
                        r = next(reader)
                        sample_rows.append(r)
                    except StopIteration:
                        break

                col_types: List[str] = []
                for col_idx in range(len(final_cols)):
                    types_seen = set()
                    for r in sample_rows:
                        if col_idx < len(r):
                            types_seen.add(_infer_type(r[col_idx]))
                    if "TEXT" in types_seen or not types_seen:
                        col_types.append("TEXT")
                    elif "REAL" in types_seen:
                        col_types.append("REAL")
                    elif "INTEGER" in types_seen:
                        col_types.append("INTEGER")
                    elif "TIMESTAMP" in types_seen:
                        col_types.append("TIMESTAMP")
                    else:
                        col_types.append("TEXT")

                col_defs = ", ".join(f'"{c}" {t}' for c, t in zip(final_cols, col_types))

                with self._engine.begin() as conn:
                    conn.execute(text(f'CREATE TABLE "{table_name}" ({col_defs})'))
                    placeholders = ", ".join([f":c{i}" for i in range(len(final_cols))])
                    insert_sql = text(f'INSERT INTO "{table_name}" VALUES ({placeholders})')

                    # Insert sample rows first
                    for r in sample_rows:
                        row_dict = {
                            f"c{i}": (r[i] if i < len(r) and r[i] != "" else None)
                            for i in range(len(final_cols))
                        }
                        conn.execute(insert_sql, row_dict)

                    # Insert remainder of file
                    for r in reader:
                        row_dict = {
                            f"c{i}": (r[i] if i < len(r) and r[i] != "" else None)
                            for i in range(len(final_cols))
                        }
                        conn.execute(insert_sql, row_dict)

            self.touch_connected()
            return True
        except Exception as e:
            self.mark_error(str(e))
            return False

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "csv",
            "file_name": Path(self.file_path).name,
            "delimiter": self.delimiter,
            "size": f"{os.path.getsize(self.file_path) / 1024:.1f} KB" if os.path.exists(self.file_path) else "0 KB",
        }


class ExcelConnector(RelationalConnector):
    """
    Connects to Excel (.xlsx/.xls) workbook, creating an isolated relational table
    for each sheet in the workbook.
    """

    def __init__(
        self,
        connection_id: str,
        name: str,
        file_path: str,
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="excel",
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.file_path = str(file_path)
        self.category = ConnectorCategory.FILE

    def connect(self) -> bool:
        try:
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"Excel file not found: {self.file_path}")

            # Check openpyxl availability
            try:
                import openpyxl
            except ImportError:
                raise RuntimeError(
                    "Python library 'openpyxl' is required to process Excel workbooks. "
                    "Install with: pip install openpyxl"
                )

            self._engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
            )

            wb = openpyxl.load_workbook(self.file_path, data_only=True, read_only=True)

            with self._engine.begin() as conn:
                for sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    table_name = _sanitize_table_name(sheet_name)
                    rows_iter = sheet.iter_rows(values_only=True)
                    headers = next(rows_iter, None)
                    if not headers:
                        continue

                    clean_cols = [
                        _sanitize_table_name(str(h) if h is not None else f"col_{idx}")
                        for idx, h in enumerate(headers)
                    ]
                    # Ensure unique
                    seen: set[str] = set()
                    final_cols: List[str] = []
                    for c in clean_cols:
                        col_name = c
                        idx = 2
                        while col_name in seen:
                            col_name = f"{c}_{idx}"
                            idx += 1
                        seen.add(col_name)
                        final_cols.append(col_name)

                    col_defs = ", ".join(f'"{c}" TEXT' for c in final_cols)
                    conn.execute(text(f'CREATE TABLE "{table_name}" ({col_defs})'))

                    placeholders = ", ".join([f":c{i}" for i in range(len(final_cols))])
                    insert_sql = text(f'INSERT INTO "{table_name}" VALUES ({placeholders})')

                    for r in rows_iter:
                        if not any(r):
                            continue
                        row_dict = {
                            f"c{i}": (str(r[i]) if i < len(r) and r[i] is not None else None)
                            for i in range(len(final_cols))
                        }
                        conn.execute(insert_sql, row_dict)

            wb.close()
            self.touch_connected()
            return True
        except Exception as e:
            self.mark_error(str(e))
            return False

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "excel",
            "file_name": Path(self.file_path).name,
            "size": f"{os.path.getsize(self.file_path) / 1024:.1f} KB" if os.path.exists(self.file_path) else "0 KB",
        }


class JSONConnector(RelationalConnector):
    """
    Connects to JSON file (array of records or nested objects) and transforms
    into an isolated SQLite table for full SQL queries and AI intelligence.
    """

    def __init__(
        self,
        connection_id: str,
        name: str,
        file_path: str,
        is_read_only: bool = False,
        user_id: str = "default_user",
    ):
        super().__init__(
            connection_id=connection_id,
            name=name,
            connector_type="json",
            is_read_only=is_read_only,
            user_id=user_id,
        )
        self.file_path = str(file_path)
        self.category = ConnectorCategory.FILE

    def connect(self) -> bool:
        try:
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"JSON file not found: {self.file_path}")

            with open(self.file_path, "r", encoding="utf-8") as f:
                content = json.load(f)

            table_name = _sanitize_table_name(Path(self.file_path).stem)
            self._engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
            )

            # Extract list of records
            records: List[Dict[str, Any]] = []
            if isinstance(content, list):
                records = [r for r in content if isinstance(r, dict)]
            elif isinstance(content, dict):
                # If dict has a main array key
                for k, v in content.items():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        records = v
                        table_name = _sanitize_table_name(k)
                        break
                if not records:
                    records = [content]

            if not records:
                raise ValueError("JSON file does not contain a list of structured records.")

            # Collect columns
            columns_set: set[str] = set()
            for r in records[:100]:
                columns_set.update(r.keys())

            final_cols = [_sanitize_table_name(k) for k in sorted(list(columns_set))]
            col_map = {orig: _sanitize_table_name(orig) for orig in columns_set}

            col_defs = ", ".join(f'"{c}" TEXT' for c in final_cols)

            with self._engine.begin() as conn:
                conn.execute(text(f'CREATE TABLE "{table_name}" ({col_defs})'))
                placeholders = ", ".join([f":{c}" for c in final_cols])
                insert_sql = text(f'INSERT INTO "{table_name}" VALUES ({placeholders})')

                for r in records:
                    row_dict = {}
                    for orig_k, clean_k in col_map.items():
                        val = r.get(orig_k)
                        if isinstance(val, (dict, list)):
                            row_dict[clean_k] = json.dumps(val)
                        elif val is not None:
                            row_dict[clean_k] = str(val)
                        else:
                            row_dict[clean_k] = None
                    conn.execute(insert_sql, row_dict)

            self.touch_connected()
            return True
        except Exception as e:
            self.mark_error(str(e))
            return False

    def to_sanitized_config(self) -> Dict[str, Any]:
        return {
            "type": "json",
            "file_name": Path(self.file_path).name,
            "size": f"{os.path.getsize(self.file_path) / 1024:.1f} KB" if os.path.exists(self.file_path) else "0 KB",
        }

