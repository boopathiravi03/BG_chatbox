#!/usr/bin/env python
"""
Baseline Profiling Script for BG AI Insert / CRUD Pipeline
Measures each stage of the lifecycle:
1. Schema retrieval
2. Intent detection (LLM vs Deterministic)
3. Form generation / Planning
4. Form submission & Confirmation preparation
5. Execution of confirmed operation
6. Post-execution profile refresh
"""
import sys
import os
import time
import tempfile
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.database_manager import connect_sqlite, disconnect_database
from app.tools.get_schema import get_schema
from app.crud.intent import parse_crud_intent
from app.crud.deterministic import build_deterministic_intent
from app.crud.router import handle_crud_request
from app.crud.service import execute_confirmed
from app.agent.orchestrator import run_agent, conversation_state
from app.database.database_context import refresh_database_profile


def setup_test_db():
    temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = temp_file.name
    temp_file.close()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Create several tables to simulate realistic database
    cur.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            city TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    """)
    cur.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 0
        )
    """)
    # Seed sample rows
    for i in range(100):
        cur.execute("INSERT INTO customers (name, email, city) VALUES (?, ?, ?)",
                    (f"Customer {i}", f"user{i}@example.com", "City X"))
        cur.execute("INSERT INTO orders (customer_id, amount, status) VALUES (?, ?, ?)",
                    (i + 1, (i + 1) * 15.5, "completed" if i % 2 == 0 else "pending"))
        cur.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
                    (f"Product {i}", (i + 1) * 2.5, i * 10))
    conn.commit()
    conn.close()

    return db_path


def profile_baseline():
    print("=" * 60)
    print("PROFILING CURRENT PIPELINE BEFORE OPTIMIZATION")
    print("=" * 60)

    db_path = setup_test_db()
    connect_sqlite(db_path)
    session_id = "bench_session_1"

    timings = {}

    try:
        # Stage 1: Schema Retrieval
        t0 = time.perf_counter()
        schema = get_schema()
        timings["schema_retrieval_ms"] = (time.perf_counter() - t0) * 1000
        print(f"Stage 1 - Schema Retrieval: {timings['schema_retrieval_ms']:.2f} ms")

        # Stage 2A: Deterministic Intent Detection
        t0 = time.perf_counter()
        det_intent = build_deterministic_intent("Add a new customer", schema)
        timings["deterministic_intent_ms"] = (time.perf_counter() - t0) * 1000
        print(f"Stage 2A - Deterministic Intent Detection: {timings['deterministic_intent_ms']:.2f} ms")

        # Stage 2B: LLM Intent Detection (parse_crud_intent)
        try:
            t0 = time.perf_counter()
            llm_intent = parse_crud_intent("Add a new customer", schema, "sqlite")
            timings["llm_intent_ms"] = (time.perf_counter() - t0) * 1000
            print(f"Stage 2B - LLM Intent Detection (Groq API): {timings['llm_intent_ms']:.2f} ms")
        except Exception as e:
            timings["llm_intent_ms"] = None
            print(f"Stage 2B - LLM Intent Detection: SKIPPED/ERROR ({e})")

        # Stage 3: Initial Request ("Add a new customer") via run_agent
        t0 = time.perf_counter()
        req1_res = run_agent("Add a new customer", session_id=session_id)
        timings["prepare_form_request_ms"] = (time.perf_counter() - t0) * 1000
        print(f"Stage 3 - Prepare Record Form Request (End-to-End): {timings['prepare_form_request_ms']:.2f} ms")

        # Stage 4: Form Submission (values provided -> confirmation response)
        values = {"name": "Test User", "email": "test@example.com", "city": "Metropolis"}
        t0 = time.perf_counter()
        req2_res = run_agent("submit", session_id=session_id, input_values=values, pending_insert=True)
        timings["form_submission_plan_ms"] = (time.perf_counter() - t0) * 1000
        print(f"Stage 4 - Form Submission & Plan Generation: {timings['form_submission_plan_ms']:.2f} ms")

        # Stage 5: Execution of Confirmed Operation (without profile refresh vs with)
        t0 = time.perf_counter()
        conf_res = execute_confirmed(session_id)
        timings["execute_confirmed_total_ms"] = (time.perf_counter() - t0) * 1000
        print(f"Stage 5 - Execute Confirmed (DB Execution + Full Refresh): {timings['execute_confirmed_total_ms']:.2f} ms")

        # Stage 6: Isolated Full Database Profile Refresh
        t0 = time.perf_counter()
        refresh_database_profile()
        timings["isolated_full_profile_refresh_ms"] = (time.perf_counter() - t0) * 1000
        print(f"Stage 6 - Isolated Full DB Profile Refresh (analyze_database): {timings['isolated_full_profile_refresh_ms']:.2f} ms")

        print("\n" + "=" * 60)
        print("BASELINE BOTTLENECK BREAKDOWN:")
        print("=" * 60)
        for k, v in timings.items():
            if v is not None:
                print(f"  {k:38s}: {v:8.2f} ms")
        print("=" * 60)

    finally:
        disconnect_database()
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
        except Exception:
            pass


if __name__ == "__main__":
    profile_baseline()

