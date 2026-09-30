#!/usr/bin/env python
"""
Manual Real-Database Test for Phase 5 Specialist Agents
BG AI — AI Data Intelligence Platform

Tests against the real database A:/bgai1/BG_AI/database/ecommerce.db:
  A. Database health request
  B. Data quality request
  C. Analyst request
  D. Anomaly request
  E. Performance request
  F. Safe update request (PREVIEW -> CONFIRM -> EXECUTE -> VERIFY)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.database_manager import connect_sqlite, get_engine, disconnect_database
from app.database.database_context import refresh_database_profile
from app.agents.registry import run_agent_task, route_to_agent
from app.agents.audit import get_action, confirm_and_execute_action, list_actions

REAL_DB_PATH = "A:/bgai1/BG_AI/database/ecommerce.db"
assert os.path.exists(REAL_DB_PATH), f"Real DB file not found: {REAL_DB_PATH}"

print(f"Connecting to real database: {REAL_DB_PATH}")
connect_sqlite(REAL_DB_PATH)
profile = refresh_database_profile()
print(f"Connected! Tables: {list(profile.tables.keys()) if profile else 'none'}")

print("\n" + "=" * 60)
print("TEST A: Database Health Request")
print("=" * 60)
prompt_a = "Is my database healthy?"
routed_a = route_to_agent(prompt_a)
print(f"Prompt: '{prompt_a}' -> Routed to: {routed_a}")
res_a = run_agent_task(prompt_a)
print(f"Agent: {res_a.agent_name} | Status: {res_a.status}")
print(f"Summary: {res_a.summary}")
print(f"Findings ({len(res_a.findings)}): {[f.title for f in res_a.findings[:3]]}")
assert res_a.status == "COMPLETED"
assert len(res_a.summary) > 0

print("\n" + "=" * 60)
print("TEST B: Data Quality Request")
print("=" * 60)
prompt_b = "Which columns have too many null values?"
routed_b = route_to_agent(prompt_b)
print(f"Prompt: '{prompt_b}' -> Routed to: {routed_b}")
res_b = run_agent_task(prompt_b)
print(f"Agent: {res_b.agent_name} | Status: {res_b.status}")
print(f"Summary: {res_b.summary}")
print(f"Evidence: {res_b.evidence}")
assert res_b.status == "COMPLETED"

print("\n" + "=" * 60)
print("TEST C: Analyst Request")
print("=" * 60)
prompt_c = "Show me monthly sales growth"
routed_c = route_to_agent(prompt_c)
print(f"Prompt: '{prompt_c}' -> Routed to: {routed_c}")
res_c = run_agent_task(prompt_c)
print(f"Agent: {res_c.agent_name} | Status: {res_c.status}")
print(f"Summary: {res_c.summary}")
assert res_c.status == "COMPLETED"

print("\n" + "=" * 60)
print("TEST D: Anomaly Request")
print("=" * 60)
prompt_d = "Are there unusual values or outliers in my data?"
routed_d = route_to_agent(prompt_d)
print(f"Prompt: '{prompt_d}' -> Routed to: {routed_d}")
res_d = run_agent_task(prompt_d)
print(f"Agent: {res_d.agent_name} | Status: {res_d.status}")
print(f"Summary: {res_d.summary}")
print(f"Anomalies detected: {res_d.evidence.get('total_anomalies', 0)}")
assert res_d.status == "COMPLETED"

print("\n" + "=" * 60)
print("TEST E: Performance Request")
print("=" * 60)
prompt_e = "Which tables need indexes?"
routed_e = route_to_agent(prompt_e)
print(f"Prompt: '{prompt_e}' -> Routed to: {routed_e}")
res_e = run_agent_task(prompt_e)
print(f"Agent: {res_e.agent_name} | Status: {res_e.status}")
print(f"Summary: {res_e.summary}")
print(f"Findings: {[f.title for f in res_e.findings[:3]]}")
assert res_e.status == "COMPLETED"

print("\n" + "=" * 60)
print("TEST F: Safe Update Request (PREVIEW -> CONFIRM -> EXECUTE -> VERIFY)")
print("=" * 60)

# Check customer #1 current name first
import sqlite3
raw_conn = sqlite3.connect(REAL_DB_PATH)
c1 = raw_conn.execute("SELECT customer_id, name, email FROM customers WHERE customer_id = 1").fetchone()
print(f"Original Record (customer_id=1): {c1}")
raw_conn.close()

prompt_f = "Update customers set name = 'Rahul Sharma' where customer_id = 1"
routed_f = route_to_agent(prompt_f)
print(f"Prompt: '{prompt_f}' -> Routed to: {routed_f}")
res_f = run_agent_task(prompt_f)

print(f"\n[STEP 1: PREVIEW]")
print(f"Agent: {res_f.agent_name} | Status: {res_f.status}")
print(f"Summary: {res_f.summary}")
assert res_f.status == "ACTION_REQUIRED", f"Expected ACTION_REQUIRED, got {res_f.status}"
assert res_f.proposed_action is not None, "Proposed action must be generated"

action = res_f.proposed_action
print(f"Action ID: {action.action_id}")
print(f"Action Type: {action.action_type}")
print(f"Target Table: {action.table}")
print(f"Exact SQL: {action.exact_sql}")
print(f"Verification SQL: {action.verification_sql}")
print(f"Estimated Affected Rows: {action.estimated_rows}")
print(f"Risk Level: {action.risk_level}")
print(f"Status before confirmation: {action.status}")
assert action.status == "AWAITING_CONFIRMATION"
assert action.estimated_rows == 1

print(f"\n[STEP 2 & 3: CONFIRM & EXECUTE inside transaction]")
exec_res = confirm_and_execute_action(action.action_id)
print(f"Execution Result: {exec_res}")
assert exec_res["success"] is True, f"Execution failed: {exec_res.get('error')}"
assert exec_res["actual_rows_affected"] == 1

print(f"\n[STEP 4: VERIFY]")
verified_action = get_action(action.action_id)
print(f"Action Status after execution: {verified_action.status}")
print(f"Actual Rows Affected: {verified_action.actual_rows_affected}")
print(f"Verification Details: {verified_action.verification_details}")
assert verified_action.status in {"VERIFIED", "EXECUTED"}

# Verify on database
raw_conn2 = sqlite3.connect(REAL_DB_PATH)
c1_after = raw_conn2.execute("SELECT customer_id, name, email FROM customers WHERE customer_id = 1").fetchone()
print(f"Updated Record in Database: {c1_after}")
assert c1_after[1] == "Rahul Sharma"

# Restore original name if desired
if c1:
    raw_conn2.execute(f"UPDATE customers SET name = ? WHERE customer_id = 1", (c1[1],))
    raw_conn2.commit()
    print(f"Restored original name '{c1[1]}' to preserve database integrity.")
raw_conn2.close()

print(f"\n[STEP 5: AUDIT LOG]")
all_audit = list_actions(db_identity_only=False)
print(f"Total audit entries: {len(all_audit)}")
our_entry = next((a for a in all_audit if a.action_id == action.action_id), None)
assert our_entry is not None, "Action must be in audit log"
print(f"Audit record: id={our_entry.action_id}, table={our_entry.table}, type={our_entry.action_type}, status={our_entry.status}, rows={our_entry.actual_rows_affected}")

print("\n" + "=" * 60)
print("ALL REAL DATABASE CHECKS (A-F) PASSED PERFECTLY!")
print("=" * 60)
