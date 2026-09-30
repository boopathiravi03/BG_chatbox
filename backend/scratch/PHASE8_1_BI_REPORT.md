# Phase 8.1 — Automated Business Intelligence Engine Report

## 1. Executive Summary
Phase 8.1 implements the foundational layer of **Automated Business Intelligence & Decision Intelligence** for BG AI. The system proactively scans any connected real database, automatically infers its business context (entity tables, temporal sequences, quantitative measures, dimensions, and relational joins), computes volume and aggregation metrics using deterministic SQL, and generates verified, evidence-backed business insights across 9 core categories without requiring the user to formulate manual prompts.

Crucially, **no business metrics or numbers are calculated by Groq or an LLM**, and no fake or hardcoded demo values are used. Every insight is supported by reproducible SQL queries and verifiable evidence objects.

---

## 2. Architecture & Directory Structure
Following the modular architecture mandate (avoiding giant monolithic orchestrators), Phase 8.1 is built under `backend/app/intelligence/business_intelligence/`:

```
backend/app/intelligence/business_intelligence/
├── __init__.py               # Package entry points & public exports
├── models.py                 # BusinessInsight, BusinessContext, DiscoveredMetric, BusinessIntelligenceReport
├── business_context.py       # Deterministic schema & entity/measure/dimension discovery
├── metric_discovery.py       # SQL volume & aggregate metric discovery layer
├── insight_engine.py         # Multi-category insight generation (9 categories)
├── insight_ranker.py         # Deterministic priority ranking & scoring engine
└── insight_explainer.py      # Causality-safe natural language explainer & Groq fallback
```

---

## 3. Business Context Discovery (`business_context.py`)
Inspects the database schema deterministically to categorize structural elements without assuming a fixed domain:
1. **Entity Tables:** Matches semantic keywords (`customer`, `order`, `product`, `transaction`, `invoice`, `payment`, etc.) or tables having non-zero rows, primary keys, and measure/dimension columns.
2. **Time Columns:** Detects chronological timestamps (`created_at`, `order_date`, `date`, `timestamp`, etc.) and dialect temporal data types (`DATETIME`, `TIMESTAMP`, `DATE`).
3. **Measure Columns:** Identifies numeric types (`INT`, `FLOAT`, `DECIMAL`, `NUMERIC`, `REAL`) with quantitative keywords (`amount`, `price`, `revenue`, `total`, `quantity`, `cost`, `salary`, `balance`), strictly excluding primary/foreign keys (`id`, `*_id`).
4. **Dimension Columns:** Categorical / text attributes (`category`, `status`, `region`, `city`, `department`, `brand`, etc.) for slice-and-dice aggregations.
5. **Relationships:** Extracts foreign key mappings from schema analysis.
6. **Sufficiency Evaluation:**
   - 0 records: `"No records available for business intelligence."`
   - < 2 records: `"Database connected, but insufficient records for automatic business insights."`
   - No measures or entities: `"Insufficient business data for automatic insight generation."`

---

## 4. Deterministic Metric Discovery (`metric_discovery.py`)
Discovers quantitative and volume measures directly via read-only SQL:
- **Volume Metrics:** `COUNT(*)` per entity table (e.g. `Total Orders`, `Total Customers`, `Total Transactions`).
- **Aggregate Metrics:** `SUM(col)` and `AVG(col)` per measure column (e.g. `Total Amount`, `Average Price`, `Average Order Value`).
- Every `DiscoveredMetric` records:
  - `name`: Human-readable label
  - `source_table`: Target table name
  - `source_columns`: Analyzed column names
  - `sql`: Deterministic read-only query
  - `current_value`: Calculated value
  - `calculation_method`: Aggregation type (`SUM`, `AVG`, `COUNT(*)`)
  - `timestamp_col`: Associated time column (if available)

---

## 5. Insight Types (9 Deterministic Categories)

