# BG AI — Phase 6 Production Readiness & Security Audit Report

**Generated:** 2026-09-30  
**Auditor:** Phase 6 Automated + Manual Engineering Audit  
**Scope:** Full backend + frontend codebase review against 25 audit areas  
**Status:** ⛔ NOT READY FOR PRODUCTION (Critical + High blockers unresolved)

---

## Severity Classification

| Level | Count | Resolved |
|---|---|---|
| CRITICAL | 1 | 0 |
| HIGH | 4 | 0 |
| MEDIUM | 8 | 3 |
| LOW | 4 | 0 |
| INFO | 3 | N/A |

---

## Regression Test Results

| Suite | Result |
|---|---|
| Phase 5 Agent Tests (32 items) | **32/32 PASS** |
| Real DB Tests (A–F) | **6/6 PASS** |
| Frontend Build | **PASS (0 errors)** |
| SQL Bypass Tests | **12/12 BLOCKED** |
| Prompt Injection Tests | **9/9 BLOCKED** |
| Transaction Rollback | **PASS** |
| Action Replay Protection | **PASS** |
| Multi-user isolation | **VULNERABLE** |
| Authentication | **NOT IMPLEMENTED** |

---

## FINDING: CRITICAL-001 — Multi-User State Collision (Global Engine)

**Severity:** CRITICAL  
**Area:** Multi-User Isolation (Area 2)  
**File:** `backend/app/database/database_manager.py` lines 8–9  
**Status:** NOT FIXED — Documented as release blocker

### Problem

`database_manager.py` uses module-level global variables for active database state:

```python
current_db_type: str = "none"
engine = None
```

All endpoints — schema, query, intelligence scan, CRUD, agents, forecasting, anomaly, audit — call `get_engine()` and `get_current_db_type()`, which return this single shared global state.

### Impact

When User B connects to Database B, User A's subsequent requests immediately run against Database B. There is no session-level isolation. This affects:

- Schema API → returns wrong schema to User A
- Intelligence cache → cached report is from wrong database
- Agent tasks → run analysis against wrong database
- CRUD operations → INSERT/UPDATE/DELETE against wrong database
- Action confirmation → confirmed action executes on wrong database
- Forecast → time-series data from wrong database

### Evidence (Automated Test Confirmation)

From `audit_phase6.py` execution:

```
[MULTI-USER TEST]
User A connects: ecommerce.db (has 'customers' table)
User B connects: temp_b.db (no 'customers' table)
User A queries SELECT * FROM customers
Result: sqlite3.OperationalError: no such table: users
```

User A's query ran against User B's database — confirmed collision.

### Correct Future Architecture

Each request must carry a session token. A per-session engine registry must map token → engine. The global engine must be eliminated:

```python
_session_engines: dict[str, Engine] = {}

def get_engine(session_token: str) -> Engine | None:
    return _session_engines.get(session_token)
```

All API endpoints must extract session_token from request headers/cookies and pass it through to every DB-touching function. This is a major architectural change requiring refactoring of all 50+ endpoint handlers.

### Recommendation

Do NOT attempt to fix in Phase 6. Requires a complete architectural rewrite. **Release blocker for any multi-user deployment.**

For single-user / personal deployment, this is acceptable as a known limitation.

---

## FINDING: HIGH-001 — No Authentication on Any Endpoint

**Severity:** HIGH  
**Area:** Authentication / Authorization (Area 5)  
**File:** `backend/app/main.py` (all endpoints)  
**Status:** NOT FIXED

### Problem

Zero authentication exists on any API endpoint. Every endpoint is publicly accessible with no API key, session token, Bearer token, or basic auth.

Exposed endpoints include:
- `POST /connect` — connects to any user-specified database
- `POST /restore` — restores arbitrary backup files
- `POST /agents/run` — runs arbitrary agent tasks against connected DB
- `POST /agent-actions/{id}/confirm` — executes database modifications
- `GET /backup` — downloads database backup
- `GET /query` — executes SQL queries

### Impact

Any network-reachable client can execute agent actions, modify database records, download backups, or reconnect to a different database without credentials.

### Recommended Fix

Implement FastAPI dependency injection with API key or JWT Bearer token authentication:

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="Unauthorized")
```

Apply to all mutation endpoints at minimum. On Render, set `API_KEY` as an environment variable.

---

## FINDING: HIGH-002 — Invalid CORS Configuration

**Severity:** HIGH  
**Area:** CORS (Area 8)  
**File:** `backend/app/main.py` lines ~15–28  
**Status:** NOT FIXED

### Problem

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # INVALID COMBINATION
    ...
)
```

