# BG AI — Groq Data Flow Documentation

**Phase 7 | Privacy Audit**  
**Generated:** 2026-09-30

---

## Overview

BG AI uses Groq's inference API (Llama 3 / Mixtral models) to:
1. Classify user intent (SQL vs. chat vs. analytics)
2. Resolve which database table the user is referring to
3. Generate SQL statements from natural language
4. Generate explanations of query results
5. Generate UPDATE/DELETE modification SQL
6. Power conversational chat responses

This document catalogs every Groq API call in the codebase, what data is sent,
and what data is explicitly NOT sent.

---

## Groq API Call Inventory

### Call 1 — Intent Classification
**File:** `backend/app/agent/orchestrator.py` line ~282  
**Function:** `_determine_intent(user_message, schema)`

**What is sent:**
| Category | Data | Sent? |
|---|---|---|
| A. Schema metadata | Table names only (no column types, no row data) | ✅ Table names |
| D. User question | Full natural language query | ✅ |
| E. Query result rows | No | ❌ |
| F. Generated SQL | No | ❌ |
| Passwords / credentials | No | ❌ Never |

**Purpose:** Classify as `sql`, `chat`, `analytics`, `dashboard`, `general_knowledge`, etc.

---

### Call 2 — Chat Response (no DB connected)
**File:** `backend/app/agent/orchestrator.py` line ~541  
**Function:** `_handle_no_db_message(user_message)`

**What is sent:**
| Category | Data | Sent? |
|---|---|---|
| D. User question | Full user message | ✅ |
| Schema / DB data | No (no DB is connected) | ❌ |

**Purpose:** Generate a friendly response when no database is connected.

---

### Call 3 — Chat Response (DB connected)
**File:** `backend/app/agent/orchestrator.py` line ~324  
**Function:** `_handle_chat(user_message)`

**What is sent:**
| Category | Data | Sent? |
|---|---|---|
| D. User question | Full user message | ✅ |
| Schema | No | ❌ |

**Purpose:** Conversational response (not DB query).

---

### Call 4 — General Knowledge Response
**File:** `backend/app/agent/orchestrator.py` line ~370  
**Function:** `_handle_general_knowledge(user_message)`

**What is sent:**
| Category | Data | Sent? |
|---|---|---|
| D. User question | Full user message | ✅ |
| Schema | No | ❌ |

**Purpose:** Answer SQL/database educational questions without referencing user's DB.

---

### Call 5 — Table Resolver (simple)
**File:** `backend/app/agent/orchestrator.py` line ~758  
**Function:** `_resolve_table_from_message(message, schema)` → Groq fallback

**What is sent:**
| Category | Data | Sent? |
|---|---|---|
| A. Schema metadata | Table names only (comma-separated list) | ✅ Table names |
| D. User question | Full user message | ✅ |
| B. Column names | No | ❌ |
| Row data | No | ❌ |

**Purpose:** Determine which table from the user's schema matches the user's request.

---

### Call 6 — Table Resolver (full schema)
**File:** `backend/app/agent/orchestrator.py` line ~821  
**Function:** `_extract_table(user_message, schema)` → full schema description

**What is sent:**
| Category | Data | Sent? |
|---|---|---|
| A. Schema metadata | Table names | ✅ |
| B. Column names | Column names per table (no types, no values) | ✅ Column names |
| D. User question | Full user message | ✅ |
| Row data / cell values | No | ❌ |

**Purpose:** Semantically resolve the target table from natural language.

**Example prompt fragment:**
```
LIVE DATABASE SCHEMA:
- customers: id, name, email, created_at
- orders: id, customer_id, amount, status, date
- products: id, name, price, category

USER REQUEST:
show me this month's revenue
```

---

### Call 7 — UPDATE SQL Generation
**File:** `backend/app/agent/orchestrator.py` line ~1474  
**Function:** `_resolve_update_request(user_message, schema)`

**What is sent:**
| Category | Data | Sent? |
|---|---|---|
| A. Schema metadata | Full schema dict (table names + column names) | ✅ |
| B. Column names | All column names per table | ✅ |
| D. User question | Full user message | ✅ |
| C. Sample values | No | ❌ |
| Row data | No | ❌ |