| Category | Trigger & Description | Example | Default Severity |
|---|---|---|---|
| **TREND** | Chronological trajectory across >= 3 periods | *"Periodic trajectory for Orders Amount increased by 18.4%"* | `INFO` |
| **GROWTH** | Period-over-period positive expansion | *"Orders Amount increased by 24.6%"* | `INFO` |
| **DECLINE** | Period-over-period negative contraction | *"Orders Amount decreased by 37.5%"* | `CRITICAL` (>25%), `WARNING` (>5%) |
| **TOP_CONTRIBUTOR** | Dominant category accounting for >= 25% of measure | *"Electronics contributed 42.0% of Orders Amount"* | `INFO` |
| **CONCENTRATION** | Top items/categories accounting for >= 50% of measure | *"High concentration: top 3 Category represent 68.2% of Orders Amount"* | `WARNING` (>=65%), `INFO` (>=50%) |
| **QUALITY** | Missing/NULL density >= 15% in sampled rows | *"Missing data in customers.email (20.0% NULL)"* | `WARNING` (>=30%), `INFO` (>=15%) |
| **ANOMALY** | Statistical IQR outlier or unusual patterns | *"Statistical anomaly detected in orders.amount: Extreme outlier"* | `CRITICAL` or `WARNING` |
| **FORECAST** | Holt's exponential smoothing forward projection | *"Projected Orders Amount for upcoming period is approximately X"* | `INFO` |
| **PERFORMANCE** | Missing indexes on foreign keys / high-volume joins | *"Optimization opportunity: orders (unindexed foreign key)"* | `WARNING` |
| **DATA_COMPLETENESS** | Ratio of tables containing null-dense columns >= 30% | *"3 of 12 tables have noticeable NULL density"* | `WARNING` or `INFO` |

---

## 6. Deterministic Ranking Algorithm (`insight_ranker.py`)
Prioritizes insights using objective, explainable factors:
$$\text{Priority} = \text{BaseSeverity} + \text{CategoryWeight} + \text{MagnitudeAdjustment} + \text{ImpactAdjustment}$$

- **Base Severity Weights:**
  - `CRITICAL`: 100.0
  - `WARNING`: 50.0
  - `INFO`: 10.0
- **Category Weights:**
  - `DECLINE`: +25.0
  - `ANOMALY`: +20.0
  - `QUALITY`: +15.0
  - `PERFORMANCE`: +12.0
  - `CONCENTRATION`: +10.0
  - `TOP_CONTRIBUTOR`: +8.0
  - `GROWTH`: +7.0
  - `TREND`: +5.0
  - `FORECAST`: +4.0
  - `DATA_COMPLETENESS`: +3.0
- **Magnitude Adjustment:** $\min(30.0, |\Delta\%| \times 0.5)$
- **Impact Adjustment:** $\min(15.0, \log_{10}(\text{affected records} + 1) \times 3.0)$
- **Result:** Purely mathematical ranking; Groq is never used to determine which insight is more important.

---

## 7. Evidence-First Design & Causality Safety
- Every generated insight includes an immutable `evidence` dictionary containing:
  `current_period`, `current_value`, `previous_period`, `previous_value`, `change_value`, `change_percent`, `periods_observed`, `sample_size`, `sql`.
- **Causality Safety Rules:**
  - Never asserts unproven causal claims (e.g. *"sales dropped because users left"*).
  - Uses approved phrasing: *"associated with"*, *"concentrated in"*, *"observed alongside"*.
- **Groq Role:**
  - Groq is **never** permitted to calculate numbers or formulate math.
  - Can optionally polish verified evidence into natural language (top 3 insights only).
  - If Groq is unavailable, disabled, or rate-limited: seamless deterministic fallback with zero degradation.

---

## 8. API Specifications (`backend/app/main.py`)