Per the CORS specification (and enforced by all modern browsers): `allow_credentials=True` is **incompatible** with `allow_origins=["*"]`. When `allow_credentials=True` is set, the browser requires an explicit origin (not wildcard), otherwise the preflight fails silently. Some browsers ignore credentials entirely in this case; others may behave inconsistently.

### Impact

Credential-bearing cross-origin requests (cookies, Authorization headers) may fail in certain browser/environment combinations. Any future authentication implementation (Bearer token / cookie-based) would be blocked by this CORS misconfiguration.

### Recommended Fix

```python
allow_origins=["https://thebg.co.in", "http://localhost:5173"],
allow_credentials=True,
```

---

## FINDING: HIGH-003 — User Data Sent to External AI (Groq) Without Explicit Consent Mechanism

**Severity:** HIGH  
**Area:** Data Privacy (Area 23)  
**File:** `backend/app/agent/orchestrator.py`  
**Status:** NOT FIXED (by design, but undisclosed)

### Problem

The following user data is transmitted to Groq's API on every relevant query:

| Groq Call Location | Data Sent |
|---|---|
| Line 282 — Intent classification | User message |
| Line 758 — Table resolver | User message + table names |
| Line 821 — Table resolver (full) | User message + table names + column names |
| Lines 1474, 1920 — UPDATE/DELETE SQL gen | User message + full schema (table + column names) |
| Line 4325 — Main SELECT SQL gen | User message + compact schema + database intelligence profile (aggregated stats) + db_type |
| Lines 324, 370, 541 — Chat/general | User message only |

**What IS sent to Groq:**
- User's natural language queries (may contain sensitive business terminology)
- Database schema: table names, column names, types
- Database intelligence context: aggregated statistics (row counts, null percentages, etc.)
- Database type (sqlite, mysql, postgresql)

**What is NOT sent to Groq:**
- Raw row data (actual cell values from SELECT results)
- Database passwords or connection strings
- User PII unless contained in natural language query

### Impact

Users connecting proprietary databases expose their complete schema structure and query intent to Groq's inference infrastructure. No user consent mechanism, opt-out, or disclosure exists in the UI.

### Evidence

Line 4298–4302 of orchestrator.py:
```python
LIVE DATABASE SCHEMA:
{compact_schema}

DATABASE INTELLIGENCE PROFILE:
{database_context}
```

`compact_schema` = `table_name: col1, col2, col3` for every table  
`database_context` = intelligence profile with health scores, row counts, attention items

### Recommended Fix

1. Add a clear disclosure in the UI: "BG AI uses Groq AI to generate SQL and explanations. Your schema structure is shared with Groq."
2. Add a consent toggle in connection settings.
3. Consider a local-inference option (Ollama) for privacy-sensitive deployments.

---

## FINDING: HIGH-004 — Audit Log Lost on Ephemeral Filesystem (Render)

**Severity:** HIGH  
**Area:** Audit Logging (Area 11)  
**File:** `backend/app/agents/audit.py`  
**Status:** NOT FIXED

### Problem

The action audit store is in-memory (`_action_store: dict[str, ActionPlan]`) and persists to `audit_log.json` in the application root directory. On Render (and most PaaS providers), the filesystem is **ephemeral** — all files are wiped on every redeploy or dyno restart.

```python
AUDIT_LOG_PATH = Path(__file__).parent.parent.parent / "audit_log.json"
```

### Impact

All records of confirmed/executed database actions are permanently lost on restart. This eliminates the audit trail entirely after each deployment, making it impossible to review what was changed, when, and by whom.

### Recommended Fix

- Write audit log to a persistent external store (PostgreSQL, Redis, or an external S3 bucket).
- Minimum: write to a Render Persistent Disk volume mounted at a known path.

---

## FINDING: MEDIUM-001 — No Rate Limiting on Expensive Operations

**Severity:** MEDIUM  
**Area:** API Security / Performance (Areas 6, 22)  
**File:** `backend/app/main.py`, all agent endpoints  
**Status:** NOT FIXED

### Problem

No rate limiting exists on computationally expensive endpoints:

- `POST /agents/run` — triggers full intelligence scan, anomaly detection, AI analysis
- `POST /chat` — triggers Groq API call (external billing, latency)
- `GET /intelligence` — full database scan across all tables
- `POST /forecast` — full time-series analysis

Any client can flood these endpoints, causing:
- Groq API cost overruns
- Database connection exhaustion
- Backend CPU/memory saturation
- Denial of service to legitimate users

### Recommended Fix

Use `slowapi` (FastAPI rate limiting) with per-IP limits:

```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/agents/run")
@limiter.limit("10/minute")
async def run_agent(...): ...
```

