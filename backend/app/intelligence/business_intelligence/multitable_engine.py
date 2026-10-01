"""
backend/app/intelligence/business_intelligence/multitable_engine.py

Phase 8.2: Multi-Table Business Intelligence Engine
Implements:
- Multi-table metric discovery & calculation
- Cross-table business insight generation
- Deterministic cross-table SQL construction with verified FK join paths
- Lineage tracking and structured evidence
- Safe causality explanation with Groq polish and deterministic fallback
"""
from __future__ import annotations

import re
import logging
from typing import Any, Optional
from datetime import datetime
from sqlalchemy import text

from app.intelligence.schema_analyzer import quote_identifier, analyze_schema
from app.intelligence.ai_analyst.trend_analyzer import get_dialect_date_trunc
from app.tools.execute_query import validate_sql
from app.agent.groq_agent import ask_groq
from app.intelligence.business_intelligence.models import (
    BusinessInsight,
    BusinessContext,
    DiscoveredMetric,
    InsightCategory,
    InsightSeverity,
)
from app.intelligence.business_intelligence.join_path import (
    JoinPath,
    build_relationship_graph,
    find_join_path,
    find_all_join_paths,
    format_join_sql,
)

logger = logging.getLogger("bgai.bi.multitable")


def discover_multitable_metrics(
    engine: Any,
    db_type: str,
    context: BusinessContext,
) -> list[DiscoveredMetric]:
    """
    Deterministically discovers multi-table aggregate and volume metrics
    using verified foreign key relationships.
    """
    if engine is None or not context.has_sufficient_data:
        return []

    metrics: list[DiscoveredMetric] = []
    schema_info = analyze_schema(engine, db_type)
    tables_data = schema_info.get("tables", {})
    graph = build_relationship_graph(schema_info)

    with engine.connect() as conn:
        # Pattern 1: Revenue by Customer (orders + customers)
        path = find_join_path(graph, "orders", "customers", max_depth=2, db_type=db_type)
        if path and "orders" in tables_data and "customers" in tables_data:
            c_cols = [c["name"] for c in tables_data["customers"].get("columns", [])]
            o_cols = [c["name"] for c in tables_data["orders"].get("columns", [])]
            
            cust_name_col = next((c for c in c_cols if c.lower() in ("name", "customer_name", "username", "full_name")), None)
            order_amt_col = next((c for c in o_cols if c.lower() in ("total_amount", "amount", "total", "price", "revenue")), None)

            if cust_name_col and order_amt_col:
                o_sql = quote_identifier("orders", db_type)
                c_sql = quote_identifier("customers", db_type)
                name_col_sql = f"{c_sql}.{quote_identifier(cust_name_col, db_type)}"
                amt_col_sql = f"{o_sql}.{quote_identifier(order_amt_col, db_type)}"
                join_clause = format_join_sql("orders", [path], db_type)

                sql = f"""
                    SELECT {name_col_sql} AS customer_name, SUM({amt_col_sql}) AS total_revenue
                    FROM {o_sql}
                    {join_clause}
                    WHERE {amt_col_sql} IS NOT NULL
                    GROUP BY {name_col_sql}
                    ORDER BY total_revenue DESC
                    LIMIT 10
                """
                try:
                    rows = conn.execute(text(sql)).fetchall()
                    if rows:
                        top_cust, top_rev = rows[0][0], float(rows[0][1] or 0.0)
                        metrics.append(
                            DiscoveredMetric(
                                name="Revenue by Customer",
                                source_table="orders",
                                source_tables=["orders", "customers"],
                                source_columns=[order_amt_col, cust_name_col],
                                sql=" ".join(sql.split()),
                                current_value=top_rev,
                                calculation_method=f"SUM(orders.{order_amt_col}) GROUP BY customers.{cust_name_col}",
                                confidence=1.0,
                                join_path=path.to_dict(),
                                aggregation="SUM",
                                grouping=[cust_name_col],
                                evidence={
                                    "top_customer": str(top_cust),
                                    "top_revenue": top_rev,
                                    "customers_observed": len(rows),
                                    "lineage": path.lineage,
                                },
                            )
                        )
                except Exception as e:
                    logger.debug("Multi-table metric failed: %s", str(e))

        # Pattern 2: Orders by Customer (orders + customers count)
        if path and "orders" in tables_data and "customers" in tables_data:
            c_cols = [c["name"] for c in tables_data["customers"].get("columns", [])]
            cust_name_col = next((c for c in c_cols if c.lower() in ("name", "customer_name", "username")), None)
            if cust_name_col:
                o_sql = quote_identifier("orders", db_type)
                c_sql = quote_identifier("customers", db_type)
                name_col_sql = f"{c_sql}.{quote_identifier(cust_name_col, db_type)}"
                join_clause = format_join_sql("orders", [path], db_type)

                sql = f"""
                    SELECT {name_col_sql} AS customer_name, COUNT(*) AS order_count
                    FROM {o_sql}
                    {join_clause}
                    GROUP BY {name_col_sql}
                    ORDER BY order_count DESC
                    LIMIT 10
                """
                try:
                    rows = conn.execute(text(sql)).fetchall()
                    if rows:
                        top_cust, top_cnt = rows[0][0], float(rows[0][1] or 0.0)
                        metrics.append(
                            DiscoveredMetric(
                                name="Orders by Customer",
                                source_table="orders",
                                source_tables=["orders", "customers"],
                                source_columns=[cust_name_col],
                                sql=" ".join(sql.split()),
                                current_value=top_cnt,
                                calculation_method=f"COUNT(orders.id) GROUP BY customers.{cust_name_col}",
                                confidence=1.0,
                                join_path=path.to_dict(),
                                aggregation="COUNT",
                                grouping=[cust_name_col],
                                evidence={
                                    "top_customer": str(top_cust),
                                    "order_count": top_cnt,
                                    "customers_observed": len(rows),
                                    "lineage": path.lineage,
                                },
                            )
                        )
                except Exception as e:
                    logger.debug("Orders by customer metric failed: %s", str(e))

        # Pattern 3: Revenue by Product (order_items + products)
        path_p = find_join_path(graph, "order_items", "products", max_depth=2, db_type=db_type)
        if path_p and "order_items" in tables_data and "products" in tables_data:
            oi_cols = [c["name"] for c in tables_data["order_items"].get("columns", [])]
            p_cols = [c["name"] for c in tables_data["products"].get("columns", [])]

            qty_col = next((c for c in oi_cols if c.lower() in ("quantity", "qty")), None)
            price_col = next((c for c in p_cols if c.lower() in ("price", "unit_price", "cost", "amount")), None)
            p_name_col = next((c for c in p_cols if c.lower() in ("name", "title", "product_name")), None)

            if qty_col and price_col and p_name_col:
                oi_sql = quote_identifier("order_items", db_type)
                p_sql = quote_identifier("products", db_type)
                qty_sql = f"{oi_sql}.{quote_identifier(qty_col, db_type)}"
                price_sql = f"{p_sql}.{quote_identifier(price_col, db_type)}"
                pname_sql = f"{p_sql}.{quote_identifier(p_name_col, db_type)}"
                join_clause = format_join_sql("order_items", [path_p], db_type)

                sql = f"""
                    SELECT {pname_sql} AS product_name, SUM({qty_sql} * {price_sql}) AS product_revenue
                    FROM {oi_sql}
                    {join_clause}
                    WHERE {qty_sql} IS NOT NULL AND {price_sql} IS NOT NULL
                    GROUP BY {pname_sql}
                    ORDER BY product_revenue DESC
                    LIMIT 10
                """
                try:
                    rows = conn.execute(text(sql)).fetchall()
                    if rows:
                        top_prod, top_rev = rows[0][0], float(rows[0][1] or 0.0)
                        metrics.append(
                            DiscoveredMetric(
                                name="Revenue by Product",
                                source_table="order_items",
                                source_tables=["order_items", "products"],
                                source_columns=[qty_col, price_col, p_name_col],
                                sql=" ".join(sql.split()),
                                current_value=top_rev,
                                calculation_method=f"SUM(order_items.{qty_col} * products.{price_col}) GROUP BY products.{p_name_col}",
                                confidence=1.0,
                                join_path=path_p.to_dict(),
                                aggregation="SUM",
                                grouping=[p_name_col],
                                evidence={
                                    "top_product": str(top_prod),
                                    "top_revenue": top_rev,
                                    "products_observed": len(rows),
                                    "lineage": path_p.lineage,
                                },
                            )
                        )
                except Exception as e:
                    logger.debug("Revenue by product metric failed: %s", str(e))

        # Pattern 4: Units Sold by Product (order_items + products)
        if path_p and "order_items" in tables_data and "products" in tables_data:
            oi_cols = [c["name"] for c in tables_data["order_items"].get("columns", [])]
            p_cols = [c["name"] for c in tables_data["products"].get("columns", [])]
            qty_col = next((c for c in oi_cols if c.lower() in ("quantity", "qty")), None)
            p_name_col = next((c for c in p_cols if c.lower() in ("name", "title", "product_name")), None)

            if qty_col and p_name_col:
                oi_sql = quote_identifier("order_items", db_type)
                p_sql = quote_identifier("products", db_type)
                qty_sql = f"{oi_sql}.{quote_identifier(qty_col, db_type)}"
                pname_sql = f"{p_sql}.{quote_identifier(p_name_col, db_type)}"
                join_clause = format_join_sql("order_items", [path_p], db_type)

                sql = f"""
                    SELECT {pname_sql} AS product_name, SUM({qty_sql}) AS units_sold
                    FROM {oi_sql}
                    {join_clause}
                    WHERE {qty_sql} IS NOT NULL
                    GROUP BY {pname_sql}
                    ORDER BY units_sold DESC
                    LIMIT 10
                """
                try:
                    rows = conn.execute(text(sql)).fetchall()
                    if rows:
                        top_prod, top_units = rows[0][0], float(rows[0][1] or 0.0)
                        metrics.append(
                            DiscoveredMetric(
                                name="Units Sold by Product",
                                source_table="order_items",
                                source_tables=["order_items", "products"],
                                source_columns=[qty_col, p_name_col],
                                sql=" ".join(sql.split()),
                                current_value=top_units,
                                calculation_method=f"SUM(order_items.{qty_col}) GROUP BY products.{p_name_col}",
                                confidence=1.0,
                                join_path=path_p.to_dict(),
                                aggregation="SUM",
                                grouping=[p_name_col],
                                evidence={
                                    "top_product": str(top_prod),
                                    "units_sold": top_units,
                                    "products_observed": len(rows),
                                    "lineage": path_p.lineage,
                                },
                            )
                        )
                except Exception as e:
                    logger.debug("Units sold metric failed: %s", str(e))

        # Pattern 5: Revenue by Category (order_items + products + categories OR products.category)
        path_cat = find_join_path(graph, "order_items", "categories", max_depth=3, db_type=db_type)
        if path_cat and "order_items" in tables_data and "products" in tables_data and "categories" in tables_data:
            oi_cols = [c["name"] for c in tables_data["order_items"].get("columns", [])]
            p_cols = [c["name"] for c in tables_data["products"].get("columns", [])]
            cat_cols = [c["name"] for c in tables_data["categories"].get("columns", [])]

            qty_col = next((c for c in oi_cols if c.lower() in ("quantity", "qty")), None)
            price_col = next((c for c in p_cols if c.lower() in ("price", "unit_price", "cost", "amount")), None)
            cat_name_col = next((c for c in cat_cols if c.lower() in ("name", "category_name", "title")), None)

            if qty_col and price_col and cat_name_col:
                oi_sql = quote_identifier("order_items", db_type)
                p_sql = quote_identifier("products", db_type)
                c_sql = quote_identifier("categories", db_type)
                qty_sql = f"{oi_sql}.{quote_identifier(qty_col, db_type)}"
                price_sql = f"{p_sql}.{quote_identifier(price_col, db_type)}"
                cat_sql = f"{c_sql}.{quote_identifier(cat_name_col, db_type)}"
                join_clause = format_join_sql("order_items", [path_cat], db_type)

                sql = f"""
                    SELECT {cat_sql} AS category_name, SUM({qty_sql} * {price_sql}) AS category_revenue
                    FROM {oi_sql}
                    {join_clause}
                    WHERE {qty_sql} IS NOT NULL AND {price_sql} IS NOT NULL
                    GROUP BY {cat_sql}
                    ORDER BY category_revenue DESC
                    LIMIT 10
                """
                try:
                    rows = conn.execute(text(sql)).fetchall()
                    if rows:
                        top_cat, top_rev = rows[0][0], float(rows[0][1] or 0.0)
                        metrics.append(
                            DiscoveredMetric(
                                name="Revenue by Category",
                                source_table="order_items",
                                source_tables=["order_items", "products", "categories"],
                                source_columns=[qty_col, price_col, cat_name_col],
                                sql=" ".join(sql.split()),
                                current_value=top_rev,
                                calculation_method=f"SUM(order_items.{qty_col} * products.{price_col}) GROUP BY categories.{cat_name_col}",
                                confidence=1.0,
                                join_path=path_cat.to_dict(),
                                aggregation="SUM",
                                grouping=[cat_name_col],
                                evidence={
                                    "top_category": str(top_cat),
                                    "top_revenue": top_rev,
                                    "categories_observed": len(rows),
                                    "lineage": path_cat.lineage,
                                },
                            )
                        )
                except Exception as e:
                    logger.debug("Revenue by category metric failed: %s", str(e))
        elif "order_items" in tables_data and "products" in tables_data:
            # Check if products table has category column directly
            p_cols = [c["name"] for c in tables_data["products"].get("columns", [])]
            cat_col = next((c for c in p_cols if c.lower() in ("category", "category_name", "department")), None)
            path_p = find_join_path(graph, "order_items", "products", max_depth=2, db_type=db_type)
            if cat_col and path_p:
                oi_cols = [c["name"] for c in tables_data["order_items"].get("columns", [])]
                qty_col = next((c for c in oi_cols if c.lower() in ("quantity", "qty")), None)
                price_col = next((c for c in p_cols if c.lower() in ("price", "unit_price", "cost", "amount")), None)

                if qty_col and price_col:
                    oi_sql = quote_identifier("order_items", db_type)
                    p_sql = quote_identifier("products", db_type)
                    qty_sql = f"{oi_sql}.{quote_identifier(qty_col, db_type)}"
                    price_sql = f"{p_sql}.{quote_identifier(price_col, db_type)}"
                    cat_sql = f"{p_sql}.{quote_identifier(cat_col, db_type)}"
                    join_clause = format_join_sql("order_items", [path_p], db_type)

                    sql = f"""
                        SELECT {cat_sql} AS category_name, SUM({qty_sql} * {price_sql}) AS category_revenue
                        FROM {oi_sql}
                        {join_clause}
                        WHERE {qty_sql} IS NOT NULL AND {price_sql} IS NOT NULL
                        GROUP BY {cat_sql}
                        ORDER BY category_revenue DESC
                        LIMIT 10
                    """
                    try:
                        rows = conn.execute(text(sql)).fetchall()
                        if rows:
                            top_cat, top_rev = rows[0][0], float(rows[0][1] or 0.0)
                            metrics.append(
                                DiscoveredMetric(
                                    name="Revenue by Category",
                                    source_table="order_items",
                                    source_tables=["order_items", "products"],
                                    source_columns=[qty_col, price_col, cat_col],
                                    sql=" ".join(sql.split()),
                                    current_value=top_rev,
                                    calculation_method=f"SUM(order_items.{qty_col} * products.{price_col}) GROUP BY products.{cat_col}",
                                    confidence=1.0,
                                    join_path=path_p.to_dict(),
                                    aggregation="SUM",
                                    grouping=[cat_col],
                                    evidence={
                                        "top_category": str(top_cat),
                                        "top_revenue": top_rev,
                                        "categories_observed": len(rows),
                                        "lineage": path_p.lineage,
                                    },
                                )
                            )
                    except Exception as e:
                        logger.debug("Revenue by product category metric failed: %s", str(e))

        # Pattern 6: Regional Performance (orders + customers.region)
        if path and "orders" in tables_data and "customers" in tables_data:
            c_cols = [c["name"] for c in tables_data["customers"].get("columns", [])]
            o_cols = [c["name"] for c in tables_data["orders"].get("columns", [])]
            region_col = next((c for c in c_cols if c.lower() in ("region", "city", "state", "country", "territory")), None)
            order_amt_col = next((c for c in o_cols if c.lower() in ("total_amount", "amount", "total", "price", "revenue")), None)

            if region_col and order_amt_col:
                o_sql = quote_identifier("orders", db_type)
                c_sql = quote_identifier("customers", db_type)
                reg_col_sql = f"{c_sql}.{quote_identifier(region_col, db_type)}"
                amt_col_sql = f"{o_sql}.{quote_identifier(order_amt_col, db_type)}"
                join_clause = format_join_sql("orders", [path], db_type)

                sql = f"""
                    SELECT {reg_col_sql} AS region_name, SUM({amt_col_sql}) AS regional_revenue
                    FROM {o_sql}
                    {join_clause}
                    WHERE {amt_col_sql} IS NOT NULL AND {reg_col_sql} IS NOT NULL
                    GROUP BY {reg_col_sql}
                    ORDER BY regional_revenue DESC
                    LIMIT 10
                """
                try:
                    rows = conn.execute(text(sql)).fetchall()
                    if rows:
                        top_reg, top_rev = rows[0][0], float(rows[0][1] or 0.0)
                        metrics.append(
                            DiscoveredMetric(
                                name="Revenue by Region",
                                source_table="orders",
                                source_tables=["orders", "customers"],
                                source_columns=[order_amt_col, region_col],
                                sql=" ".join(sql.split()),
                                current_value=top_rev,
                                calculation_method=f"SUM(orders.{order_amt_col}) GROUP BY customers.{region_col}",
                                confidence=1.0,
                                join_path=path.to_dict(),
                                aggregation="SUM",
                                grouping=[region_col],
                                evidence={
                                    "top_region": str(top_reg),
                                    "top_revenue": top_rev,
                                    "regions_observed": len(rows),
                                    "lineage": path.lineage,
                                },
                            )
                        )
                except Exception as e:
                    logger.debug("Regional revenue metric failed: %s", str(e))

    return metrics