### `GET /intelligence/insights`
- **Method:** `GET`
- **Protection:** Authenticated (`Bearer <JWT>`), user-scoped via `_activate(user)`.
- **Query Parameters:**
  - `category` (optional): Filter by category (`DECLINE`, `GROWTH`, `QUALITY`, etc.)
  - `severity` (optional): Filter by severity (`CRITICAL`, `WARNING`, `INFO`)
  - `limit` (optional): Integer limit of insights returned
- **Response Format:**
  ```json
  {
    "success": true,
    "status": "success",
    "generated_at": "2026-10-01T01:22:30.123456",
    "database_context": {
      "context_id": "ctx_...",
      "database_type": "sqlite",
      "database_identity": "sqlite:///..."
    },
    "insights": [
      {
        "id": "bi_a1b2c3d4",
        "title": "Orders Amount decreased by 37.5%",
        "summary": "Orders Amount decreased from 4,000.00 to 2,500.00 (-37.5% change) during the latest observed period.",
        "category": "DECLINE",
        "severity": "CRITICAL",
        "priority": 143.75,
        "metric": "Orders Amount",
        "current_value": 2500.0,
        "previous_value": 4000.0,
        "change_value": -1500.0,
        "change_percent": -37.5,
        "source_tables": ["orders"],
        "source_columns": ["created_at", "amount"],
        "sql": "SELECT strftime('%Y-%m', \"created_at\") AS period, SUM(\"amount\") AS val...",
        "evidence": {
          "current_period": "2024-06",
          "current_value": 2500.0,
          "previous_period": "2024-05",
          "previous_value": 4000.0,
          "change_value": -1500.0,
          "change_percent": -37.5
        },
        "investigation_type": "ai_analyst",
        "recommended_next_step": "Review recent transactions in AI Analyst..."
      }
    ],
    "summary": {
      "total": 6,
      "critical": 1,
      "warning": 2,
      "info": 3
    }
  }
  ```

### `POST /intelligence/insights/refresh`
- **Method:** `POST`
- **Protection:** Authenticated (`Bearer <JWT>`), user-scoped.
- Forces a fresh re-scan of the user's active database context and updates `user_cache`.

---

## 9. Cache Architecture & Invalidation
- Cached per user in `backend/app/security/user_cache.py` under `CACHE_INSIGHTS_REPORT = "insights_report"`.
- Cache keys are `(user_id, "insights_report")`.
- Invalidation triggers:
  1. `/connect`: `cache_clear_user(user.user_id)`
  2. `/disconnect`: `cache_clear_user(user.user_id)`
  3. `/intelligence/insights/refresh`: Recomputes and updates cache
  4. Safe action confirm (`/agent-actions/{id}/confirm`): `cache_delete(user.user_id, CACHE_INSIGHTS_REPORT)` on verified execution.
- Completely isolated: Clearing User A's cache never affects User B.

---

## 10. Frontend Overview Upgrades (`OverviewView.tsx`)
1. **Automated Business Intelligence Card Section:**
   - Pill summary: Total count, `[ Critical X ]`, `[ Warning Y ]`, `[ Info Z ]`.
   - Real-time refresh button with loading spinner.
   - Dynamic cards showing Category icons, Severity badges, Metric and Delta pills.
2. **Insight Detail Drawer / Modal:**
   - Displays full Observation Summary.
   - 4-column metric grid: Metric Name, Current Value, Previous Value, Change %.
   - Verifiable Evidence key-value panel.
   - Syntax-highlighted deterministic SQL block with a One-Click Copy button.
   - Recommended Next Step with direct workspace navigation buttons:
     - *"Investigate in Workspace"* -> Routes to AI Analyst, Data Explorer, Anomaly Center, Forecasting, or Data Health.
3. **Recommended Investigations Bar:**
   - Quick inquiry buttons:
     - `[ Why did revenue decline? ]`
     - `[ Which products drive sales? ]`
     - `[ Show customer concentration ]`
     - `[ Investigate anomalies ]`
4. **Empty / Disconnected State:**
   - When no database is connected: displays *"Connect a database to generate business intelligence."* with clean zero-state cards (no fake numbers).
   - When database has insufficient rows: displays informative banner explaining why insights are not yet available.