---

## FINDING: MEDIUM-002 — PRAGMA Configuration Write Blocked (FIXED)

**Severity:** MEDIUM  
**Area:** SQL Security (Area 3)  
**File:** `backend/app/tools/execute_query.py` lines 76–98  
**Status:** ✅ FIXED

### Problem (Pre-Fix)

`PRAGMA journal_mode = WAL` and other write-form PRAGMA statements were allowed through SQL validation and could be used to modify SQLite database configuration.

### Fix Applied

Added PRAGMA parsing to split on `=` — if right-hand side value is present, block the statement. Read-form PRAGMA (`PRAGMA table_info(...)`) is still allowed.

### Verification

SQL bypass test: `PRAGMA journal_mode = WAL` → **BLOCKED**. `PRAGMA table_info(customers)` → **ALLOWED**.

---

## FINDING: MEDIUM-003 — Path Traversal in /restore (FIXED)

**Severity:** MEDIUM  
**Area:** Deployment / File Safety (Area 20)  
**File:** `backend/app/main.py` lines 158–175  
**Status:** ✅ FIXED

### Problem (Pre-Fix)

The `/restore` endpoint accepted arbitrary filenames without sanitization. A filename like `../../etc/passwd` could potentially traverse directories.

### Fix Applied

```python
safe_name = Path(file.filename).name  # strips directory components
if not safe_name.lower().endswith(".db"):
    raise HTTPException(status_code=400, detail="Only .db files are supported for restore.")
```

### Verification

Path traversal filenames are now sanitized to basename only. Non-`.db` extensions are rejected.

---

## FINDING: MEDIUM-004 — Safety Guard Ordering in ActionAgent (FIXED)

**Severity:** MEDIUM  
**Area:** Specialist Agent Security (Area 3/5)  
**File:** `backend/app/agents/action_agent.py`  
**Status:** ✅ FIXED

### Problem (Pre-Fix)

The injection trigger check (blocking GRANT, REVOKE, DROP TABLE, etc.) occurred AFTER the database connectivity check. This meant that without a connected database, blocked commands returned "No database connected" instead of a safety rejection — potentially obscuring the security intent.

### Fix Applied

Moved `injection_triggers` check to the very top of `execute()`, before any DB access. All forbidden patterns are now rejected regardless of database state.

### Verification

Phase 5 Tests 21 (GRANT blocking) and 23 (prompt injection): **PASS** (previously FAIL).

---

## FINDING: MEDIUM-005 — psycopg2 Undeclared in requirements.txt

**Severity:** MEDIUM  
**Area:** Dependency Health (Area 18)  
**File:** `backend/requirements.txt`  
**Status:** NOT FIXED

### Problem

`psycopg2==2.9.12` is installed in the active Python environment but is **not declared** in `requirements.txt`. A fresh deployment (`pip install -r requirements.txt`) will not install `psycopg2`, causing PostgreSQL connections to fail silently at runtime.

### Evidence

```
pip show psycopg2   → psycopg2 2.9.12
grep psycopg requirements.txt → (no output)
```

### Recommended Fix

Add to `requirements.txt`:
```
psycopg2-binary==2.9.12
```

(Use `psycopg2-binary` instead of `psycopg2` to avoid C compilation requirement on Render.)

---

## FINDING: MEDIUM-006 — Backup Path Leaked in API Response

**Severity:** MEDIUM  
**Area:** Data Privacy / API Security (Areas 23, 7)  
**File:** `backend/app/main.py` lines ~150–157  
**Status:** NOT FIXED

### Problem

The `/backup` endpoint returns the full server filesystem path of the backup file in the API response. This exposes server directory structure to clients.

### Evidence

```json
{"backup_path": "/app/database/backups/ecommerce_2026-09-30.db", "success": true}
```

### Recommended Fix

Return only a download URL or filename, not the absolute server path.

---

## FINDING: MEDIUM-007 — Stack Traces Exposed in /chat Error Handler

**Severity:** MEDIUM  
**Area:** Error Handling (Area 16)  
**File:** `backend/app/main.py` chat endpoint  
**Status:** NOT FIXED

### Problem

The `/chat` endpoint uses `traceback.print_exc()` which writes full Python stack traces to stdout. On Render, stdout is accessible in the deployment logs. In debug configurations, this may also leak internal module paths and variable names.

### Recommended Fix

Replace `traceback.print_exc()` with structured logging. Return generic error messages to clients, log details server-side only.

---

## FINDING: MEDIUM-008 — Anomaly Detection Samples Only 1,000 Rows

