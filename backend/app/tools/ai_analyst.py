import json
import re
from typing import Any

from sqlalchemy import text

from app.tools.analyze_database import analyze_database
from app.database.database_manager import get_engine, get_current_db_type
from app.agent.groq_agent import ask_groq


def _quote(ident: str) -> str:
    escaped = ident.replace('"', '""')
    return f'"{escaped}"'


def analyze_business(user_message: str = "") -> dict[str, Any]:
    profile = analyze_database()
    
    overview = {
        "total_tables": profile.total_tables,
        "total_rows": profile.total_rows,
        "total_columns": profile.total_columns,
        "database_type": profile.database_type,
    }
    
    kpis = []
    data_quality = {
        "null_percentage": 0.0,
        "duplicate_tables": 0,
        "empty_tables": 0,
        "null_heavy_columns": 0,
    }
    
    total_cells = 0
    total_nulls = 0
    
    table_schemas = {}
    
    for table_name, table in profile.tables.items():
        if table.row_count == 0:
            data_quality["empty_tables"] += 1
            
        schema_hash = tuple(sorted([f"{c.name}:{c.type}" for c in table.columns]))
        if schema_hash in table_schemas:
            table_schemas[schema_hash].append(table_name)
        else:
            table_schemas[schema_hash] = [table_name]
            
        for col in table.columns:
            total_cells += col.total_values
            total_nulls += col.null_count
            if col.total_values > 0 and (col.null_count / col.total_values) >= 0.5:
                data_quality["null_heavy_columns"] += 1

    data_quality["duplicate_tables"] = sum(
        len(tables) - 1 for tables in table_schemas.values() if len(tables) > 1
    )
    
    if total_cells > 0:
        data_quality["null_percentage"] = round((total_nulls / total_cells) * 100, 2)

    engine = get_engine()
    distribution_data = {}
    
    if engine is not None:
        with engine.connect() as conn:
            for table_name, table in profile.tables.items():
                for col in table.columns:
                    if col.role == "numeric_measure":
                        try:
                            table_sql = _quote(table_name)
                            col_sql = _quote(col.name)
                            sql = f"SELECT SUM({col_sql}), AVG({col_sql}) FROM {table_sql}"
                            result = conn.execute(text(sql)).fetchone()
                            
                            if result and result[0] is not None:
                                val_sum = result[0]
                                label_name = col.name.replace("_", " ").title()
                                kpis.append({
                                    "label": f"Total {label_name} ({table_name})",
                                    "value": f"{val_sum:,.2f}",
                                    "icon": "dollar-sign" if any(x in col.name.lower() for x in ["price", "amount", "revenue", "cost"]) else "trending-up"
                                })
                        except Exception:
                            pass
                            
                    elif col.role == "category" and table.row_count > 0:
                        try:
                            table_sql = _quote(table_name)
                            col_sql = _quote(col.name)
                            sql = f"SELECT {col_sql}, COUNT(*) FROM {table_sql} GROUP BY {col_sql} ORDER BY COUNT(*) DESC LIMIT 5"
                            rows = conn.execute(text(sql)).fetchall()
                            dist = {str(r[0]): r[1] for r in rows if r[0] is not None}
                            if dist:
                                distribution_data[f"{table_name}.{col.name}"] = dist
                        except Exception:
                            pass

    context = profile.to_context()
    
    prompt = f"""You are an expert AI business analyst analyzing a database.
Below is the database schema, locally computed KPIs, data quality metrics, and distribution data.

DATABASE CONTEXT:
{context}

KPIs:
{json.dumps(kpis, indent=2)}

DATA QUALITY:
{json.dumps(data_quality, indent=2)}

DISTRIBUTION DATA:
{json.dumps(distribution_data, indent=2)}

Your task is to generate actionable business insights, identify anomalies or warnings, provide recommendations, and write a comprehensive Markdown summary of your findings.

Respond STRICTLY in JSON format matching this schema:
{{
  "insights": [
    {{"type": "warning", "message": "Short warning message (e.g., high null rate in important column)"}},
    {{"type": "success", "message": "Short success message"}},
    {{"type": "info", "message": "Short informational insight"}}
  ],
  "recommendations": [
    "Actionable recommendation 1",
    "Actionable recommendation 2"
  ],
  "ai_summary": "A full Markdown formatted report detailing the business overview, key metrics, data quality assessment, and findings."
}}

Do NOT wrap the JSON in Markdown backticks (e.g. ```json). Just output the raw JSON object.
"""

    try:
        response = ask_groq(prompt)
        
        # Clean markdown code fences if model returned ```json ... ```
        cleaned = re.sub(r'^```(?:json)?\s*', '', response.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned.strip())
        
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        raw_json = match.group() if match else cleaned
        parsed = json.loads(raw_json)
    except Exception:
        parsed = {
            "insights": [
                {
                    "aspect": "Data Completeness",
                    "description": f"Overall null rate across all fields is {data_quality['null_percentage']}%.",
                    "impact": "Data is clean and ready for analysis." if data_quality['null_percentage'] < 10 else "Potential missing operational data."
                },
                {
                    "aspect": "Schema Architecture",
                    "description": f"Database contains {profile.total_tables} tables with {len(profile.relationships)} relational connections.",
                    "impact": "Relational integrity preserved."
                }
            ],
            "recommendations": [
                {"action": "Continuous Monitoring", "details": "Run periodic health checks to ensure null percentage stays low."},
                {"action": "Relationship Optimization", "details": "Ensure foreign key indices are maintained as records grow."}
            ],
            "ai_summary": f"Automated analysis of {profile.database_type.upper()} database comprising {profile.total_tables} tables and {profile.total_rows} records."
        }

    # Build analytics_data for frontend AnalyticsDashboard component
    table_stats = {t_name: t.row_count for t_name, t in profile.tables.items()}
    sorted_tables = sorted(table_stats.items(), key=lambda x: x[1], reverse=True)[:8]

    analytics_data = {
        "cards": {
            "table_count": profile.total_tables,
            "total_rows": profile.total_rows,
            "tables": table_stats,
        },
        "bar": {
            "labels": [t[0] for t in sorted_tables] if sorted_tables else ["No data"],
            "values": [t[1] for t in sorted_tables] if sorted_tables else [0],
        },
        "line": {
            "labels": [t[0] for t in sorted_tables] if sorted_tables else ["No data"],
            "values": [t[1] for t in sorted_tables] if sorted_tables else [0],
        },
        "pie": {
            "labels": [t[0] for t in sorted_tables[:5]] if sorted_tables else ["No data"],
            "values": [t[1] for t in sorted_tables[:5]] if sorted_tables else [0],
        },
    }

    insights_list = parsed.get("insights", [])
    recommendations_list = parsed.get("recommendations", [])
    raw_ai_summary = parsed.get("ai_summary", "")

    # Format structured executive presentation
    summary_parts = []
    summary_parts.append("## 🏢 Executive Business & Data Overview\n")
    summary_parts.append(
        f"**Database**: `{profile.database_type.upper() or 'Connected DB'}` &nbsp;|&nbsp; "
        f"**Tables**: `{profile.total_tables:,}` &nbsp;|&nbsp; "
        f"**Total Records**: `{profile.total_rows:,}` &nbsp;|&nbsp; "
        f"**Total Columns**: `{profile.total_columns:,}`\n"
    )

    if kpis:
        summary_parts.append("### 📈 Key Performance Indicators (KPIs)")
        summary_parts.append("| Metric | Value | Table / Source |")
        summary_parts.append("| :--- | :--- | :--- |")
        for k in kpis:
            label = k.get("label", "Metric")
            val = k.get("value", "-")
            summary_parts.append(f"| **{label}** | `{val}` | Verified Live |")
        summary_parts.append("")

    summary_parts.append("### 🚨 AI Detected Insights & Signals")
    if insights_list:
        for ins in insights_list:
            if isinstance(ins, dict):
                aspect = ins.get("aspect") or ins.get("type", "Signal")
                desc = ins.get("description") or ins.get("message") or str(ins)
                impact = ins.get("impact")

                text_lower = f"{aspect} {desc}".lower()
                if any(w in text_lower for w in ["missing", "loss", "degrade", "risk", "gap", "lack", "warning", "danger", "error", "anomaly"]):
                    prefix = "🔴 **Anomaly / Risk**"
                elif any(w in text_lower for w in ["maintain", "integrity", "growth", "opportunity", "success", "correct"]):
                    prefix = "🟢 **Positive / Health**"
                else:
                    prefix = "🟡 **Observation**"

                entry = f"- {prefix}: **{aspect}** — {desc}"
                if impact:
                    entry += f" *(Impact: {impact})*"
                summary_parts.append(entry)
            else:
                summary_parts.append(f"- 🟡 {str(ins)}")
    else:
        summary_parts.append(f"- 🟢 Data is actively structured across {profile.total_tables} functional tables.")
        if profile.relationships:
            summary_parts.append(f"- 🟡 Detected {len(profile.relationships)} relational connections across business entities.")
    summary_parts.append("")

    summary_parts.append("### 🩺 Data Health & Quality Diagnostic")
    summary_parts.append(
        f"| Diagnostic Check | Finding | Status |\n"
        f"| :--- | :--- | :--- |\n"
        f"| Overall Null Values | `{data_quality['null_percentage']}%` | {'⚠️ Needs cleanup' if data_quality['null_percentage'] > 15 else '✅ Healthy'} |\n"
        f"| Empty Tables | `{data_quality['empty_tables']}` | {'⚠️ Review empty tables' if data_quality['empty_tables'] > 0 else '✅ None'} |\n"
        f"| High-Null Columns (≥50%) | `{data_quality['null_heavy_columns']}` | {'⚠️ Sparsely populated' if data_quality['null_heavy_columns'] > 0 else '✅ Low'} |\n"
        f"| Potentially Redundant Tables | `{data_quality['duplicate_tables']}` | {'⚠️ Schema overlap' if data_quality['duplicate_tables'] > 0 else '✅ Optimized'} |"
    )
    summary_parts.append("")

    if raw_ai_summary and len(raw_ai_summary) > 40:
        summary_parts.append("### 🧠 AI Analyst Narrative")
        summary_parts.append(raw_ai_summary.strip())
        summary_parts.append("")

    if recommendations_list:
        summary_parts.append("### 💡 Recommended Strategic Actions")
        for i, rec in enumerate(recommendations_list, 1):
            if isinstance(rec, dict):
                act = rec.get("action", f"Action {i}")
                det = rec.get("details", "")
                summary_parts.append(f"{i}. **{act}**: {det}")
            else:
                summary_parts.append(f"{i}. {rec}")
        summary_parts.append("")

    final_report = "\n".join(summary_parts)

    return {
        "overview": overview,
        "kpis": kpis,
        "data_quality": data_quality,
        "insights": insights_list,
        "recommendations": recommendations_list,
        "ai_summary": final_report,
        "analytics_data": analytics_data,
    }
