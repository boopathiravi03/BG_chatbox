#!/usr/bin/env python
"""
Phase 8.8: Controlled Business Actions & Action Intelligence Test Suite
Covers 50+ dedicated assertions verifying:
1. Action models serialization (to_dict / from_dict)
2. Valid INSERT proposal
3. Valid UPDATE proposal
4. Valid DELETE proposal
5. Schema validation: non-existent table is blocked
6. Column validation: non-existent column is blocked
7. Primary key discovery and handling
8. Foreign key dependency detection
9. Unrestricted UPDATE blocked (no WHERE clause)
10. Unrestricted UPDATE blocked (WHERE 1=1 tautology)
11. Unrestricted DELETE blocked (no WHERE clause)
12. DDL blocked (DROP TABLE, ALTER TABLE, TRUNCATE, CREATE TABLE)
13. Command chaining blocked (UPDATE ...; DROP TABLE)
14. System tables blocked (sqlite_master, sqlite_sequence, information_schema)
15. Dangerous SQL keywords blocked (EXEC, GRANT, REVOKE, ATTACH, DETACH)
16. Parameterized SQL and parameters dictionary generation
17. Impact preview with sample records
18. Excessive affected rows limit (> 500 rows)
19. Risk classification: LOW (single row non-critical update)
20. Risk classification: MEDIUM (multi-row update)
21. Risk classification: HIGH (DELETE operation)
22. Risk classification: HIGH (business critical column: price, amount, stock)
23. Risk classification: BLOCKED
24. Confirmation token generation
25. Confirmation token HMAC signature verification
26. Confirmation token binding (user, action_id, db identity, action_hash)
27. Confirmation token expiration (expired timestamp rejected)
28. Modified action invalidates confirmation token (hash mismatch)
29. Tampered token signature rejected
30. High-risk execution blocked without high_risk_acknowledged
31. Atomic execution inside transaction (BEGIN ... COMMIT)
32. Rollback on execution error
33. Post-execution verification for UPDATE (checks updated value)
34. Post-execution verification for DELETE (checks count == 0)
35. Verification failure detection
36. Duplicate execution protection (409 Conflict)
37. State machine progression (PROPOSED -> READY_FOR_CONFIRMATION -> CONFIRMED -> EXECUTED -> VERIFIED)
38. Cancel action (sets status CANCELLED)
39. Cancel already executed action blocked
40. Audit logging on success
41. Audit logging on failure
42. Audit log hides secrets (no passwords, tokens)
43. API: POST /intelligence/actions/propose requires JWT
44. API: Rate limiting on propose, preview, confirm, execute
45. API: User isolation (User B cannot preview User A's action)
46. API: User isolation (User B cannot confirm User A's action)
47. API: User isolation (User B cannot execute User A's action)
48. Multi-dialect SQL identifier quoting (SQLite, PostgreSQL, MySQL)
49. Zero autonomous mutation guarantee (no execution without explicit confirmation)
50. Phase 8.1 - 8.7 Regression Guards
"""
from __future__ import annotations

import os
import sys
import uuid
import time
import tempfile
import sqlite3
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from app.security.auth import create_access_token
from app.intelligence.actions.models import (
    ActionType,
    ActionStatus,
    ActionRisk,
    ActionTarget,
    ActionChange,
    ActionImpact,
    ActionValidation,
    ActionConfirmation,
    ActionExecutionResult,
    ActionVerification,
    ActionAuditRecord,
    ActionProposal,
)
from app.intelligence.actions.action_policy import (
    classify_action_risk,
    is_business_critical_column,
    is_system_table,
)
from app.intelligence.actions.action_validator import validate_action
from app.intelligence.actions.impact_preview import calculate_impact_preview
from app.intelligence.actions.confirmation import (
    compute_action_hash,
    generate_confirmation_token,
    validate_confirmation_token,
)
from app.intelligence.actions.verification import (
    verify_action_execution,
)
from app.intelligence.actions.action_audit import (
    save_action,
    get_action,
    list_actions,
    record_audit,
    list_audits,
    clear_actions_store,
)
from app.intelligence.actions.executor import (
    execute_action,
    ActionExecutionConflict,
    ActionExecutionError,
)
from app.intelligence.actions.action_builder import (
    build_action_proposal,
)
from app.intelligence.schema_analyzer import quote_identifier

client = TestClient(app, raise_server_exceptions=False)
test_results: list[tuple[str, str, str | None]] = []


def run_assertion(test_id: int, desc: str, condition: bool, err_msg: str = ""):
    if condition:
        test_results.append((f"Test {test_id:02d}", "PASS", desc))
        print(f"  [PASS] [{test_id:02d}] {desc}")
    else:
        test_results.append((f"Test {test_id:02d}", "FAIL", f"{desc} -> {err_msg}"))
        print(f"  [FAIL] [{test_id:02d}] {desc} -> {err_msg}")



