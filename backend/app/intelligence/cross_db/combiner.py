"""backend/app/intelligence/cross_db/combiner.py

Application-Layer Data Combiner for BG AI 2.0.
Combines subquery results from independent database engines using key matching,
metric comparison, or federated aggregation. Explains data provenance clearly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.intelligence.cross_db.models import SourceQueryResult


class CrossDatabaseCombiner:
    """Combines and synthesizes multi-source query results in the application layer."""

    @classmethod
    def combine(
        cls,
        sub_results: List[SourceQueryResult],
        user_message: str,
    ) -> Tuple[Optional[Dict[str, Any]], str, str]:
        """
        Returns:
        (combined_result_dict, explanation, combination_strategy)
        """
        successful = [r for r in sub_results if r.success]

        if not successful:
            return (
                None,
                "All sub-queries to connected databases failed to execute.",
                "none",
            )

        if len(successful) == 1:
            res = successful[0]
            explanation = (
                f"Query executed on **{res.source_name}** ({res.connector_type}).\n\n"
                f"- **Executed query:** `{res.query_text}`\n"
                f"- **Rows returned:** {res.rows_returned} (in {res.execution_time_ms}ms)"
            )
            combined = {
                "columns": res.columns,
                "rows": res.rows,
                "rows_returned": res.rows_returned,
                "source": res.source_name,
            }
            return combined, explanation, "direct"

        # Multi-source combination:
        # Check Strategy 1: Common Key Join
        join_res = cls._try_common_key_join(successful)
        if join_res is not None:
            combined_rows, combined_cols, join_key = join_res
            strategy = "key_join"
            explanation = (
                f"Combined data from **{len(successful)} independent databases** "
                f"in the application layer using common key `{join_key}`:\n\n"
            )
            for r in successful:
                explanation += f"- **{r.source_name}** ({r.connector_type}): `{r.query_text}` ({r.rows_returned} rows)\n"

            explanation += f"\nMerged {len(combined_rows)} correlated records."
            combined = {
                "columns": combined_cols,
                "rows": combined_rows,
                "rows_returned": len(combined_rows),
                "join_key": join_key,
            }
            return combined, explanation, strategy

        # Strategy 2: Multi-metric side-by-side comparison
        metric_res = cls._try_metric_comparison(successful)
        if metric_res is not None:
            combined_rows, combined_cols = metric_res
            strategy = "multi_metric"
            explanation = (
                f"Compared metrics across **{len(successful)} databases**:\n\n"
            )
            for r in successful:
                explanation += f"- **{r.source_name}** ({r.connector_type}): `{r.query_text}`\n"

            combined = {
                "columns": combined_cols,
                "rows": combined_rows,
                "rows_returned": len(combined_rows),
            }
            return combined, explanation, strategy

        # Strategy 3: Multi-source overview union
        strategy = "union_overview"
        combined_rows = []
        for r in successful:
            for row in r.rows:
                tagged = dict(row)
                tagged["_source_database"] = r.source_name
                combined_rows.append(tagged)

        all_cols = ["_source_database"]
        for r in successful:
            for c in r.columns:
                if c not in all_cols:
                    all_cols.append(c)

        explanation = (
            f"Retrieved and consolidated results across **{len(successful)} databases**:\n\n"
        )
        for r in successful:
            explanation += f"- **{r.source_name}** ({r.connector_type}): {r.rows_returned} rows\n"

        combined = {
            "columns": all_cols,
            "rows": combined_rows[:200],  # bounded
            "rows_returned": len(combined_rows[:200]),
        }
        return combined, explanation, strategy

    @classmethod
    def _try_common_key_join(
        cls, results: List[SourceQueryResult]
    ) -> Optional[Tuple[List[Dict[str, Any]], List[str], str]]:
        """Attempt to join on common key like id, customer_id, user_id, email, date."""
        if len(results) != 2:
            return None

        r1, r2 = results[0], results[1]
        keys1 = set(r1.columns)
        keys2 = set(r2.columns)
        common = keys1.intersection(keys2)

        # Prioritize ID-like columns
        preferred_keys = ["id", "customer_id", "user_id", "email", "order_id", "date"]
        join_key = None
        for pk in preferred_keys:
            if pk in common:
                join_key = pk
                break

        if not join_key and common:
            # Pick first common column that is not generic name
            for c in common:
                if "id" in c.lower() or "code" in c.lower():
                    join_key = c
                    break

        if not join_key:
            return None

        # Build index for r2
        idx2: Dict[str, Dict[str, Any]] = {}
        for row in r2.rows:
            k = str(row.get(join_key))
            if k and k != "None":
                idx2[k] = row

        merged: List[Dict[str, Any]] = []
        prefix1 = r1.connector_type
        prefix2 = r2.connector_type

        combined_columns = [join_key]

        for row1 in r1.rows:
            k = str(row1.get(join_key))
            if k in idx2:
                row2 = idx2[k]
                merged_row: Dict[str, Any] = {join_key: row1.get(join_key)}

                for c, v in row1.items():
                    if c == join_key:
                        continue
                    col_name = f"{prefix1}_{c}" if c in keys2 else c
                    merged_row[col_name] = v
                    if col_name not in combined_columns:
                        combined_columns.append(col_name)

                for c, v in row2.items():
                    if c == join_key:
                        continue
                    col_name = f"{prefix2}_{c}" if c in keys1 else c
                    merged_row[col_name] = v
                    if col_name not in combined_columns:
                        combined_columns.append(col_name)

                merged.append(merged_row)

        if not merged:
            return None

        return merged, combined_columns, join_key

    @classmethod
    def _try_metric_comparison(
        cls, results: List[SourceQueryResult]
    ) -> Optional[Tuple[List[Dict[str, Any]], List[str]]]:
        """Format aggregate scalar comparison table."""
        # Check if each result has exactly 1 row with aggregate counts
        if all(r.rows_returned == 1 for r in results):
            comp_rows: List[Dict[str, Any]] = []
            for r in results:
                row = r.rows[0]
                for k, v in row.items():
                    comp_rows.append({
                        "database_source": r.source_name,
                        "engine": r.connector_type,
                        "metric_name": k,
                        "metric_value": v,
                    })

            cols = ["database_source", "engine", "metric_name", "metric_value"]
            return comp_rows, cols

        return None