**Purpose:** Parse UPDATE natural language into JSON `{table, fields, where}`.

---

### Call 8 — Modification SQL Generation (UPDATE/DELETE/DROP/TRUNCATE)
**File:** `backend/app/agent/orchestrator.py` line ~1920  
**Function:** `_build_modification_sql(operation, user_message, schema)`

**What is sent:**
| Category | Data | Sent? |
|---|---|---|
| A. Schema metadata | Full schema dict | ✅ |
| B. Column names | All column names | ✅ |
| D. User question | Full user message | ✅ |
| Row data | No | ❌ |

**Purpose:** Generate a complete UPDATE/DELETE SQL statement.

---

### Call 9 — Primary SELECT SQL Generation
**File:** `backend/app/agent/orchestrator.py` line ~4325  
**Function:** Main SQL generation path

**What is sent:**
| Category | Data | Sent? |
|---|---|---|
| A. Schema metadata | Compact schema: `table: col1, col2, col3` | ✅ |
| B. Column names | All column names | ✅ |
| D. User question | Full user message | ✅ |
| G. Database intelligence profile | Aggregated stats (row counts, health score, key findings) | ✅ Aggregated only |
| G. Database type | sqlite / mysql / postgresql | ✅ |
| C. Sample row values | No | ❌ |
| E. Query result rows | No | ❌ |

**Purpose:** Generate a SELECT SQL from natural language + schema.

**Example database_context:**
```
Database: ecommerce.db | Type: SQLite | Tables: 4 | Records: 13
Health Score: 94/100 | Key tables: customers (5 rows), orders (4 rows)
Attention: Missing primary key on 'inventory'
```

---

## Summary Table

| Groq Call | Table Names | Column Names | Row Data | User Query | Aggregated Stats |
|---|---|---|---|---|---|
| Intent classification | ✅ | ❌ | ❌ | ✅ | ❌ |
| Chat (no DB) | ❌ | ❌ | ❌ | ✅ | ❌ |
| Chat (with DB) | ❌ | ❌ | ❌ | ✅ | ❌ |
| General knowledge | ❌ | ❌ | ❌ | ✅ | ❌ |
| Table resolver (simple) | ✅ | ❌ | ❌ | ✅ | ❌ |
| Table resolver (full) | ✅ | ✅ | ❌ | ✅ | ❌ |
| UPDATE SQL gen | ✅ | ✅ | ❌ | ✅ | ❌ |
| Modification SQL gen | ✅ | ✅ | ❌ | ✅ | ❌ |
| SELECT SQL gen (main) | ✅ | ✅ | ❌ | ✅ | ✅ aggregated |

---

## What is NEVER Sent to Groq

- Database passwords, connection strings with credentials
- Raw row data (actual cell values from SELECT results)
- API keys, tokens, secrets
- User PII (unless the user types it in their natural language query)
- Backup file contents
- JWT tokens or session identifiers

---

## Privacy Risk Classification

| Risk | Assessment |
|---|---|
| Schema structure exposed (table/column names) | **Present** — by design, required for SQL generation |
| Row data exposed | **Not present** |
| Passwords exposed | **Not present** |
| Business intelligence exposed | **Partial** — aggregated row counts and health scores only |
| User's NL query exposed | **Present** — query intent is sent for classification/generation |

---

## Recommendations

1. **User consent disclosure** — Add a visible notice in the UI: *"BG AI uses Groq AI to understand your questions. Your database schema structure (table and column names) and your questions are shared with Groq's inference API."*

2. **Opt-out option** — Future: Allow local LLM inference (Ollama) as an alternative for privacy-sensitive deployments.

3. **Context minimization** — The main SQL generation path (Call 9) currently sends the full compact schema. For databases with hundreds of tables, consider sending only the most relevant tables (determined by relevance scoring). This is a future optimization.

4. **Groq logging policy** — Verify Groq's current data retention and logging policy at https://console.groq.com/docs/privacy. As of Phase 7, this has not been independently verified.

---

## Conclusion

BG AI sends **schema structure** and **user questions** to Groq. It does **not** send raw row data, passwords, or tokens. This is a deliberate architectural choice required for LLM-assisted SQL generation. Users with sensitive schemas should be clearly informed about this data flow before connecting their databases.
