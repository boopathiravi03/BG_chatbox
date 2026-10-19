# BG AI — AI-Powered Conversational Database Intelligence & Visualization

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React_19_TypeScript-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Bundler-Vite_8-646CFF?logo=vite&logoColor=white)](https://vitejs.dev)
[![Tailwind CSS](https://img.shields.io/badge/Styling-Tailwind_CSS_v4-38B2AC?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy_2.0-D71F00?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org)

**BG AI** is a production-oriented, AI-powered conversational database intelligence workspace. It bridges natural-language user queries with multi-engine database management, visual analytics, autonomous specialist agents, automated anomaly detection, forecasting, and enterprise-grade cybersecurity governance.

- **Web Application:** [https://thebg.co.in/](https://thebg.co.in/)
- **Backend API Deployment:** [https://bg-chatbox.onrender.com](https://bg-chatbox.onrender.com)
- **Interactive Swagger Documentation:** [https://bg-chatbox.onrender.com/docs](https://bg-chatbox.onrender.com/docs)

---

## Table of Contents

- [1. Problem Statement](#1-problem-statement)
- [2. Our Solution](#2-our-solution)
- [3. Key Features](#3-key-features)
- [4. How BG AI Works](#4-how-bg-ai-works)
- [5. System Architecture](#5-system-architecture)
- [6. Technology Stack](#6-technology-stack)
- [7. Supported Databases & Connectors](#7-supported-databases--connectors)
- [8. Project Directory Structure](#8-project-directory-structure)
- [9. Prerequisites](#9-prerequisites)
- [10. Installation & Local Setup](#10-installation--local-setup)
- [11. Environment Variables](#11-environment-variables)
- [12. Running BG AI Locally](#12-running-bg-ai-locally)
- [13. Core API Endpoints](#13-core-api-endpoints)
- [14. Database Connection & Lifecycle](#14-database-connection--lifecycle)
- [15. Security, Governance & Intrusion Safeguards](#15-security-governance--intrusion-safeguards)
- [16. Testing & Quality Assurance](#16-testing--quality-assurance)
- [17. Windows Desktop Application (Electron + PyInstaller)](#17-windows-desktop-application-electron--pyinstaller)
- [18. Cloud Deployment Architecture](#18-cloud-deployment-architecture)
- [19. Troubleshooting Guide](#19-troubleshooting-guide)
- [20. Product Roadmap](#20-product-roadmap)
- [21. Contributing](#21-contributing)
- [22. License](#22-license)
- [23. Acknowledgements & Authors](#23-acknowledgements--authors)

---

## 1. Problem Statement

Modern enterprise data architectures face severe accessibility and governance bottlenecks:

1. **SQL Skill Barriers:** Business teams and analysts frequently depend on data engineers to write complex SQL joins, aggregations, or document queries.
2. **Context Switching Across Data Engines:** Teams juggle different management interfaces for relational databases (MySQL, PostgreSQL, SQLite, SQL Server), NoSQL document databases (MongoDB), in-memory caches (Redis), vector databases (Qdrant, Chroma), and flat files (CSV, Excel).
3. **Operational Risks of Destructive Queries:** Conversational AI assistants that execute arbitrary SQL risk accidental data loss from unchecked `DROP`, `TRUNCATE`, or unconstrained `UPDATE`/`DELETE` queries.
4. **Data Privacy & Credential Leakage:** Many LLM-assisted database tools unwittingly transmit unmasked Personally Identifiable Information (PII), credit card numbers, or database connection strings containing plaintext passwords to external cloud models.
5. **Lack of Verifiable Auditability:** Typical AI operations lack cryptographic proof of provenance, tamper resistance, and intrusion tracking.

---

## 2. Our Solution

BG AI eliminates these challenges through a unified, secure database intelligence platform:

- **Conversational Intelligence:** Converts plain English into safe, validated SQL queries and document aggregations.
- **Multi-Engine Connector Architecture:** Seamlessly connects to SQLite, MySQL, PostgreSQL, MariaDB, SQL Server, MongoDB, Redis, Qdrant, Chroma, and tabular flat files.
- **Deterministic Security Gates:** Enforces human-in-the-loop confirmation for write mutations, unconditionally blocks destructive DDL (`DROP`, `TRUNCATE`, `ALTER`), and validates `WHERE` clauses.
- **Autonomous Specialist AI Agents:** Dispatches tasks across 6 specialized agents for data quality, health assessment, anomaly detection, business intelligence, query performance, and controlled mutations.
- **Enterprise Governance & Tamper-Evident Ledger:** Implements a SHA-256 hash-chained immutable audit ledger, client IP intrusion detection, brute-force defense, and a zero-raw-secret sensitive data exposure scanner.

---

## 3. Key Features

### 💬 AI Command Workspace
- Natural-language query translation into safe SQL or native connector operations.
- Dynamic result tables with column sorting, live search filtering, pagination, and export to CSV, Excel, or PDF.
- Context-aware introductory summaries and query suggestions generated from the live database schema.

### 📊 Visual Analytics & Auto-Generated Charts
- Instant generation of interactive Chart.js visualizations (bar, line, doughnut, pie, polar area).
- Interactive Mermaid.js database relationship graphs and entity-relationship (ER) diagrams with foreign-key inspection.

### 🗄️ Multi-Database Data Explorer & CRUD
- Live database schema inspection for tables, columns, data types, indexes, and constraints.
- Inline record creation, cell-level editing, record deletion, and dynamic index management.
- Dynamic table creation and schema definitions across relational and NoSQL engines.

### 🧪 SQL Lab
- Raw SQL query editor with syntax highlighting, execution timing telemetry, row count reporting, and safe query validation.

### 🤖 Autonomous Specialist Agents (Phase 5)
- **Database Health Agent:** Evaluates connection health, schema complexity, missing indexes, and engine metrics.
- **Data Quality Agent:** Inspects null ratios, duplicates, invalid formats, and data anomalies.
- **Analyst Agent:** Performs cohort calculations, growth trends, top-contributor breakdowns, and revenue analytics.
- **Anomaly Agent:** Identifies structural anomalies, out-of-range numerical spikes, and orphaned records.
- **Performance Agent:** Pinpoints slow query bottlenecks, unindexed foreign keys, and missing secondary indexes.
- **Action Agent:** Prepares structured mutation plans (`INSERT`, `UPDATE`, `DELETE`) with bounded row estimation (`COUNT(*)`) and mandatory human confirmation.

### 🔍 Proactive Intelligence & Forecasting
- Evaluates operational KPIs, data velocity, completeness, and freshness.
- Statistical forecasting view tracking historical metric series and projected confidence bands.
- Centralized Anomaly Center reporting categorized severity levels (Critical, Warning, Informational).

### 🛡️ Cybersecurity & Intrusion Center
- **Security Posture Score (0–100):** Real-time posture assessment with mathematical deductions for vulnerabilities.
- **Sensitive Data Exposure Scanner:** Conservative regex and Luhn-validated detection of credit card numbers, plain passwords, SSNs, and private API keys with zero raw secret exposure.
- **IP Threat Intelligence & Intrusion Detection:**
  - Trusted-proxy IP extraction preventing spoofed `X-Forwarded-For` injection.
  - Brute-force authentication detection ($\ge 5$ failures within 300s).
  - High-frequency burst detection ($\ge 60$ requests within 60s).
  - Scanner/crawler probe identification (probing `.env`, `wp-`, `actuator`, `shell`).
  - Automated, time-limited IP quarantine with manual administrative unblock controls.
- **Tamper-Evident Audit Ledger:** Cryptographic SHA-256 hash-chained operational ledger with real-time verification.
- **Guardrail Policy Controls:** Human confirmation modals required before modifying live security guardrails.

---

## 4. How BG AI Works

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Client
    participant UI as React 19 Frontend
    participant Edge as IP & Security Middleware
    participant API as FastAPI Backend (Port 8001)
    participant Router as Agent & Intent Router
    participant Gate as SQL Safety & Policy Gate
    participant DB as Connected Database Engine
    participant Audit as Cryptographic Audit Store

    User->>UI: Enter prompt: "Show top 5 customers by sales"
    UI->>Edge: POST /chat (with Bearer Token & Connection Context)
    Edge->>Edge: Verify trusted proxy IP & rate limits
    Edge->>API: Forward authenticated request
    API->>Router: Classify user intent & fetch schema metadata
    Router->>Gate: Generate SQL & validate safety policies
    Gate-->>API: Status: Allowed (Read-only SELECT query)
    API->>DB: Execute query with bounded LIMIT
    DB-->>API: Return columns & record rows
    API->>Audit: Record data access event in SHA-256 hash chain
    API-->>UI: Return result set, query metadata & suggested charts
    UI->>User: Render interactive grid & Chart.js visualization
```

---

## 5. System Architecture

```mermaid
graph TD
    subgraph Client ["Client Presentation Tier (React 19 + TypeScript + Vite)"]
        UI_Nav["Workspace Sidebar & Navigation"]
        UI_Chat["AI Command Workspace"]
        UI_Explorer["Data Explorer & CRUD"]
        UI_Analytics["Analytics & Chart.js Dashboards"]
        UI_Agents["Agent Center (6 Specialist Agents)"]
        UI_Security["Cybersecurity & IP Threat Center"]
        UI_SQL["SQL Lab & Schema Visualizer"]
    end

    subgraph Middleware ["FastAPI Security & Gateway Middleware"]
        MW_CORS["CORS & Strict CSP Headers"]
        MW_Rate["SlowAPI Velocity Limiter"]
        MW_IP["IP Threat & Intrusion Middleware"]
        MW_Auth["Bearer JWT & Session Authenticator"]
    end

    subgraph Core ["Application & Intelligence Core"]
        CC_Context["Per-User Connection ContextVars"]
        INT_Agents["Specialist Agent Registry"]
        INT_Scanner["Database Posture & Sensitive Data Scanner"]
        INT_Anomaly["Statistical Anomaly Detector"]
        INT_Forecast["Forecasting & Trend Engine"]
        SEC_Gate["SQL Safety Gate (validate_sql)"]
        SEC_Policy["Governance Policy Engine"]
    end

    subgraph Connectors ["Multi-Database Connector Tier"]
        C_SQLite["SQLite Connector (Built-in)"]
        C_MySQL["MySQL & MariaDB Connectors"]
        C_PG["PostgreSQL Connector"]
        C_MSSQL["SQL Server Connector"]
        C_Mongo["MongoDB Connector"]
        C_Redis["Redis Key-Value Connector"]
        C_Vector["Qdrant & Chroma Vector Connectors"]
        C_Files["CSV, Excel & JSON Connectors"]
    end

    subgraph Storage ["Persistent State & Ledger"]
        DB_Ledger[("bgai_governance.db (SHA-256 Hash Chain)")]
        DB_Auth[("users.db (Bcrypt Hashed Credentials)")]
    end

    Client --> Middleware
    Middleware --> Core
    Core --> Connectors
    Core --> Storage
```

---

## 6. Technology Stack

### Frontend
- **Framework:** React 19.2, TypeScript 6.0
- **Bundler & Build Tool:** Vite 8.2
- **Styling:** Tailwind CSS v4, Lucide React Icons
- **Data Visualizations:** Chart.js 4.5, React-ChartJS-2, Mermaid.js 11.16
- **Workflow & Diagrams:** @xyflow/react 12.11
- **Exporting & Reporting:** jsPDF, html2canvas, SheetJS (xlsx), FileSaver

### Backend
- **Web Framework:** FastAPI 0.141, Starlette, Uvicorn 0.52
- **ORM & Database Driver:** SQLAlchemy 2.0, PyMySQL 1.1, psycopg2-binary
- **Authentication & Security:** Python-JOSE, Passlib / Bcrypt 5.0, SlowAPI
- **LLM & Inference:** Groq Python SDK (`llama-3.3-70b-versatile`, `openai/gpt-oss-20b`)
- **Data & Configuration:** Pydantic v2, Python-Dotenv, Python-Multipart

---

## 7. Supported Databases & Connectors

| Database Engine | Category | Status | Capabilities Supported |
| :--- | :--- | :---: | :--- |
| **SQLite** | Relational | **Fully Implemented** | Read, Write, Schema Inspection, Record CRUD, Index Management, Table Creation |
| **MySQL** | Relational | **Fully Implemented** | Read, Write, Schema Reflection, Dynamic Records, Index DDL, TLS Checks, Privileges |
| **PostgreSQL** | Relational | **Fully Implemented** | Read, Write, Schema Metadata, Relational CRUD, Index Operations, SSL Verification |
| **MariaDB** | Relational | **Fully Implemented** | Drop-in MySQL protocol support, CRUD, Schema Reflection |
| **SQL Server (MSSQL)** | Relational | **Fully Implemented** | PyODBC / SQLAlchemy MSSQL connector, Schema Metadata, Bounded Queries |
| **MongoDB** | Document | **Fully Implemented** | PyMongo connector, Collection Browsing, Document CRUD, Document Count Summaries |
| **Redis** | Key-Value | **Fully Implemented** | In-memory key listing, Key-value CRUD, TTL telemetry, Hash inspection |
| **Qdrant** | Vector AI | **Fully Implemented** | Collection listing, Vector payload inspection, Dimension metadata |
| **Chroma DB** | Vector AI | **Fully Implemented** | Collection discovery, Embedding counts, Metadata retrieval |
| **CSV / Excel / JSON** | Flat Files | **Fully Implemented** | Upload to in-memory/file SQL table, Dynamic SQL querying, Export |

---

## 8. Project Directory Structure

```text
BG_AI/
├── backend/
│   ├── app/
│   │   ├── agent/                 # Conversational orchestrator & Groq LLM client
│   │   ├── agents/                # Autonomous specialist agents & Action Agent
│   │   ├── connectors/            # Multi-database connector registry & implementations
│   │   │   ├── base.py            # BaseConnector abstract interface
│   │   │   ├── relational.py      # SQLite, MySQL, Postgres, MSSQL, MariaDB
│   │   │   ├── mongodb.py         # MongoDB document connector
│   │   │   ├── redis_connector.py # Redis key-value connector
│   │   │   ├── vector.py          # Qdrant & Chroma vector connectors
│   │   │   ├── file_connectors.py # CSV, Excel, JSON connectors
│   │   │   └── registry.py        # Centralized ConnectionRegistry
│   │   ├── crud/                  # Dynamic CRUD service & Intent detection
│   │   ├── database/              # ContextVars engine isolation & backup services
│   │   ├── intelligence/          # Analytics, anomaly detection, forecasting, governance
│   │   │   └── governance/        # Tamper-evident hash chain & audit store
│   │   ├── security/              # Auth, posture scanner & IP intrusion intelligence
│   │   │   ├── auth.py            # JWT token encoding & decoding
│   │   │   ├── sessions.py        # User authentication & password hashing
│   │   │   ├── posture_scanner.py # Sensitive data scanner & posture score engine
│   │   │   └── ip_intelligence.py # IP threat detection & temporary quarantine
│   │   ├── tools/                 # SQL validation, schema extraction, chart generation
│   │   ├── main.py                # FastAPI route registration & middleware
│   │   └── config.py              # Environment configuration & Groq model bindings
│   ├── requirements.txt           # Python backend dependencies
│   └── scratch/                   # Automated unit & integration verification test suites
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/              # AI Command conversation interface & modals
│   │   │   ├── ui/                # UI widgets & BG AI ModelSelector
│   │   │   └── workspace/         # Main workspace layout, headers, views
│   │   │       └── views/         # 11 Dedicated functional views
│   │   ├── services/
│   │   │   └── api.ts             # Typed REST API client methods
│   │   ├── types/
│   │   │   └── index.ts           # Shared TypeScript interfaces & types
│   │   ├── pages/
│   │   │   └── Home.tsx           # Primary workspace application container
│   │   └── main.tsx               # React application entrypoint
│   ├── package.json               # Frontend dependencies & build scripts
│   ├── vite.config.ts             # Vite build & proxy configuration
│   └── tailwind.config.js         # Tailwind CSS styling configuration
└── README.md                      # Complete system documentation
```

---

## 9. Prerequisites

Before setting up BG AI locally, ensure the following software is installed:

- **Python:** Version `3.11` or higher
- **Node.js:** Version `18.0.0` or higher (Node 20+ recommended)
- **Package Manager:** `npm` (bundled with Node.js)
- **Operating System:** Windows 10/11, macOS, or Linux
- **Git:** Version `2.30` or higher
- **Groq API Key:** Required for natural-language SQL generation and AI agent reasoning (free tier available at [groq.com](https://console.groq.com/)).

---

## 10. Installation & Local Setup

### Step 1: Clone the Repository

Open Windows PowerShell or your terminal and clone the repository:

```powershell
git clone https://github.com/boopathiravi03/BG_chatbox.git
cd BG_chatbox
```

### Step 2: Configure the Backend Environment

Navigate to the `backend` directory and create a virtual environment:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
pip install -r requirements.txt
```

Create a `.env` file in `backend/.env`:

```ini
# Groq Inference Credentials
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# JWT Authentication Secret
JWT_SECRET_KEY=generate_a_secure_random_secret_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Optional Reverse Proxy & Intrusion Settings
BGAI_TRUSTED_PROXIES=127.0.0.1,10.0.0.0/8
BGAI_TEMP_BLOCK_DURATION=900
```

### Step 3: Configure the Frontend Environment

Open a separate terminal window, navigate to the `frontend` directory, and install packages:

```powershell
cd frontend
npm install
```

Create a `.env` file in `frontend/.env`:

```ini
# Base URL for the FastAPI Backend
VITE_API_BASE=http://localhost:8001
```

---

## 11. Environment Variables

| Variable Name | Required | Default Value | Description |
| :--- | :---: | :--- | :--- |
| `GROQ_API_KEY` | **Yes** | *None* | Authentication token for Groq LLM inference |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | LLM model identifier for SQL translation |
| `JWT_SECRET_KEY` | **Yes** | *None* | Cryptographic salt used for signing access JWT tokens |
| `JWT_ALGORITHM` | No | `HS256` | Token signing algorithm |
| `BGAI_EXTRA_ORIGINS` | No | `http://localhost:5173,...` | Comma-separated CORS allowed origin URLs |
| `BGAI_TRUSTED_PROXIES` | No | *Empty (Untrusted)* | Whitelisted reverse-proxy IP addresses or CIDRs |
| `BGAI_AUTH_FAILURE_THRESHOLD`| No | `5` | Failed logins before brute-force alert is raised |
| `BGAI_TEMP_BLOCK_DURATION` | No | `900` | Duration (seconds) of automated IP quarantine blocks |
| `VITE_API_BASE` | No | `http://localhost:8001` | Frontend target URL for backend API requests |

---

## 12. Running BG AI Locally

### 1. Launch the Backend Server

From the `backend` directory with the virtual environment activated:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

- **Backend Address:** `http://127.0.0.1:8001`
- **Swagger Documentation:** `http://127.0.0.1:8001/docs`
- **ReDoc Documentation:** `http://127.0.0.1:8001/redoc`

### 2. Launch the Frontend Development Server

From the `frontend` directory:

```powershell
npm run dev
```

- **Frontend Address:** `http://localhost:5173`

Open your browser to `http://localhost:5173`, create a user account via the registration modal, and connect your database or use the built-in SQLite sample database.

---

## 13. Core API Endpoints

### 🔐 Authentication (`/auth`)
- `POST /auth/register` — Register a new account with bcrypt password hashing.
- `POST /auth/login` — Authenticate credentials and receive Bearer JWT.
- `GET /auth/me` — Retrieve verified profile of current authenticated user.

### 💬 Conversational Intelligence & SQL (`/`)
- `POST /chat` — Translate natural language into executed query results with schema suggestions.
- `POST /query` — Execute validated SQL query on active user connection.
- `POST /confirm-query` — Confirm execution of pending data mutations (`INSERT`/`UPDATE`/`DELETE`).
- `GET /schema` — Retrieve complete schema metadata (tables, columns, types).
- `GET /dashboard` — Retrieve live table counts, row counts, and summary statistics.

### 🔌 Multi-Database Connections (`/connections`)
- `GET /connections/catalog` — List supported database connector catalog.
- `GET /connections` — List all registered connectors for active user.
- `POST /connections` — Register and connect a new database source.
- `POST /connections/switch` — Switch active workspace database connection.
- `DELETE /connections/{connection_id}` — Safely disconnect and remove database connection.

### 🤖 Autonomous Agents (`/agents`)
- `GET /agents` — List available specialist AI agents.
- `POST /agents/run` — Run an autonomous task through intent-routed specialist agent.
- `GET /agent-actions` — List proposed mutation plans requiring confirmation.
- `POST /agent-actions/{action_id}/confirm` — Execute confirmed mutation plan within database transaction.
- `POST /agent-actions/{action_id}/cancel` — Cancel proposed mutation plan.

### 🛡️ Cybersecurity & IP Threat Center (`/security`)
- `POST /security/scan` — Run bounded, read-only cybersecurity posture scan on active connection.
- `POST /security/explain` — Generate AI advisory explaining vulnerability risks with zero raw secret leaks.
- `GET /security/ip-threats` — List recorded intrusion events, brute-force detections, and active blocks.
- `POST /security/ip-threats/reputation` — Query behavioral IP reputation profile.
- `POST /security/ip-threats/unblock` — Administratively lift an active temporary IP quarantine.

### 📜 Enterprise Governance & Audit (`/intelligence/governance`)
- `GET /intelligence/governance/audit` — Retrieve immutable audit ledger entries.
- `POST /intelligence/governance/audit/verify` — Cryptographically verify SHA-256 hash chain integrity.
- `GET /intelligence/governance/policies` — List operational guardrail policies.
- `POST /intelligence/governance/policies/status` — Enable or disable configurable guardrails.

---

## 14. Database Connection & Lifecycle

BG AI supports connecting to existing databases via the **Data Sources** or **Database Modal**:

1. **Local & File Databases:** Upload a `.sqlite`, `.db`, `.csv`, `.xlsx`, or `.json` file. The backend reads schema metadata dynamically without copying external credentials.
2. **Network Databases (MySQL, PostgreSQL, MSSQL, MongoDB, Redis):** Provide connection credentials (host, port, database name, username, password).
3. **Password Masking:** Connection credentials are sanitized immediately upon registration. Raw passwords and secrets are **never returned by the API** (`hide_password=True`) and are omitted from serialized state.
4. **Context Isolation:** Active connections are isolated per user via Python `ContextVar`, preventing cross-tenant bleed or concurrent query collisions.

---

## 15. Security, Governance & Intrusion Safeguards

BG AI employs defense-in-depth security controls:

- **Strict SQL Safety Gate (`validate_sql`):**
  - Unconditionally blocks destructive DDL (`DROP TABLE`, `TRUNCATE TABLE`, `ALTER TABLE`).
  - Prohibits stacked multi-statement injection attacks (`;`).
  - Enforces mandatory `WHERE` clause presence on `UPDATE` and `DELETE` queries.
  - Requires human confirmation before applying single-table mutations.
- **Trusted-Proxy Header Verification:** Client IP extraction verifies `X-Forwarded-For` and `X-Real-IP` only when the direct peer socket matches an entry in `BGAI_TRUSTED_PROXIES`.
- **Intrusion Detection:**
  - Automated detection of brute-force authentication attacks and path crawlers.
  - Temporary quarantine blocks with automatic expiration and administrative unblock overrides.
- **Sensitive Data Redaction:** Bounded posture scanning (`MAX_SAMPLE_ROWS = 50`, `MAX_TABLES_TO_SCAN = 15`) uses conservative regular expressions and Luhn checksum validation to detect unmasked payment cards, plain passwords, and tokens without logging or storing raw sensitive data.
- **Tamper-Evident SHA-256 Audit Chain:** Every governance and security action generates a cryptographic link `Hash(Event + PrevHash)`, verifying log immutability on demand.

---

## 16. Testing & Quality Assurance

All features in BG AI are verified by automated backend test suites and strict frontend TypeScript builds.

### Run Verification Test Suites (PowerShell)

Activate the backend virtual environment and execute the test scripts:

```powershell
cd backend

# 1. IP Threat Intelligence & Intrusion Detection (11/11 PASS)
python scratch/test_ip_intelligence.py

# 2. Database Cybersecurity & Sensitive Data Scanner (13/13 PASS)
python scratch/test_cybersecurity_phase1.py

# 3. Autonomous Specialist Agents & Routing (32/32 PASS)
python scratch/test_phase5_agents.py

# 4. Overview & Database Statistics Synchronization (3/3 PASS)
python scratch/test_overview_sync_stats.py

# 5. Anomaly Center & Metric Evaluator Synchronization (3/3 PASS)
python scratch/test_anomaly_overview_sync.py

# 6. Database Read/Write & Connector Capabilities (14/14 PASS)
python scratch/test_read_write_capabilities.py
```

### Run Frontend Production Build

From the `frontend` directory, verify TypeScript compilation and bundle generation:

```powershell
cd frontend
npm run build
```

*Expected output: Clean production build with 0 TypeScript errors.*

---

## 17. Windows Desktop Application (Electron + PyInstaller)

BG AI provides a standalone, installable Windows desktop application that packages the full web workspace together with an autonomous local Python FastAPI backend server.

### Architecture Overview

```text
┌────────────────────────────────────────────────────────┐
│                   Windows Host OS                      │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │             Electron Desktop Shell               │  │
│  │                                                  │  │
│  │  ┌─────────────────────┐   ┌──────────────────┐  │  │
│  │  │   Vite + React 19   │   │  Preload Bridge  │  │  │
│  │  │   Frontend UI       │◄──┤  (IPC / Context  │  │  │
│  │  │   (Renderer)        │   │   Isolation)     │  │  │
│  │  └──────────┬──────────┘   └─────────▲────────┘  │  │
│  └─────────────┼────────────────────────┼───────────┘  │
│                │ REST / WebSocket       │ Lifecycle    │
│                ▼                        │ Monitoring   │
│  ┌──────────────────────────────────────┴───────────┐  │
│  │        Bundled Python FastAPI Server             │  │
│  │        (bgai_backend.exe via PyInstaller)        │  │
│  │                                                  │  │
│  │  • Embedded Python 3.11 Runtime (No host Python) │  │
│  │  • SQLAlchemy 2.0 / Relational & NoSQL Drivers   │  │
│  │  • Dynamic Port Hunting (8001 -> 8010 fallback)  │  │
│  │  • Parent-PID Heartbeat (Orphan process defense) │  │
│  └──────────────────────┬───────────────────────────┘  │
│                         │ File I/O                     │
│                         ▼                              │
│       ┌───────────────────────────────────┐            │
│       │   %APPDATA%\BG_AI                 │            │
│       │   • bgai_users.db                 │            │
│       │   • bgai_audit.db                 │            │
│       │   • bgai_guardian.db              │            │
│       │   • desktop_backend.log           │            │
│       │   • .env (Local API Keys)         │            │
│       └───────────────────────────────────┘            │
└────────────────────────────────────────────────────────┘
```

### Key Desktop Features & Safeguards

1. **Zero Runtime Prerequisites:**
   - The desktop installer packages an embedded Python 3.11 environment alongside all SQL drivers (PyMySQL, psycopg2, SQLite) and native modules using PyInstaller.
   - Target machines **do not** require Python, Node.js, or Git installed globally.
2. **Per-User AppData Architecture (`%APPDATA%\BG_AI`):**
   - Windows installations inside `C:\Program Files\BG AI\` are read-only for standard users.
   - All stateful SQLite stores (`bgai_users.db`, `bgai_audit.db`, `bgai_guardian.db`, etc.) and log files are routed to `%APPDATA%\BG_AI`, preventing permission errors and preserving user data across application updates.
3. **Dynamic Port Allocation & Conflict Avoidance:**
   - When Electron launches, it probes ports starting from `8001` through `8010` to find an open socket.
   - It transmits the assigned port to the backend process via `--port` and `BGAI_PORT`, and passes the backend address dynamically to the React frontend through `window.electronAPI.getBackendUrl()`.
4. **Strict Context Isolation & Process Security:**
   - Renderer runs with `nodeIntegration: false` and `contextIsolation: true`.
   - All desktop integrations (`openExternal`, `showItemInFolder`, `openAppDataFolder`) are mediated through a secure, validated preload bridge (`electron/preload.js`).
   - External web navigation inside the application window is strictly blocked and delegated to the user's default OS browser.
5. **Clean Shutdown & Orphan Process Defense:**
   - The bundled backend process actively monitors its parent Electron process ID (`--parent-pid`). If Electron terminates, Python shuts down immediately.
   - On application exit, Electron dispatches a graceful SIGTERM followed by a forced process-tree termination (`taskkill /F /T /PID`) to guarantee no orphan background processes linger.
6. **Built-in Splash Screen & Diagnostic Recovery:**
   - A dedicated native HTML/CSS splash screen displays real-time backend startup steps and health checks (`GET /health`).
   - If startup encounters a missing dependency or locked port, actionable diagnostic logs and an "Open Logs" button are provided directly in the interface.

---

### Desktop Development Workflow

To run the desktop application locally with live development servers:

```powershell
# From the project root:
npm start
```

*Note: In development mode, Electron connects to `http://localhost:5173` if Vite is running, or automatically launches `backend/desktop_server.py` and opens the local React build.*

---

### Building the Windows Installer (`.exe`)

BG AI features a single unified build pipeline that compiles the React bundle, packages the Python backend via PyInstaller, and bundles everything into an NSIS installer using `electron-builder`:

```powershell
# Run the complete automated desktop build:
npm run build
```

This single command performs the following sequence:
1. `npm run build:frontend` — Compiles the React + TypeScript frontend into `frontend/dist/`.
2. `npm run build:backend` — Invokes PyInstaller (`backend/bgai_backend.spec`) to produce the standalone binary directory `backend/dist/bgai_backend/`.
3. `npm run dist` — Packages the installer via Electron Builder into:
   - **Standalone Installer:** `dist/BG AI Setup 1.0.0.exe` (~124 MB)
   - **Unpacked Portable Directory:** `dist/win-unpacked/BG AI.exe`

#### To Build Components Individually:

```powershell
# Build frontend only:
npm run build:frontend

# Build backend standalone executable only:
npm run build:backend

# Package without re-compiling backend (quick test):
npm run dist
```

---

### Installation & Updating

1. **Installation:** Run `BG AI Setup 1.0.0.exe`. The NSIS installer allows choosing an installation directory (default: `%LOCALAPPDATA%\Programs\BG AI` or `C:\Program Files\BG AI`) and creates Desktop and Start Menu shortcuts.
2. **Upgrading:** Running a newer version of the installer updates the binary files while preserving all databases, connection configs, and credentials located in `%APPDATA%\BG_AI`.
3. **Uninstalling:** Standard Windows Add/Remove Programs uninstaller removes the application binaries while safely keeping user application data intact.

---

### Desktop Configuration & API Keys

- **Groq API Key:** The desktop version loads configuration from `%APPDATA%\BG_AI\.env` if present, or from system environment variables. You can enter or update your Groq API key directly within the app settings or by editing:
  ```text
  %APPDATA%\BG_AI\.env
  ```
  Example contents:
  ```ini
  GROQ_API_KEY=gsk_your_groq_api_key_here
  GROQ_MODEL=llama-3.3-70b-versatile
  ```

---

### Code Signing Notice

The generated installer `BG AI Setup 1.0.0.exe` is unsigned (self-packaged for local/enterprise distribution). When installing on Windows 10 or 11, Windows SmartScreen may display an unknown publisher alert:
- Click **More info** -> **Run anyway**.
- For enterprise deployments, sign the output executable using `signtool.exe` with a valid Authenticode Code Signing Certificate.

---

## 18. Cloud Deployment Architecture

BG AI is structured for cloud deployment across separate frontend and backend tiers:

- **Frontend Deployment (Client Tier):** Static single-page application built with Vite and hosted on CDN infrastructure serving [https://thebg.co.in/](https://thebg.co.in/).
- **Backend Deployment (API Tier):** Python FastAPI application hosted on Render at [https://bg-chatbox.onrender.com](https://bg-chatbox.onrender.com).
- **CORS & CSP Configuration:** Backend explicitly permits requests from `https://thebg.co.in` and local development origins with strict Content-Security-Policy headers.

---

## 19. Troubleshooting Guide

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| `HTTP 401 Unauthorized` | Missing or expired JWT access token | Log in via the account modal or submit credentials to `POST /auth/login`. |
| `HTTP 403 Forbidden: Access Denied` | Source IP is under temporary quarantine | Review active blocks in Cybersecurity -> IP Threats, or call `POST /security/ip-threats/unblock`. |
| `Connection refused: localhost:8001` | Backend FastAPI server is not running | Start backend with `uvicorn app.main:app --port 8001 --reload` in `backend/`. |
| `PyMySQL / psycopg2 missing` | Database drivers not installed in virtualenv | Run `pip install -r requirements.txt` inside the activated virtual environment. |
| `Groq API Key Error / Invalid Key` | `GROQ_API_KEY` missing in `.env` | Set a valid `GROQ_API_KEY` in `backend/.env` (web mode) or `%APPDATA%\BG_AI\.env` (desktop mode). |
| `Vite build fails on TypeScript` | Outdated dependencies or missing node modules | Run `npm install` followed by `npm run build` in `frontend/`. |
| `Desktop Splash: Backend failed to start` | Port in use or firewall blocking loopback | Inspect `%APPDATA%\BG_AI\desktop_backend.log` for exact startup error. Ensure ports 8001-8010 are accessible. |
| `Windows SmartScreen Warning` | Unsigned installer executable | Click "More info" -> "Run anyway", or sign the `.exe` with an Authenticode certificate. |

---

## 20. Product Roadmap

The following capabilities are actively planned for future releases:

- [ ] **Multi-Region Audit Ledger Replication:** Cross-region consensus replication for tamper-evident audit logs.
- [ ] **Asynchronous Background Task Workers:** Celery / Redis queue worker for large-scale enterprise database profiling.
- [ ] **Custom Enterprise SSO Providers:** SAML 2.0 and OIDC integrations for enterprise identity providers.
- [ ] **Role-Based Fine-Grained Permissions (RBAC):** Column-level and row-level masking policies per user role.

---

## 21. Contributing

Contributions to BG AI are welcome. To contribute:

1. **Fork the Repository:** Create your own branch (`git checkout -b feature/your-feature-name`).
2. **Follow Coding Standards:** Adhere to PEP 8 standards for Python and ESLint/TypeScript guidelines for the frontend.
3. **Execute Test Suites:** Ensure all tests pass (`python scratch/test_ip_intelligence.py`, `npm run build`).
4. **Submit a Pull Request:** Provide a clear description of the fix or feature.

---

## 22. License

This repository does not currently specify an open-source license. All rights are reserved by the original project authors. For permissions or licensing inquiries, please contact the maintainers.

---

## 23. Acknowledgements & Authors

- **Developed By:** [Boopathi Ravi](https://github.com/boopathiravi03)
- **Project Repository:** [boopathiravi03/BG_chatbox](https://github.com/boopathiravi03/BG_chatbox)
- **Official Website:** [https://thebg.co.in/](https://thebg.co.in/)