def generate_multitable_insights(
    engine: Any,
    db_type: str,
    context: BusinessContext,
) -> list[BusinessInsight]:
    """
    Constructs high-priority cross-table BusinessInsight cards
    from discovered multi-table metrics and join relationships.
    Enforces causality-safe explanations ("was concentrated in", "was associated with").
    """
    if engine is None or not context.has_sufficient_data:
        return []

    insights: list[BusinessInsight] = []
    mt_metrics = discover_multitable_metrics(engine, db_type, context)

    for m in mt_metrics:
        ev = m.evidence
        if m.name == "Revenue by Product" and "top_product" in ev:
            prod_name = ev["top_product"]
            rev = ev["top_revenue"]
            summary = (
                f"Product revenue was concentrated in '{prod_name}', "
                f"accounting for {rev:,.2f} in total sales across observed orders."
            )
            insights.append(
                BusinessInsight(
                    title=f"Top Product Contribution: {prod_name}",
                    summary=summary,
                    category=InsightCategory.TOP_CONTRIBUTOR,
                    severity=InsightSeverity.INFO,
                    priority=88.0,
                    metric=f"Revenue ({prod_name})",
                    current_value=rev,
                    source_tables=m.source_tables,
                    source_columns=m.source_columns,
                    sql=m.sql,
                    evidence=ev,
                    investigation_type="ai_analyst",
                    recommended_next_step=f"Explore pricing and inventory allocation for '{prod_name}'.",
                )
            )

        elif m.name == "Revenue by Category" and "top_category" in ev:
            cat_name = ev["top_category"]
            rev = ev["top_revenue"]
            summary = (
                f"Sales volume was strongest in the '{cat_name}' category, "
                f"generating {rev:,.2f} in total revenue."
            )
            insights.append(
                BusinessInsight(
                    title=f"Category Concentration: {cat_name}",
                    summary=summary,
                    category=InsightCategory.CONCENTRATION,
                    severity=InsightSeverity.INFO,
                    priority=86.0,
                    metric=f"Revenue ({cat_name})",
                    current_value=rev,
                    source_tables=m.source_tables,
                    source_columns=m.source_columns,
                    sql=m.sql,
                    evidence=ev,
                    investigation_type="ai_analyst",
                    recommended_next_step=f"Benchmark margin performance for '{cat_name}' across related product lines.",
                )
            )

        elif m.name == "Revenue by Customer" and "top_customer" in ev:
            cust_name = ev["top_customer"]
            rev = ev["top_revenue"]
            summary = (
                f"Customer order value was concentrated in account '{cust_name}', "
                f"contributing {rev:,.2f} in total purchasing volume."
            )
            insights.append(
                BusinessInsight(
                    title=f"Key Customer Account: {cust_name}",
                    summary=summary,
                    category=InsightCategory.TOP_CONTRIBUTOR,
                    severity=InsightSeverity.INFO,
                    priority=84.0,
                    metric=f"Customer Spend ({cust_name})",
                    current_value=rev,
                    source_tables=m.source_tables,
                    source_columns=m.source_columns,
                    sql=m.sql,
                    evidence=ev,
                    investigation_type="ai_analyst",
                    recommended_next_step=f"Evaluate retention and repeat order cadence for '{cust_name}'.",
                )
            )

        elif m.name == "Revenue by Region" and "top_region" in ev:
            reg_name = ev["top_region"]
            rev = ev["top_revenue"]
            summary = (
                f"Regional sales were highest in '{reg_name}', "
                f"delivering {rev:,.2f} in cumulative customer transactions."
            )
            insights.append(
                BusinessInsight(
                    title=f"Regional Performance: {reg_name}",
                    summary=summary,
                    category=InsightCategory.GROWTH,
                    severity=InsightSeverity.INFO,
                    priority=82.0,
                    metric=f"Regional Sales ({reg_name})",
                    current_value=rev,
                    source_tables=m.source_tables,
                    source_columns=m.source_columns,
                    sql=m.sql,
                    evidence=ev,
                    investigation_type="ai_analyst",
                    recommended_next_step=f"Analyze logistics and regional market penetration in '{reg_name}'.",
                )
            )

        elif m.name == "Orders by Customer" and "top_customer" in ev:
            cust_name = ev["top_customer"]
            cnt = ev["order_count"]
            summary = (
                f"Order frequency was highest for '{cust_name}' "
                f"with {int(cnt)} verified orders recorded."
            )
            insights.append(
                BusinessInsight(
                    title=f"High Order Volume Customer: {cust_name}",
                    summary=summary,
                    category=InsightCategory.TOP_CONTRIBUTOR,
                    severity=InsightSeverity.INFO,
                    priority=80.0,
                    metric=f"Order Count ({cust_name})",
                    current_value=cnt,
                    source_tables=m.source_tables,
                    source_columns=m.source_columns,
                    sql=m.sql,
                    evidence=ev,
                    investigation_type="ai_analyst",
                    recommended_next_step="Inspect order intervals and fulfillment status in Data Explorer.",
                )
            )

        elif m.name == "Units Sold by Product" and "top_product" in ev:
            prod_name = ev["top_product"]
            units = ev["units_sold"]
            summary = (
                f"Product unit volume was led by '{prod_name}' "
                f"with {int(units)} total units sold across order items."
            )
            insights.append(
                BusinessInsight(
                    title=f"Top Unit Volume: {prod_name}",
                    summary=summary,
                    category=InsightCategory.TOP_CONTRIBUTOR,
                    severity=InsightSeverity.INFO,
                    priority=78.0,
                    metric=f"Units Sold ({prod_name})",
                    current_value=units,
                    source_tables=m.source_tables,
                    source_columns=m.source_columns,
                    sql=m.sql,
                    evidence=ev,
                    investigation_type="ai_analyst",
                    recommended_next_step=f"Verify supply inventory levels for '{prod_name}'.",
                )
            )

    return insights