---

## 11. Test Verification Results

### A. Phase 8.1 Dedicated BI Test Suite (`backend/scratch/test_phase8_bi.py`)
Tested against a real disposable SQLite test database with realistic tables, relationships, and chronological records:
1. `[PASS]` Discovers entity tables, time columns, measures, and dimensions
2. `[PASS]` Discovers quantitative volume and aggregate metrics with deterministic SQL
3. `[PASS]` Generates chronological TREND insight across multiple periods
4. `[PASS]` Generates formatted GROWTH insight with percentage increase and next step
5. `[PASS]` Detects recent period volume/revenue contraction as DECLINE insight
6. `[PASS]` Identifies dominant dimension category as TOP_CONTRIBUTOR insight
7. `[PASS]` Identifies Pareto/concentration patterns as CONCENTRATION insight
8. `[PASS]` Detects high-null density columns as QUALITY insight
9. `[PASS]` Anomaly detection integrates cleanly without exception
10. `[PASS]` Forecast engine produces cautious forward-looking FORECAST insight
11. `[PASS]` Returns graceful insufficient_data response when records < 2
12. `[PASS]` Handles empty tables with zero records gracefully
13. `[PASS]` Handles schema without numeric measure columns without crashing
14. `[PASS]` Skips temporal insights gracefully when no time-series columns exist
15. `[PASS]` Every generated insight contains verifiable structured evidence
16. `[PASS]` Insights include reproducible, read-only SQL lineage queries
17. `[PASS]` Insights cache is strictly user-scoped; clearing User A leaves User B intact
18. `[PASS]` Cache invalidation removes user insights report on demand
19. `[PASS]` Groq failure falls back silently to deterministic explanation
20. `[PASS]` Guaranteed read-only: database state and row counts are completely unchanged

**Result:** `20 passed, 0 failed`

### B. Full Regression Suite Results
| Suite | Command | Result |
|---|---|:---:|
| **Python Syntax Compilation** | `python -m compileall app` | **PASS (0 errors)** |
| **Phase 8.1 BI Suite** | `python scratch/test_phase8_bi.py` | **20 / 20 PASS** |
| **Phase 7 Security Suite** | `python scratch/test_phase7_security.py` | **35 / 35 PASS** |
| **Phase 7 Isolation Suite** | `python scratch/test_phase7_isolation.py` | **12 / 12 PASS** |
| **Phase 5 Specialist Agent Suite** | `python scratch/test_phase5_agents.py` | **32 / 32 PASS** |
| **Real Database Agents Integration** | `python scratch/test_real_db_agents.py` | **A–F ALL PASS** |
| **Frontend Production Build** | `cd frontend && npm run build` | **PASS (0 errors)** |

---

## 12. Safe Action Integration
Phase 8.1 strictly complies with the no-write guarantee. Business insights **never** execute database mutations. If an insight suggests remediation (e.g. an unindexed foreign key column in a large table), it provides a clear recommendation to review the indexing strategy. Any eventual modification must follow the established Phase 5/6/7 safe action lifecycle: `PROPOSE -> PREVIEW -> CONFIRM -> EXECUTE -> VERIFY -> AUDIT`.

---

## 13. Known Limitations & Future Roadmap
1. **Scheduled Proactive Monitoring:** Not yet active in Phase 8.1 per explicit instructions (to prevent expanding ephemeral local storage dependencies before durable cloud persistence is added in Phase 8.x).
2. **Multi-Table Joins for Breakdowns:** Cross-table dimension aggregations currently focus on entity tables and direct foreign-key joins. Multi-hop snowflake joins will be expanded in Phase 8.2.
3. **Database Dialect Date Functions:** Date truncation currently supports SQLite (`strftime`), PostgreSQL (`TO_CHAR`), and MySQL (`DATE_FORMAT`). Additional dialects will be added as drivers are enabled.