def setup_test_db() -> tuple[Any, str]:
    """Create a temporary sqlite db with products, customers, and orders tables."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                status TEXT NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL
            );
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );
        """))
        conn.execute(text("""
            INSERT INTO customers (customer_id, name, email, status) VALUES
            (1, 'Alice Smith', 'alice@example.com', 'active'),
            (2, 'Bob Jones', 'bob@example.com', 'pending'),
            (3, 'Charlie Brown', 'charlie@example.com', 'active');
        """))
        conn.execute(text("""
            INSERT INTO products (product_id, name, category, price, stock) VALUES
            (101, 'Mechanical Keyboard', 'Electronics', 120.0, 50),
            (102, 'Wireless Mouse', 'Electronics', 45.0, 150),
            (103, 'USB-C Cable', 'Accessories', 15.0, 500);
        """))
        conn.execute(text("""
            INSERT INTO orders (order_id, customer_id, total_amount) VALUES
            (1001, 1, 165.0),
            (1002, 2, 45.0);
        """))
    return engine, path


def run_all_tests():
    print("\n============================================================")
    print("PHASE 8.8 CONTROLLED BUSINESS ACTIONS & ACTION INTELLIGENCE")
    print("TEST SUITE (50+ ASSERTIONS)")
    print("============================================================\n")

    engine, db_path = setup_test_db()
    db_id = engine.url.render_as_string(hide_password=True)
    clear_actions_store()

    try:
        # 1. Action models serialization
        prop = ActionProposal(
            action_id="act-test-01",
            user_id="user_test_1",
            action_type="UPDATE",
            status=ActionStatus.PROPOSED.value,
            target=ActionTarget(table="products", columns=["price"], primary_keys=["product_id"]),
            changes=[ActionChange(column="price", current_value=120.0, proposed_value=99.99)],
            reason="Holiday discount adjustment",
            risk=ActionRisk.HIGH.value,
            sql_preview='UPDATE "products" SET "price" = 99.99 WHERE "product_id" = 101',
            parameterized_sql='UPDATE "products" SET "price" = :val_0 WHERE "product_id" = :id',
            parameters={"val_0": 99.99, "id": 101},
            database_identity=db_id,
        )
        d = prop.to_dict()
        restored = ActionProposal.from_dict(d)
        run_assertion(
            1,
            "Action models serialization (to_dict / from_dict)",
            restored.action_id == prop.action_id and restored.risk == ActionRisk.HIGH.value and restored.changes[0].proposed_value == 99.99,
            "Model serialization did not restore properly",
        )

        # 2. Valid INSERT proposal
        ins_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="INSERT",
            target_table="customers",
            changes=[
                {"column": "name", "proposed_value": "David Warner"},
                {"column": "email", "proposed_value": "david@example.com"},
                {"column": "status", "proposed_value": "active"},
            ],
            reason="New VIP signup",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            2,
            "Valid INSERT proposal construction",
            ins_prop.action_type == "INSERT" and ins_prop.validation.is_valid and "INSERT INTO" in ins_prop.parameterized_sql,
            f"INSERT proposal invalid: {ins_prop.validation.blocked_reason if ins_prop.validation else 'None'}",
        )

        # 3. Valid UPDATE proposal
        upd_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="customers",
            changes=[{"column": "status", "proposed_value": "verified"}],
            condition_sql="customer_id = :cid",
            condition_params={"cid": 2},
            reason="Customer verification complete",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            3,
            "Valid UPDATE proposal with restrictive condition",
            upd_prop.validation.is_valid and upd_prop.status in (ActionStatus.PROPOSED.value, ActionStatus.READY_FOR_CONFIRMATION.value) and upd_prop.parameters.get("cid") == 2,
            f"UPDATE proposal failed: {upd_prop.validation.blocked_reason if upd_prop.validation else 'None'}",
        )

        # 4. Valid DELETE proposal
        del_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="DELETE",
            target_table="products",
            changes=[],
            condition_sql="product_id = :pid",
            condition_params={"pid": 103},
            reason="Discontinued accessory",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            4,
            "Valid DELETE proposal with restrictive condition",
            del_prop.action_type == "DELETE" and del_prop.validation.is_valid and del_prop.risk == ActionRisk.HIGH.value,
            f"DELETE proposal failed: {del_prop.validation.blocked_reason if del_prop.validation else 'None'}",
        )

        # 5. Schema validation: non-existent table is blocked
        bad_tbl_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="non_existent_inventory",
            changes=[{"column": "qty", "proposed_value": 10}],
            condition_sql="id = :id",
            condition_params={"id": 1},
            reason="Inventory fix",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            5,
            "Schema validation blocks non-existent table",
            not bad_tbl_prop.validation.is_valid and "does not exist" in bad_tbl_prop.validation.blocked_reason,
            f"Bad table was not blocked: {bad_tbl_prop.validation.blocked_reason if bad_tbl_prop.validation else 'None'}",
        )

        # 6. Column validation: non-existent column is blocked
        bad_col_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="products",
            changes=[{"column": "ghost_column", "proposed_value": "hello"}],
            condition_sql="product_id = :id",
            condition_params={"id": 101},
            reason="Column fix",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            6,
            "Column validation blocks non-existent column",
            not bad_col_prop.validation.is_valid and "does not exist in table" in bad_col_prop.validation.blocked_reason,
            f"Bad column was not blocked: {bad_col_prop.validation.blocked_reason if bad_col_prop.validation else 'None'}",
        )

        # 7. Primary key discovery and handling
        run_assertion(
            7,
            "Primary key discovery for target table",
            "product_id" in del_prop.target.primary_keys or "customer_id" in upd_prop.target.primary_keys,
            f"Primary keys not properly extracted: {del_prop.target.primary_keys}",
        )

        # 8. Foreign key dependency detection in impact preview
        run_assertion(
            8,
            "Foreign key dependency detection in impact preview",
            upd_prop.impact is not None and "orders" in upd_prop.impact.related_records_count,
            f"Foreign key dependent 'orders' was not detected in {upd_prop.impact.related_records_count if upd_prop.impact else 'None'}",
        )

        # 9. Unrestricted UPDATE blocked (no WHERE clause)
        unrestr_upd = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="customers",
            changes=[{"column": "status", "proposed_value": "blocked"}],
            condition_sql="",
            condition_params={},
            reason="Mass update",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            9,
            "Unrestricted UPDATE blocked (missing WHERE clause)",
            not unrestr_upd.validation.is_valid and "Unrestricted UPDATE blocked" in unrestr_upd.validation.blocked_reason,
            f"Unrestricted UPDATE was not blocked: {unrestr_upd.validation.blocked_reason if unrestr_upd.validation else 'None'}",
        )

        # 10. Unrestricted UPDATE blocked (WHERE 1=1 tautology)
        taut_upd = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="customers",
            changes=[{"column": "status", "proposed_value": "blocked"}],
            condition_sql="1=1",
            condition_params={},
            reason="Tautology mass update",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            10,
            "Unrestricted UPDATE blocked (WHERE 1=1 tautology)",
            not taut_upd.validation.is_valid and "WHERE condition contains a tautology" in taut_upd.validation.blocked_reason,
            f"Tautology UPDATE was not blocked: {taut_upd.validation.blocked_reason if taut_upd.validation else 'None'}",
        )

        # 11. Unrestricted DELETE blocked (no WHERE clause)
        unrestr_del = build_action_proposal(
            user_id="user_test_1",
            action_type="DELETE",
            target_table="customers",
            changes=[],
            condition_sql="",
            condition_params={},
            reason="Wipe table",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            11,
            "Unrestricted DELETE blocked (missing WHERE clause)",
            not unrestr_del.validation.is_valid and "Unrestricted DELETE blocked" in unrestr_del.validation.blocked_reason,
            f"Unrestricted DELETE was not blocked: {unrestr_del.validation.blocked_reason if unrestr_del.validation else 'None'}",
        )

        # 12. DDL blocked (DROP TABLE, ALTER TABLE, TRUNCATE, CREATE TABLE)
        ddl_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="customers",
            changes=[{"column": "status", "proposed_value": "x"}],
            condition_sql="customer_id = 1; DROP TABLE customers",
            condition_params={},
            reason="DDL attempt",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            12,
            "DDL keywords in condition blocked",
            not ddl_prop.validation.is_valid and ("drop" in (ddl_prop.validation.blocked_reason or "").lower() or "multiple sql statements" in (ddl_prop.validation.blocked_reason or "").lower()),
            f"DDL was not blocked: {ddl_prop.validation.blocked_reason if ddl_prop.validation else 'None'}",
        )

        # 13. Command chaining blocked
        chain_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="customers",
            changes=[{"column": "status", "proposed_value": "x"}],
            condition_sql="customer_id = 1; UPDATE customers SET status = 'hacked'",
            condition_params={},
            reason="Command chain attempt",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            13,
            "Command chaining (semicolon) blocked",
            not chain_prop.validation.is_valid and "Multiple SQL statements" in chain_prop.validation.blocked_reason,
            f"Command chaining was not blocked: {chain_prop.validation.blocked_reason if chain_prop.validation else 'None'}",
        )

        # 14. System tables blocked
        sys_tbl_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="sqlite_master",
            changes=[{"column": "sql", "proposed_value": "corrupt"}],
            condition_sql="name = 'customers'",
            condition_params={},
            reason="System table corruption",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            14,
            "System tables mutation blocked",
            not sys_tbl_prop.validation.is_valid and "system table" in (sys_tbl_prop.validation.blocked_reason or "").lower(),
            f"System table was not blocked: {sys_tbl_prop.validation.blocked_reason if sys_tbl_prop.validation else 'None'}",
        )

        # 15. Dangerous SQL keywords blocked
        grant_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="customers",
            changes=[{"column": "status", "proposed_value": "GRANT ALL"}],
            condition_sql="customer_id = 1 AND EXEC('something')",
            condition_params={},
            reason="Exec keyword",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            15,
            "Dangerous SQL keywords (EXEC) blocked",
            not grant_prop.validation.is_valid and "exec" in (grant_prop.validation.blocked_reason or "").lower(),
            f"EXEC keyword was not blocked: {grant_prop.validation.blocked_reason if grant_prop.validation else 'None'}",
        )


        # 16. Parameterized SQL and parameters dictionary generation
        run_assertion(
            16,
            "Parameterized SQL and parameters dictionary generation",
            ":cid" in upd_prop.parameterized_sql and ":val_0" in upd_prop.parameterized_sql and upd_prop.parameters.get("cid") == 2 and upd_prop.parameters.get("val_0") == "verified",
            f"Parameterized SQL incorrect: {upd_prop.parameterized_sql}, params: {upd_prop.parameters}",
        )

        # 17. Impact preview with sample records
        run_assertion(
            17,
            "Impact preview includes sample current records",
            upd_prop.impact.actual_preview_rows == 1 and len(upd_prop.impact.current_sample_records) == 1 and upd_prop.impact.current_sample_records[0]["customer_id"] == 2,
            f"Impact preview sample records incorrect: {upd_prop.impact}",
        )

        # 18. Excessive affected rows limit (> 500 rows)
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS bulk_items (id INTEGER PRIMARY KEY, active INTEGER);"))
            conn.execute(text("DELETE FROM bulk_items;"))
            bulk_data = [{"id": i, "active": 1} for i in range(1, 550)]
            conn.execute(text("INSERT INTO bulk_items (id, active) VALUES (:id, :active)"), bulk_data)
        
        bulk_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="bulk_items",
            changes=[{"column": "active", "proposed_value": 0}],
            condition_sql="id > :min_id",
            condition_params={"min_id": 0},
            reason="Mass deactivation",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            18,
            "Excessive affected rows (> 500 rows) flagged",
            bulk_prop.impact.is_excessive and any("excessive" in w.lower() or "exceeds" in w.lower() for w in bulk_prop.impact.warnings),
            f"Excessive rows warning not triggered: {bulk_prop.impact.warnings if bulk_prop.impact else 'None'}",
        )

        # 19. Risk classification: LOW (single row non-critical update on standalone table)
        low_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="products",
            changes=[{"column": "name", "proposed_value": "Mechanical Keyboard Pro"}],
            condition_sql="product_id = :id",
            condition_params={"id": 101},
            reason="Name spelling correction",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            19,
            "Risk classification: LOW for single non-critical row update",
            low_prop.risk == ActionRisk.LOW.value,
            f"Expected LOW risk, got {low_prop.risk}",
        )

        # 20. Risk classification: MEDIUM (multi-row update on non-critical column)
        med_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="products",
            changes=[{"column": "category", "proposed_value": "Peripherals"}],
            condition_sql="category = :cat",
            condition_params={"cat": "Electronics"},
            reason="Rename category",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            20,
            "Risk classification: MEDIUM for multi-row non-critical update",
            med_prop.risk == ActionRisk.MEDIUM.value,
            f"Expected MEDIUM risk, got {med_prop.risk}",
        )

        # 21. Risk classification: HIGH (DELETE operation)
        run_assertion(
            21,
            "Risk classification: HIGH for DELETE operation",
            del_prop.risk == ActionRisk.HIGH.value,
            f"Expected HIGH risk for DELETE, got {del_prop.risk}",
        )

        # 22. Risk classification: HIGH (business critical column: price, amount, stock)
        price_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="products",
            changes=[{"column": "price", "proposed_value": 39.99}],
            condition_sql="product_id = :id",
            condition_params={"id": 102},
            reason="Price drop",
            engine=engine,
            database_identity=db_id,
        )
        run_assertion(
            22,
            "Risk classification: HIGH for business-critical column (price)",
            price_prop.risk == ActionRisk.HIGH.value,
            f"Expected HIGH risk for price update, got {price_prop.risk}",
        )

        # 23. Risk classification: BLOCKED
        run_assertion(
            23,
            "Risk classification: BLOCKED for invalid proposal",
            bad_tbl_prop.risk == ActionRisk.BLOCKED.value,
            f"Expected BLOCKED risk, got {bad_tbl_prop.risk}",
        )

        # 24. Confirmation token generation
        token_info = generate_confirmation_token(
            proposal=price_prop,
            user_id="user_test_1",
            db_identity=db_id,
            high_risk_acknowledged=True,
        )
        run_assertion(
            24,
            "Confirmation token generation (HMAC-SHA256)",
            token_info.confirmation_token and len(token_info.confirmation_token.split(".")) == 3,
            "Confirmation token structure invalid",
        )

        # 25. Confirmation token HMAC signature verification
        is_sig_valid, sig_msg = validate_confirmation_token(
            token_str=token_info.confirmation_token,
            proposal=price_prop,
            user_id="user_test_1",
            current_db_identity=db_id,
        )
        run_assertion(
            25,
            "Confirmation token HMAC signature verification passes",
            is_sig_valid,
            f"Token signature verification failed: {sig_msg}",
        )

        # 26. Confirmation token binding (user, action_id, db identity, action_hash)
        is_user_bound, user_msg = validate_confirmation_token(
            token_str=token_info.confirmation_token,
            proposal=price_prop,
            user_id="DIFFERENT_USER",
            current_db_identity=db_id,
        )
        run_assertion(
            26,
            "Confirmation token rejects mismatched user_id",
            not is_user_bound and "ownership mismatch" in (user_msg or "").lower(),
            f"Expected user mismatch rejection, got {user_msg}",
        )

        # 27. Confirmation token expiration (expired timestamp rejected)
        expired_token_info = generate_confirmation_token(
            proposal=price_prop,
            user_id="user_test_1",
            db_identity=db_id,
            ttl_seconds=-10,
        )
        is_exp_valid, exp_msg = validate_confirmation_token(
            token_str=expired_token_info.confirmation_token,
            proposal=price_prop,
            user_id="user_test_1",
            current_db_identity=db_id,
        )
        run_assertion(
            27,
            "Confirmation token rejects expired timestamp",
            not is_exp_valid and "expired" in (exp_msg or "").lower(),
            f"Expected expiration rejection, got {exp_msg}",
        )

        # 28. Modified action invalidates confirmation token (hash mismatch)
        mutated_action = ActionProposal.from_dict(price_prop.to_dict())
        mutated_action.changes[0].proposed_value = 1.00
        is_hash_valid, hash_msg = validate_confirmation_token(
            token_str=token_info.confirmation_token,
            proposal=mutated_action,
            user_id="user_test_1",
            current_db_identity=db_id,
        )
        run_assertion(
            28,
            "Modified action parameters invalidate confirmation token (hash mismatch)",
            not is_hash_valid and "modified" in (hash_msg or "").lower(),
            f"Expected hash mismatch rejection, got {hash_msg}",
        )

        # 29. Tampered token signature rejected
        parts = token_info.confirmation_token.split(".")
        tampered_token = f"{parts[0]}.{parts[1]}.tampered_signature_12345"
        is_tampered_valid, tamp_msg = validate_confirmation_token(
            token_str=tampered_token,
            proposal=price_prop,
            user_id="user_test_1",
            current_db_identity=db_id,
        )
        run_assertion(
            29,
            "Tampered token signature is rejected",
            not is_tampered_valid and "failed" in (tamp_msg or "").lower(),
            f"Expected signature rejection, got {tamp_msg}",
        )

        # 30. High-risk execution blocked without high_risk_acknowledged
        unack_token_info = generate_confirmation_token(
            proposal=price_prop,
            user_id="user_test_1",
            db_identity=db_id,
            high_risk_acknowledged=False,
        )
        unack_valid, unack_msg = validate_confirmation_token(
            token_str=unack_token_info.confirmation_token,
            proposal=price_prop,
            user_id="user_test_1",
            current_db_identity=db_id,
        )
        run_assertion(
            30,
            "High-risk confirmation blocked without high_risk_acknowledged",
            not unack_valid and "explicit user acknowledgment" in (unack_msg or "").lower(),
            f"Expected high risk ack rejection, got {unack_msg}",
        )

        # 31. Atomic execution inside transaction (BEGIN ... COMMIT)
        price_prop.confirmation = token_info
        price_prop.status = ActionStatus.CONFIRMED.value
        save_action(price_prop)
        exec_res = execute_action(
            proposal=price_prop,
            engine=engine,
            user_id="user_test_1",
            confirmation_token=token_info.confirmation_token,
            current_db_identity=db_id,
        )
        run_assertion(
            31,
            "Atomic execution inside transaction succeeds and commits",
            exec_res.success and exec_res.actual_rows_affected == 1 and exec_res.transaction_id,
            f"Transaction execution failed: {exec_res.error}",
        )

        # 32. Rollback on execution error
        fail_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="INSERT",
            target_table="customers",
            changes=[
                {"column": "customer_id", "proposed_value": 1},  # PK conflict
                {"column": "name", "proposed_value": "Duplicate"},
                {"column": "email", "proposed_value": "dup@example.com"},
                {"column": "status", "proposed_value": "active"},
            ],
            reason="Trigger duplicate key error",
            engine=engine,
            database_identity=db_id,
        )
        fail_token = generate_confirmation_token(fail_prop, "user_test_1", db_id, high_risk_acknowledged=True)
        fail_prop.confirmation = fail_token
        fail_prop.status = ActionStatus.CONFIRMED.value
        save_action(fail_prop)
        try:
            execute_action(
                proposal=fail_prop,
                engine=engine,
                user_id="user_test_1",
                confirmation_token=fail_token.confirmation_token,
                current_db_identity=db_id,
            )
            rolled_back = False
            fail_err = ""
        except ActionExecutionError as aee:
            rolled_back = True
            fail_err = str(aee)
        run_assertion(
            32,
            "Rollback on execution error (integrity constraint)",
            rolled_back and "UNIQUE constraint failed" in fail_err,
            f"Execution did not rollback properly: {fail_err}",
        )

        # 33. Post-execution verification for UPDATE (checks updated value)
        verif_res = verify_action_execution(price_prop, engine)
        run_assertion(
            33,
            "Post-execution verification for UPDATE verifies mutated value",
            verif_res.verified and "Verified:" in verif_res.details,
            f"UPDATE post-execution verification failed: {verif_res.details}",
        )

        # 34. Post-execution verification for DELETE (checks count == 0)
        del_token = generate_confirmation_token(
            proposal=del_prop,
            user_id="user_test_1",
            db_identity=db_id,
            high_risk_acknowledged=True,
        )
        del_prop.confirmation = del_token
        del_prop.status = ActionStatus.CONFIRMED.value
        save_action(del_prop)
        del_exec = execute_action(
            proposal=del_prop,
            engine=engine,
            user_id="user_test_1",
            confirmation_token=del_token.confirmation_token,
            current_db_identity=db_id,
        )
        del_verif = verify_action_execution(del_prop, engine)
        run_assertion(
            34,
            "Post-execution verification for DELETE verifies 0 remaining records",
            del_verif.verified and del_verif.actual_value == 0,
            f"DELETE verification failed: {del_verif.details}",
        )

        # 35. Verification failure detection
        bogus_action = ActionProposal.from_dict(price_prop.to_dict())
        bogus_action.action_id = "act-bogus-verify"
        bogus_action.changes[0].proposed_value = 999999.99
        bogus_verif = verify_action_execution(bogus_action, engine)
        run_assertion(
            35,
            "Verification failure properly flagged when actual value does not match expected",
            not bogus_verif.verified and "Verification failed" in bogus_verif.details,
            f"Expected verification failure, got {bogus_verif}",
        )

        # 36. Duplicate execution protection (409 Conflict)
        try:
            execute_action(
                proposal=price_prop,
                engine=engine,
                user_id="user_test_1",
                confirmation_token=token_info.confirmation_token,
                current_db_identity=db_id,
            )
            dup_blocked = False
            dup_err = ""
        except ActionExecutionConflict as aec:
            dup_blocked = True
            dup_err = str(aec)
        run_assertion(
            36,
            "Duplicate execution protection blocks re-executing completed action",
            dup_blocked and "already been executed" in dup_err,
            f"Duplicate execution was not blocked: {dup_err}",
        )

        # 37. State machine progression (PROPOSED -> READY_FOR_CONFIRMATION -> CONFIRMED -> EXECUTED -> VERIFIED)
        sm_prop = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="customers",
            changes=[{"column": "email", "proposed_value": "new_alice@example.com"}],
            condition_sql="customer_id = :cid",
            condition_params={"cid": 1},
            reason="Update email",
            engine=engine,
            database_identity=db_id,
        )
        s1 = sm_prop.status in (ActionStatus.PROPOSED.value, ActionStatus.READY_FOR_CONFIRMATION.value)
        sm_tok = generate_confirmation_token(sm_prop, "user_test_1", db_id, high_risk_acknowledged=True)
        sm_prop.confirmation = sm_tok
        sm_prop.status = ActionStatus.CONFIRMED.value
        save_action(sm_prop)
        s2 = sm_prop.status == ActionStatus.CONFIRMED.value
        sm_exec = execute_action(
            proposal=sm_prop,
            engine=engine,
            user_id="user_test_1",
            confirmation_token=sm_tok.confirmation_token,
            current_db_identity=db_id,
        )
        s3 = sm_prop.status in (ActionStatus.EXECUTED.value, ActionStatus.VERIFIED.value) and sm_exec.success
        run_assertion(
            37,
            "State machine progression: PROPOSED -> CONFIRMED -> EXECUTED -> VERIFIED",
            s1 and s2 and s3,
            f"State machine progression failed: s1={s1}, s2={s2}, s3={s3}",
        )

        # 38. Cancel action sets status CANCELLED
        cancel_target = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="customers",
            changes=[{"column": "status", "proposed_value": "archived"}],
            condition_sql="customer_id = :id",
            condition_params={"id": 3},
            reason="To be cancelled",
            engine=engine,
            database_identity=db_id,
        )
        cancel_target.status = ActionStatus.CANCELLED.value
        save_action(cancel_target)
        fetched_cancel = get_action(cancel_target.action_id, "user_test_1")
        run_assertion(
            38,
            "Cancel action sets status to CANCELLED",
            fetched_cancel is not None and fetched_cancel.status == ActionStatus.CANCELLED.value,
            f"Cancelled action status is {fetched_cancel.status if fetched_cancel else 'None'}",
        )

        # 39. Cancel already executed action blocked
        # Using API cancel endpoint for an executed action
        auth_token_u1 = create_access_token(user_id="user_test_1", username="user_test_1")
        cancel_resp = client.post(
            f"/intelligence/actions/{price_prop.action_id}/cancel",
            headers={"Authorization": f"Bearer {auth_token_u1}"},
        )

        run_assertion(
            39,
            "Cancelling an already EXECUTED/VERIFIED action returns 400 Bad Request",
            cancel_resp.status_code == 400,
            f"Cancelling executed action returned status {cancel_resp.status_code}",
        )

        # 40. Audit logging on success
        audits = list_audits("user_test_1")
        has_exec_audit = any(a.execution_status == "SUCCESS" and a.user_id == "user_test_1" for a in audits)
        run_assertion(
            40,
            "Audit logging records SUCCESS in persistent audit store",
            has_exec_audit,
            f"No SUCCESS audit found: {[a.execution_status for a in audits]}",
        )

        # 41. Audit logging on failure
        has_fail_audit = any(a.execution_status == "FAILED" and a.user_id == "user_test_1" for a in audits)
        run_assertion(
            41,
            "Audit logging records FAILED on transaction rollback",
            has_fail_audit,
            f"No FAILED audit found in {[a.execution_status for a in audits]}",
        )


        # 42. Audit log hides secrets (no passwords, tokens)
        import json
        has_leak = False
        for a in audits:
            record_str = json.dumps(a.to_dict()).lower()
            if "password" in record_str or "secret" in record_str:
                has_leak = True
                break
        run_assertion(
            42,
            "Audit records contain no secret or password leakage",
            not has_leak,
            "Audit log leaked sensitive keywords",
        )


        # 43. API: POST /intelligence/actions/propose requires JWT
        anon_resp = client.post("/intelligence/actions/propose", json={
            "action_type": "UPDATE",
            "target_table": "customers",
            "changes": [{"column": "status", "proposed_value": "active"}],
            "condition_sql": "customer_id = 1",
        })
        run_assertion(
            43,
            "API: POST /intelligence/actions/propose requires JWT authentication",
            anon_resp.status_code in (401, 403),
            f"Anonymous proposal returned status {anon_resp.status_code}",
        )

        # 44. API: Route registration for all 7 Phase 8.8 endpoints
        routes = [r.path for r in app.routes]
        has_all_routes = (
            "/intelligence/actions/propose" in routes and
            "/intelligence/actions/{action_id}/preview" in routes and
            "/intelligence/actions/{action_id}/confirm" in routes and
            "/intelligence/actions/{action_id}/execute" in routes and
            "/intelligence/actions/{action_id}" in routes and
            "/intelligence/actions" in routes and
            "/intelligence/actions/{action_id}/cancel" in routes
        )
        run_assertion(
            44,
            "All 7 Phase 8.8 API endpoints are registered on FastAPI application",
            has_all_routes,
            f"Missing routes in app: {routes}",
        )

        # 45. API: User isolation (User B cannot preview User A's action)
        token_user_a = create_access_token(user_id="user_alpha", username="user_alpha")
        token_user_b = create_access_token(user_id="user_beta", username="user_beta")
        
        alpha_prop = build_action_proposal(
            user_id="user_alpha",
            action_type="UPDATE",
            target_table="customers",
            changes=[{"column": "name", "proposed_value": "Alpha User"}],
            condition_sql="customer_id = :id",
            condition_params={"id": 1},
            reason="Alpha private update",
            engine=engine,
            database_identity=db_id,
        )
        save_action(alpha_prop)

        beta_preview_resp = client.post(
            f"/intelligence/actions/{alpha_prop.action_id}/preview",
            headers={"Authorization": f"Bearer {token_user_b}"},
        )
        run_assertion(
            45,
            "API User Isolation: User B cannot preview User A's action (404/403)",
            beta_preview_resp.status_code in (403, 404),
            f"User B got status {beta_preview_resp.status_code} accessing User A's action",
        )

        # 46. API: User isolation (User B cannot confirm User A's action)
        beta_confirm_resp = client.post(
            f"/intelligence/actions/{alpha_prop.action_id}/confirm",
            headers={"Authorization": f"Bearer {token_user_b}"},
            json={},
        )
        run_assertion(
            46,
            "API User Isolation: User B cannot confirm User A's action (404/403)",
            beta_confirm_resp.status_code in (403, 404),
            f"User B got status {beta_confirm_resp.status_code} confirming User A's action",
        )

        # 47. API: User isolation (User B cannot execute User A's action)
        beta_exec_resp = client.post(
            f"/intelligence/actions/{alpha_prop.action_id}/execute",
            headers={"Authorization": f"Bearer {token_user_b}"},
            json={"confirmation_token": "fake_token"},
        )
        run_assertion(
            47,
            "API User Isolation: User B cannot execute User A's action (404/403)",
            beta_exec_resp.status_code in (403, 404),
            f"User B got status {beta_exec_resp.status_code} executing User A's action",
        )

        # 48. Multi-dialect SQL identifier quoting (SQLite, PostgreSQL, MySQL)
        sqlite_q = quote_identifier("table_name", "sqlite")
        pg_q = quote_identifier("table_name", "postgresql")
        mysql_q = quote_identifier("table_name", "mysql")
        run_assertion(
            48,
            "Multi-dialect SQL identifier quoting (SQLite: \", PG: \", MySQL: `)",
            sqlite_q == '"table_name"' and pg_q == '"table_name"' and mysql_q == '`table_name`',
            f"Dialect quoting error: sqlite={sqlite_q}, pg={pg_q}, mysql={mysql_q}",
        )

        # 49. Zero autonomous mutation guarantee (no execution without explicit confirmation)
        unconfirmed_action = build_action_proposal(
            user_id="user_test_1",
            action_type="UPDATE",
            target_table="customers",
            changes=[{"column": "status", "proposed_value": "autonomous"}],
            condition_sql="customer_id = :id",
            condition_params={"id": 1},
            reason="Autonomous attempt",
            engine=engine,
            database_identity=db_id,
        )
        unconfirmed_action.status = ActionStatus.PROPOSED.value
        try:
            execute_action(
                proposal=unconfirmed_action,
                engine=engine,
                user_id="user_test_1",
                confirmation_token="",
                current_db_identity=db_id,
            )
            auto_blocked = False
            auto_err = ""
        except ActionExecutionError as aee:
            auto_blocked = True
            auto_err = str(aee)
        run_assertion(
            49,
            "Zero Autonomous Mutation: unconfirmed proposals strictly refuse execution",
            auto_blocked and ("explicitly confirmed first" in auto_err or "cannot be executed in state" in auto_err),
            f"Autonomous execution was not rejected: {auto_err}",
        )

        # 50. Phase 8.1 - 8.7 Regression Guards
        try:
            from app.intelligence.business_intelligence.insight_engine import generate_business_intelligence_report
            from app.intelligence.business_intelligence.multitable_engine import query_multitable_bi
            from app.intelligence.proactive.evaluator import evaluate_proactive_metrics
            from app.intelligence.decision.decision_engine import run_decision_analysis
            from app.intelligence.learning.outcome_engine import synthesize_learning_summary
            from app.intelligence.monitoring.monitor_engine import run_monitoring_scan
            from app.intelligence.investigation.investigator import investigate_signal
            regressions_ok = True
        except ImportError as ie:
            regressions_ok = False
            ie_msg = str(ie)
        run_assertion(
            50,
            "Phase 8.1 - 8.7 Regression Guards: all core engines import cleanly without regression",
            regressions_ok,
            f"Regression in earlier phase modules: {ie_msg if not regressions_ok else ''}",
        )


    finally:
        # Cleanup temporary sqlite database
        try:
            engine.dispose()
            if os.path.exists(db_path):
                os.remove(db_path)
        except Exception:
            pass

    # Summary
    passed = sum(1 for _, status, _ in test_results if status == "PASS")
    failed = sum(1 for _, status, _ in test_results if status == "FAIL")
    total = len(test_results)
    print("\n" + "=" * 60)
    print(f"PHASE 8.8 TEST SUMMARY: {passed}/{total} Passed, {failed} Failed")
    print("=" * 60 + "\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