**Severity:** MEDIUM  
**Area:** Anomaly Detection Correctness (Area 15)  
**File:** `backend/app/intelligence/anomaly/detector.py` lines 61–78  
**Status:** NOT FIXED (documented limitation)

### Problem

Anomaly detection queries `LIMIT 1000` per column per table. For tables with millions of rows, IQR-based outlier detection will miss anomalies outside the sampled 1,000 rows.

```python
SELECT {column} FROM {table} WHERE {column} IS NOT NULL LIMIT 1000
```

Additionally, only up to 3 numeric columns are checked per table.

### Impact

Large production tables may have undetected outliers. The anomaly report is statistically valid only for the sample.

### Recommended Fix

Document sampling limitation clearly in UI. For large tables, optionally increase to `LIMIT 10000` or use reservoir sampling.

---

## FINDING: LOW-001 — Forecasting Prediction Interval is Approximation

**Severity:** LOW  
**Area:** Forecasting Correctness (Area 14)  
**File:** `backend/app/intelligence/forecasting/forecaster.py` lines 258–260  
**Status:** NOT FIXED (documented)

### Problem

The 95% prediction interval is computed as `1.96 * residual_std` — a normal approximation. This is not a statistically rigorous prediction interval for Holt's Exponential Smoothing (which requires simulation-based intervals or proper forecasting error propagation).

### Impact

Displayed confidence bounds are approximate. For financial or critical decisions, users should not treat these as precise statistical intervals.

### Recommended Fix

Document in UI: "Confidence interval is an approximation based on historical residual standard deviation."

---

## FINDING: LOW-002 — Dead Code: gemini_agent.py + google-generativeai

**Severity:** LOW  
**Area:** Dead Code / Architecture Risks (Area 24)  
**File:** `backend/app/agent/gemini_agent.py`, `backend/requirements.txt`  
**Status:** NOT FIXED

### Problem

`gemini_agent.py` defines `ask_gemini()` which is **never called** anywhere in the codebase. The `google-generativeai` package is included in `requirements.txt` but serves no active purpose.

This adds ~50MB to the deployment image and introduces an unnecessary transitive dependency surface.

### Evidence

```
grep -r "ask_gemini" backend/ → only gemini_agent.py (definition only)
grep "google-generativeai" requirements.txt → found
```

### Recommended Fix

Remove `gemini_agent.py` and remove `google-generativeai` from `requirements.txt`.

---

## FINDING: LOW-003 — aiosqlite in requirements.txt but Unused

**Severity:** LOW  
**Area:** Dependency Health (Area 18)  
**File:** `backend/requirements.txt`  
**Status:** NOT FIXED

### Problem

`aiosqlite` is listed in `requirements.txt` but the application uses SQLAlchemy's synchronous engine. No async SQLite operations are performed.

### Recommended Fix

Remove `aiosqlite` from `requirements.txt`.

---

## FINDING: LOW-004 — No Structured Logging

**Severity:** LOW  
**Area:** Observability (Area 17)  
**File:** Throughout `backend/app/`  
**Status:** NOT FIXED

### Problem

All logging is via `print()` statements. There is no structured logging (JSON format), no log levels, no request IDs, and no correlation between requests. This makes production debugging extremely difficult.

### Evidence

```python
# orchestrator.py
print("\n========== BG AI SQL ==========")
print("USER:", user_message)
print("RAW :", raw_sql)
```

### Recommended Fix

Replace `print()` with Python's `logging` module:

```python
import logging
logger = logging.getLogger("bgai")
logger.info("SQL generated", extra={"user_msg": user_message[:100], "sql": sql[:200]})
```

Add a structured JSON formatter for production environments.

---

## FINDING: INFO-001 — Backup System is SQLite-Only

**Severity:** INFO  
**Area:** Backup / Restore Safety (Area 19)  
**File:** `backend/app/main.py`, `backend/app/database/db.py`  
**Status:** Documented limitation

### Problem

The `/backup` endpoint uses `shutil.copy2()` of the `.db` file. This only works for SQLite databases. MySQL and PostgreSQL databases have no backup mechanism implemented.

### Impact

Users with MySQL/PostgreSQL connections cannot use the backup feature.

---

## FINDING: INFO-002 — Test Scripts in Production Code Directory

**Severity:** INFO  
**Area:** Dead Code (Area 24)  
**File:** `backend/app/agent/test_gemini.py`, `backend/app/agent/test_groq.py`  
**Status:** Documented

### Problem

Test scripts exist inside the production `app/agent/` package directory. These are not imported, but they are part of the deployed artifact.

### Recommended Fix

Move to `backend/tests/` or `backend/scratch/`.

---

## FINDING: INFO-003 — Database Dialect Compatibility