def query_multitable_bi(
    question: str,
    engine: Any = None,
    db_type: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Executes a multi-table business intelligence query responding to natural language questions.
    Follows strict security and schema validation pipeline:
    1. Question parsing -> Target entities, metrics, dimensions
    2. Relationship path discovery & verification
    3. Deterministic read-only SQL generation
    4. SQL safety validation
    5. Database execution with bounded LIMIT
    6. Structured evidence & join lineage formatting
    7. Causality-safe natural language explanation (with Groq polish fallback)
    """
    from app.database.database_manager import get_engine, get_current_db_type

    if engine is None:
        engine = get_engine()
    if db_type is None:
        db_type = get_current_db_type()

    if engine is None or db_type == "none":
        return {
            "status": "error",
            "message": "No database connected.",
            "data": None,
            "lineage": [],
            "sql": None,
        }

    schema_info = analyze_schema(engine, db_type)
    tables_data = schema_info.get("tables", {})
    if not tables_data:
        return {
            "status": "error",
            "message": "No tables found in connected database.",
            "data": None,
            "lineage": [],
            "sql": None,
        }

    graph = build_relationship_graph(schema_info)
    q_lower = question.lower()

    # Detect entity tables mentioned or implied in the question
    detected_tables: list[str] = []
    for tbl in tables_data.keys():
        t_low = tbl.lower()
        # Direct word match or singular match (e.g. "product" matches "products")
        if re.search(r"\b" + re.escape(t_low) + r"\b", q_lower) or re.search(r"\b" + re.escape(t_low.rstrip("s")) + r"\b", q_lower):
            if tbl not in detected_tables:
                detected_tables.append(tbl)

    # Infer common domain relationships if implied (e.g. "sales" or "revenue" implies orders/order_items)
    if any(w in q_lower for w in ("revenue", "sales", "spend", "order", "orders")) and "orders" in tables_data and "orders" not in detected_tables:
        detected_tables.append("orders")
    if any(w in q_lower for w in ("revenue", "sold", "item", "quantity", "unit")) and "order_items" in tables_data and "order_items" not in detected_tables:
        detected_tables.append("order_items")
    if any(w in q_lower for w in ("category", "categories")) and "categories" in tables_data and "categories" not in detected_tables:
        detected_tables.append("categories")
    if any(w in q_lower for w in ("customer", "customers", "client", "region")) and "customers" in tables_data and "customers" not in detected_tables:
        detected_tables.append("customers")
    if any(w in q_lower for w in ("product", "products", "item")) and "products" in tables_data and "products" not in detected_tables:
        detected_tables.append("products")

    # If only 1 table detected, check if we need an adjacent table for the requested metric or dimension
    if len(detected_tables) == 1:
        tbl0 = detected_tables[0]
        if tbl0 == "products" and any(w in q_lower for w in ("revenue", "sold", "most revenue", "sales")):
            if "order_items" in tables_data:
                detected_tables.append("order_items")
        elif tbl0 == "categories" and any(w in q_lower for w in ("revenue", "sales", "sold")):
            if "products" in tables_data:
                detected_tables.append("products")
            if "order_items" in tables_data:
                detected_tables.append("order_items")
        elif tbl0 == "customers" and any(w in q_lower for w in ("revenue", "orders", "sales", "highest")):
            if "orders" in tables_data:
                detected_tables.append("orders")

    # If still no tables detected, fallback to most connected tables
    if not detected_tables:
        detected_tables = list(tables_data.keys())[:2]

    # Verify relationships between detected tables
    if len(detected_tables) >= 2:
        # Check if there is a valid join path
        start_table = detected_tables[0]
        target_table = detected_tables[1]
        
        path = find_join_path(graph, start_table, target_table, max_depth=3, db_type=db_type)
        if not path:
            # Try reverse
            path = find_join_path(graph, target_table, start_table, max_depth=3, db_type=db_type)
            if path:
                start_table, target_table = target_table, start_table

        if not path:
            # Step 14: No verified relationship found
            available_rels = []
            for t1 in tables_data.keys():
                for edge in graph.get(t1, []):
                    if not edge.is_reverse:
                        available_rels.append(f"{edge.source_table}.{edge.source_column} -> {edge.target_table}.{edge.target_column}")

            return {
                "status": "no_relationship",
                "message": "No verified relationship was found between these tables.",
                "tables": detected_tables,
                "available_relationships": available_rels[:5],
                "data": None,
                "lineage": [],
                "sql": None,
            }
    else:
        path = None
        start_table = detected_tables[0]

    # Build deterministic SQL based on the question intent
    sql, lineage, calculation = _build_cross_table_query(
        question=question,
        detected_tables=detected_tables,
        graph=graph,
        tables_data=tables_data,
        db_type=db_type,
    )

    if not sql:
        return {
            "status": "error",
            "message": "Unable to determine a verified query structure for this question.",
            "data": None,
            "lineage": [],
            "sql": None,
        }

    # Validate SQL safety (Step 7: read-only guarantee)
    val_res = validate_sql(sql)
    if not val_res.get("allowed", False):
        return {
            "status": "error",
            "message": f"Query blocked by safety policy: {val_res.get('reason', 'Operation not permitted')}",
            "data": None,
            "lineage": lineage,
            "sql": None,
        }

    # Execute deterministic SQL
    with engine.connect() as conn:
        try:
            cursor = conn.execute(text(sql))
            rows = cursor.fetchall()
            col_names = list(cursor.keys())
        except Exception as e:
            return {
                "status": "error",
                "message": f"Query execution failed: {str(e)}",
                "data": None,
                "lineage": lineage,
                "sql": sql,
            }

    data_rows = [dict(zip(col_names, [r[i] for i in range(len(col_names))])) for r in rows]

    # Format explanation
    key_insight = _generate_multitable_summary(question, data_rows, lineage)
    ai_explanation = _explain_with_groq_or_fallback(question, key_insight, data_rows, lineage)

    return {
        "status": "success",
        "question": question,
        "key_insight": key_insight,
        "ai_explanation": ai_explanation,
        "data": data_rows,
        "lineage": lineage,
        "sql": " ".join(sql.split()),
        "source_tables": detected_tables,
        "calculation": calculation,
        "timestamp": datetime.utcnow().isoformat(),
        "record_count": len(data_rows),
    }


def _build_cross_table_query(
    question: str,
    detected_tables: list[str],
    graph: dict[str, Any],
    tables_data: dict[str, Any],
    db_type: str,
) -> tuple[Optional[str], list[str], str]:
    """
    Constructs deterministic read-only SQL with verified JOIN clauses for cross-table analytics.
    """
    q_low = question.lower()
    lineage: list[str] = []

    # Priority 1: Average Order Value by Customer (specific metric)
    if any(w in q_low for w in ("average order value", "aov")) or (any(w in q_low for w in ("average", "avg")) and "order" in q_low):
        if "orders" in tables_data and "customers" in tables_data:
            path = find_join_path(graph, "orders", "customers", max_depth=2, db_type=db_type)
            if path:
                o_sql = quote_identifier("orders", db_type)
                c_sql = quote_identifier("customers", db_type)
                join_sql = format_join_sql("orders", [path], db_type)
                lineage = path.lineage

                c_cols = [c["name"] for c in tables_data["customers"].get("columns", [])]
                o_cols = [c["name"] for c in tables_data["orders"].get("columns", [])]
                cust_name_col = next((c for c in c_cols if c.lower() in ("name", "customer_name", "username")), "name")
                order_amt_col = next((c for c in o_cols if c.lower() in ("total_amount", "amount", "total", "revenue")), "total_amount")

                sql = f"""
                    SELECT {c_sql}.{quote_identifier(cust_name_col, db_type)} AS customer_name,
                           AVG({o_sql}.{quote_identifier(order_amt_col, db_type)}) AS average_order_value
                    FROM {o_sql}
                    {join_sql}
                    GROUP BY {c_sql}.{quote_identifier(cust_name_col, db_type)}
                    ORDER BY average_order_value DESC
                    LIMIT 10
                """
                return sql, lineage, f"AVG(orders.{order_amt_col})"

    # Priority 2: Customers with Most Orders (count vs revenue)
    if any(w in q_low for w in ("customer", "customers")) and any(w in q_low for w in ("most orders", "placed the most", "order count", "orders placed")):
        if "orders" in tables_data and "customers" in tables_data:
            path = find_join_path(graph, "orders", "customers", max_depth=2, db_type=db_type)
            if path:
                o_sql = quote_identifier("orders", db_type)
                c_sql = quote_identifier("customers", db_type)
                join_sql = format_join_sql("orders", [path], db_type)
                lineage = path.lineage

                c_cols = [c["name"] for c in tables_data["customers"].get("columns", [])]
                cust_name_col = next((c for c in c_cols if c.lower() in ("name", "customer_name", "username")), "name")

                sql = f"""
                    SELECT {c_sql}.{quote_identifier(cust_name_col, db_type)} AS customer_name,
                           COUNT(*) AS order_count
                    FROM {o_sql}
                    {join_sql}
                    GROUP BY {c_sql}.{quote_identifier(cust_name_col, db_type)}
                    ORDER BY order_count DESC
                    LIMIT 10
                """
                return sql, lineage, "COUNT(orders.id)"

    # Priority 3: Products sold the most / units sold (before revenue)
    if any(w in q_low for w in ("product", "products")) and (any(w in q_low for w in ("sold the most", "units sold", "most units", "top selling", "sold most", "quantity sold")) or ("sold" in q_low and "most" in q_low)):
        if "order_items" in tables_data and "products" in tables_data:
            path = find_join_path(graph, "order_items", "products", max_depth=2, db_type=db_type)
            if path:
                oi_sql = quote_identifier("order_items", db_type)
                p_sql = quote_identifier("products", db_type)
                join_sql = format_join_sql("order_items", [path], db_type)
                lineage = path.lineage

                oi_cols = [c["name"] for c in tables_data["order_items"].get("columns", [])]
                p_cols = [c["name"] for c in tables_data["products"].get("columns", [])]
                qty_col = next((c for c in oi_cols if c.lower() in ("quantity", "qty")), "quantity")
                name_col = next((c for c in p_cols if c.lower() in ("name", "title", "product_name")), "name")

                sql = f"""
                    SELECT {p_sql}.{quote_identifier(name_col, db_type)} AS product_name,
                           SUM({oi_sql}.{quote_identifier(qty_col, db_type)}) AS units_sold
                    FROM {oi_sql}
                    {join_sql}
                    GROUP BY {p_sql}.{quote_identifier(name_col, db_type)}
                    ORDER BY units_sold DESC
                    LIMIT 10
                """
                return sql, lineage, f"SUM(order_items.{qty_col})"

    # Priority 4: Category revenue over time / monthly (before general category revenue)
    if any(w in q_low for w in ("category", "categories")) and any(w in q_low for w in ("monthly", "over time", "time", "month", "trend")):
        if "orders" in tables_data and "order_items" in tables_data and "products" in tables_data:
            path_oi = find_join_path(graph, "orders", "order_items", max_depth=2, db_type=db_type)
            path_p = find_join_path(graph, "order_items", "products", max_depth=2, db_type=db_type)
            if path_oi and path_p:
                o_sql = quote_identifier("orders", db_type)
                oi_sql = quote_identifier("order_items", db_type)
                p_sql = quote_identifier("products", db_type)

                combined_join = format_join_sql("orders", [path_oi, path_p], db_type)
                lineage = path_oi.lineage + path_p.lineage

                o_cols = [c["name"] for c in tables_data["orders"].get("columns", [])]
                oi_cols = [c["name"] for c in tables_data["order_items"].get("columns", [])]
                p_cols = [c["name"] for c in tables_data["products"].get("columns", [])]

                d_col = next((c for c in o_cols if c.lower() in ("created_at", "order_date", "date")), "created_at")
                qty_col = next((c for c in oi_cols if c.lower() in ("quantity", "qty")), "quantity")
                price_col = next((c for c in p_cols if c.lower() in ("price", "unit_price", "cost", "amount")), "price")
                cat_col = next((c for c in p_cols if c.lower() in ("category", "category_name")), "category")

                d_sql = f"{o_sql}.{quote_identifier(d_col, db_type)}"
                date_expr = get_dialect_date_trunc(d_sql, db_type, "month")

                sql = f"""
                    SELECT {date_expr} AS period,
                           {p_sql}.{quote_identifier(cat_col, db_type)} AS category,
                           SUM({oi_sql}.{quote_identifier(qty_col, db_type)} * {p_sql}.{quote_identifier(price_col, db_type)}) AS revenue
                    FROM {o_sql}
                    {combined_join}
                    WHERE {d_sql} IS NOT NULL
                    GROUP BY period, category
                    ORDER BY period ASC, revenue DESC
                    LIMIT 24
                """
                return sql, lineage, "Monthly Category Revenue"

    # Priority 5: Revenue by Product / Top Products
    if any(w in q_low for w in ("product", "products")) and any(w in q_low for w in ("revenue", "sales", "highest", "most", "contributes most")):
        if "order_items" in tables_data and "products" in tables_data:
            path = find_join_path(graph, "order_items", "products", max_depth=2, db_type=db_type)
            if path:
                oi_sql = quote_identifier("order_items", db_type)
                p_sql = quote_identifier("products", db_type)
                join_sql = format_join_sql("order_items", [path], db_type)
                lineage = path.lineage

                oi_cols = [c["name"] for c in tables_data["order_items"].get("columns", [])]
                p_cols = [c["name"] for c in tables_data["products"].get("columns", [])]
                qty_col = next((c for c in oi_cols if c.lower() in ("quantity", "qty")), "quantity")
                price_col = next((c for c in p_cols if c.lower() in ("price", "unit_price", "cost", "amount")), "price")
                name_col = next((c for c in p_cols if c.lower() in ("name", "title", "product_name")), "name")

                limit_val = 1 if "contributes most" in q_low or "most revenue" in q_low and "top 10" not in q_low else 10

                sql = f"""
                    SELECT {p_sql}.{quote_identifier(name_col, db_type)} AS product_name,
                           SUM({oi_sql}.{quote_identifier(qty_col, db_type)} * {p_sql}.{quote_identifier(price_col, db_type)}) AS total_revenue
                    FROM {oi_sql}
                    {join_sql}
                    GROUP BY {p_sql}.{quote_identifier(name_col, db_type)}
                    ORDER BY total_revenue DESC
                    LIMIT {limit_val}
                """
                return sql, lineage, f"SUM(order_items.{qty_col} * products.{price_col})"

    # Priority 6: Category Revenue / Top Category
    if any(w in q_low for w in ("category", "categories")) and any(w in q_low for w in ("revenue", "sales", "highest", "most", "contributes most")):
        if "categories" in tables_data and "order_items" in tables_data and "products" in tables_data:
            path = find_join_path(graph, "order_items", "categories", max_depth=3, db_type=db_type)
            if path:
                oi_sql = quote_identifier("order_items", db_type)
                p_sql = quote_identifier("products", db_type)
                c_sql = quote_identifier("categories", db_type)
                join_sql = format_join_sql("order_items", [path], db_type)
                lineage = path.lineage

                oi_cols = [c["name"] for c in tables_data["order_items"].get("columns", [])]
                p_cols = [c["name"] for c in tables_data["products"].get("columns", [])]
                cat_cols = [c["name"] for c in tables_data["categories"].get("columns", [])]

                qty_col = next((c for c in oi_cols if c.lower() in ("quantity", "qty")), "quantity")
                price_col = next((c for c in p_cols if c.lower() in ("price", "unit_price", "cost", "amount")), "price")
                cat_name_col = next((c for c in cat_cols if c.lower() in ("name", "category_name")), "name")

                limit_val = 1 if "contributes most" in q_low or "highest revenue" in q_low else 10

                sql = f"""
                    SELECT {c_sql}.{quote_identifier(cat_name_col, db_type)} AS category_name,
                           SUM({oi_sql}.{quote_identifier(qty_col, db_type)} * {p_sql}.{quote_identifier(price_col, db_type)}) AS total_revenue
                    FROM {oi_sql}
                    {join_sql}
                    GROUP BY {c_sql}.{quote_identifier(cat_name_col, db_type)}
                    ORDER BY total_revenue DESC
                    LIMIT {limit_val}
                """
                return sql, lineage, f"SUM(order_items.{qty_col} * products.{price_col})"

        elif "products" in tables_data and "order_items" in tables_data:
            p_cols = [c["name"] for c in tables_data["products"].get("columns", [])]
            cat_col = next((c for c in p_cols if c.lower() in ("category", "category_name", "department")), None)
            path = find_join_path(graph, "order_items", "products", max_depth=2, db_type=db_type)
            if cat_col and path:
                oi_sql = quote_identifier("order_items", db_type)
                p_sql = quote_identifier("products", db_type)
                join_sql = format_join_sql("order_items", [path], db_type)
                lineage = path.lineage

                oi_cols = [c["name"] for c in tables_data["order_items"].get("columns", [])]
                qty_col = next((c for c in oi_cols if c.lower() in ("quantity", "qty")), "quantity")
                price_col = next((c for c in p_cols if c.lower() in ("price", "unit_price", "cost", "amount")), "price")

                limit_val = 1 if "contributes most" in q_low or "highest revenue" in q_low else 10

                sql = f"""
                    SELECT {p_sql}.{quote_identifier(cat_col, db_type)} AS category_name,
                           SUM({oi_sql}.{quote_identifier(qty_col, db_type)} * {p_sql}.{quote_identifier(price_col, db_type)}) AS total_revenue
                    FROM {oi_sql}
                    {join_sql}
                    GROUP BY {p_sql}.{quote_identifier(cat_col, db_type)}
                    ORDER BY total_revenue DESC
                    LIMIT {limit_val}
                """
                return sql, lineage, f"SUM(order_items.{qty_col} * products.{price_col})"

    # Priority 7: Customer Revenue / Top Customers
    if any(w in q_low for w in ("customer", "customers")) and any(w in q_low for w in ("revenue", "sales", "highest", "most", "spend", "value")):
        if "orders" in tables_data and "customers" in tables_data:
            path = find_join_path(graph, "orders", "customers", max_depth=2, db_type=db_type)
            if path:
                o_sql = quote_identifier("orders", db_type)
                c_sql = quote_identifier("customers", db_type)
                join_sql = format_join_sql("orders", [path], db_type)
                lineage = path.lineage

                c_cols = [c["name"] for c in tables_data["customers"].get("columns", [])]
                o_cols = [c["name"] for c in tables_data["orders"].get("columns", [])]
                cust_name_col = next((c for c in c_cols if c.lower() in ("name", "customer_name", "username")), "name")
                order_amt_col = next((c for c in o_cols if c.lower() in ("total_amount", "amount", "total", "revenue")), "total_amount")

                sql = f"""
                    SELECT {c_sql}.{quote_identifier(cust_name_col, db_type)} AS customer_name,
                           SUM({o_sql}.{quote_identifier(order_amt_col, db_type)}) AS total_revenue
                    FROM {o_sql}
                    {join_sql}
                    GROUP BY {c_sql}.{quote_identifier(cust_name_col, db_type)}
                    ORDER BY total_revenue DESC
                    LIMIT 10
                """
                return sql, lineage, f"SUM(orders.{order_amt_col})"

    # Priority 8: Regional Sales / Revenue by Region
    if any(w in q_low for w in ("region", "regional", "city", "state", "territory")):
        if "orders" in tables_data and "customers" in tables_data:
            path = find_join_path(graph, "orders", "customers", max_depth=2, db_type=db_type)
            if path:
                c_cols = [c["name"] for c in tables_data["customers"].get("columns", [])]
                o_cols = [c["name"] for c in tables_data["orders"].get("columns", [])]
                reg_col = next((c for c in c_cols if c.lower() in ("region", "city", "state", "country")), None)
                amt_col = next((c for c in o_cols if c.lower() in ("total_amount", "amount", "total", "revenue")), "total_amount")

                if reg_col:
                    o_sql = quote_identifier("orders", db_type)
                    c_sql = quote_identifier("customers", db_type)
                    join_sql = format_join_sql("orders", [path], db_type)
                    lineage = path.lineage

                    sql = f"""
                        SELECT {c_sql}.{quote_identifier(reg_col, db_type)} AS region_name,
                               SUM({o_sql}.{quote_identifier(amt_col, db_type)}) AS regional_revenue
                        FROM {o_sql}
                        {join_sql}
                        WHERE {c_sql}.{quote_identifier(reg_col, db_type)} IS NOT NULL
                        GROUP BY {c_sql}.{quote_identifier(reg_col, db_type)}
                        ORDER BY regional_revenue DESC
                        LIMIT 10
                    """
                    return sql, lineage, f"SUM(orders.{amt_col})"

    # Default fallback: shortest join path between first two tables with a basic count/group
    if len(detected_tables) >= 2:
        t1, t2 = detected_tables[0], detected_tables[1]
        path = find_join_path(graph, t1, t2, max_depth=3, db_type=db_type)
        if path:
            t1_sql = quote_identifier(t1, db_type)
            join_sql = format_join_sql(t1, [path], db_type)
            lineage = path.lineage
            sql = f"""
                SELECT COUNT(*) AS total_count
                FROM {t1_sql}
                {join_sql}
            """
            return sql, lineage, "COUNT(*)"

    return None, [], ""


def _generate_multitable_summary(
    question: str,
    data_rows: list[dict[str, Any]],
    lineage: list[str],
) -> str:
    """
    Constructs a concise, causality-safe summary of multi-table analytical results.
    Never asserts causation; uses associative, observational phrasing.
    """
    if not data_rows:
        return "No matching records found across verified relationship paths."

    first_row = data_rows[0]
    keys = list(first_row.keys())

    if len(keys) >= 2:
        dim_key, val_key = keys[0], keys[1]
        top_name = first_row[dim_key]
        top_val = first_row[val_key]
        val_str = f"{top_val:,.2f}" if isinstance(top_val, (int, float)) else str(top_val)

        return (
            f"Analysis of {len(data_rows)} entity records indicates {dim_key.replace('_', ' ')} "
            f"was concentrated in '{top_name}' with {val_key.replace('_', ' ')} of {val_str}."
        )

    return f"Retrieved {len(data_rows)} verified record(s) matching your cross-table query."


def _explain_with_groq_or_fallback(
    question: str,
    key_insight: str,
    data_rows: list[dict[str, Any]],
    lineage: list[str],
) -> str:
    """
    Produces natural language explanation using Groq if available.
    Strictly forbids Groq from altering or recalculating numbers.
    Falls back gracefully to a deterministic explanation on timeout/network failure.
    """
    prompt = (
        f"You are a business intelligence assistant. The database calculated the following verified results:\n"
        f"Question: '{question}'\n"
        f"Key Insight: '{key_insight}'\n"
        f"Join Lineage: {', '.join(lineage)}\n"
        f"Top 3 Data Rows: {data_rows[:3]}\n\n"
        f"Provide a 2-3 sentence business explanation of these findings. "
        f"Rules: Do NOT recalculate numbers. Do NOT claim causation (use 'was associated with' or 'was concentrated in'). "
        f"Mention the verified relationship lineage."
    )
    try:
        explanation = ask_groq(prompt)
        if explanation and len(explanation.strip()) > 20:
            return explanation.strip().replace("\u2192", "->").replace("\u21b3", "->")
    except Exception:
        pass

    lineage_str = f" via {', '.join(lineage)}" if lineage else ""
    return (
        f"{key_insight} These numbers were verified directly from database records{lineage_str}. "
        f"No causal relationship is asserted."
    )