**Severity:** INFO  
**Area:** Database Dialect Compatibility (Area 13)  
**Status:** Documented

### Current State

| Database | Support | Notes |
|---|---|---|
| SQLite | Full | Primary test database |
| MySQL | Partial | PyMySQL driver declared in requirements.txt |
| PostgreSQL | Partial | `psycopg2` installed but NOT in requirements.txt (MEDIUM-005) |

`_normalize_sql_for_active_database()` in `orchestrator.py` handles basic dialect normalization (backtick → double-quote for PostgreSQL). Not all SQL features are tested across all dialects.

---

## Security Audit Summary — Groq Privacy Audit

### What Groq Receives Per Request Type

| Request | Table Names | Column Names | Row Data | User Query | Intelligence Stats |
|---|---|---|---|---|---|
| Intent classification | No | No | No | Yes | No |
| Chat / General | No | No | No | Yes | No |
| Table resolver | Yes | No | No | Yes | No |
| Table resolver (full) | Yes | Yes | No | Yes | No |
| UPDATE/DELETE SQL gen | Yes | Yes | No | Yes | No |
| SELECT SQL gen | Yes | Yes | No | Yes | Yes (aggregated) |

**No raw row data (cell values) is ever sent to Groq.**  
**Database passwords and connection strings are never sent to Groq.**  
**Schema structure (table/column names) IS sent on SQL generation requests.**

---

## SQL Security Audit

All 12 bypass variants tested and blocked:

| Attack | Result |
|---|---|
| `DROP TABLE users` | BLOCKED |
| `DR/**/OP TABLE users` (comment bypass) | BLOCKED (default-deny) |
| `ALTER TABLE customers ADD COLUMN pw TEXT` | BLOCKED |
| `TRUNCATE TABLE orders` | BLOCKED |
| `DELETE FROM customers` (no WHERE) | BLOCKED |
| `UPDATE customers SET role='admin'` (no WHERE) | BLOCKED |
| `SELECT 1; DROP TABLE users` (multi-statement) | BLOCKED |
| `PRAGMA journal_mode = WAL` | BLOCKED |
| `ATTACH DATABASE '/etc/passwd' AS evil` | BLOCKED |
| `GRANT ALL PRIVILEGES ON *.* TO 'hacker'` | BLOCKED |
| `REVOKE ALL ON customers FROM PUBLIC` | BLOCKED |
| `'; DROP TABLE users; --` | BLOCKED |

---

## Phase 6 Action Items — Priority Order

### Release Blockers (Must Fix Before Multi-User Production)

1. **CRITICAL-001** — Implement per-session engine registry (architectural rewrite)
2. **HIGH-001** — Implement API key or JWT authentication
3. **HIGH-002** — Fix CORS: replace `allow_origins=["*"]` with explicit origin list
4. **HIGH-004** — Persist audit log to external database or persistent volume

### Should Fix Before Public Launch

5. **HIGH-003** — Add Groq data disclosure + consent UI
6. **MEDIUM-001** — Add `slowapi` rate limiting on expensive endpoints
7. **MEDIUM-005** — Add `psycopg2-binary` to `requirements.txt`
8. **MEDIUM-006** — Remove server path from backup API response
9. **MEDIUM-007** — Replace `traceback.print_exc()` with structured logging

### Can Fix Incrementally

10. **LOW-002** — Remove `gemini_agent.py` and `google-generativeai`
11. **LOW-003** — Remove `aiosqlite` from requirements
12. **LOW-004** — Implement structured logging with `logging` module

---

## Final Verdict

```
AUDIT STATUS: NOT PRODUCTION READY

Critical blockers:  1  (multi-user isolation — architectural rewrite required)
High blockers:      4  (auth, CORS, Groq privacy, audit persistence)
Medium issues:      8  (3 fixed, 5 open)
Low issues:         4  (0 fixed, 4 open)
Info items:         3

Phase 5 tests:              32/32 PASS
Real DB tests (A-F):        6/6 PASS
Frontend build:             PASS (0 errors)
SQL bypass tests:           12/12 BLOCKED
Prompt injection tests:     9/9 BLOCKED
Transaction rollback:       PASS
Action replay protection:   PASS
Multi-user isolation:       VULNERABLE (global engine — release blocker)
Authentication:             NOT IMPLEMENTED (release blocker)

Suitable for:
  - Single-user personal/internal use: YES (with awareness of known limitations)
  - Multi-user public deployment:       NO (CRITICAL-001 blocks this)
  - Production with user data:          NO (HIGH-001, HIGH-003 block this)

DO NOT COMMIT OR PUSH.
```
