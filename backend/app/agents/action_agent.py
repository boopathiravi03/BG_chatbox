from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text

from app.agents.audit import store_action
from app.agents.base_agent import BaseAgent
from app.agents.models import ActionPlan, AgentFinding, AgentResult, AgentTask
from app.database.database_manager import get_current_db_type, get_engine
from app.intelligence.forecasting.detector import quote_identifier
from app.tools.execute_query import validate_sql


class ActionAgent(BaseAgent):
    name = "action_agent"
    role = "Safe Action Specialist"
    description = (
        "Prepares bounded, deterministic database modifications with exact SQL previews, "
        "pre-execution affected-row estimates, and verification post-checks. Never executes without human confirmation."
    )
    is_read_only = False
    capabilities = [
        "Formulate bounded UPDATE and DELETE operations with strict WHERE clauses",
        "Estimate affected row counts using non-destructive pre-execution checks",
        "Generate post-execution verification queries and rollback safety constraints",
        "Enforce explicit human-in-the-loop confirmation boundaries",
    ]
    allowed_tools = [
        "schema_inspector",
        "affected_row_estimator",
        "sql_validator",
        "transaction_manager",
    ]

    def execute(self, task: AgentTask, context: dict[str, Any]) -> AgentResult:
        steps = [f"Evaluating action request: '{task.request}'"]

        # Reject prompt injection or rules-bypass patterns immediately (before DB check)
        req_lower = task.request.strip().lower()
        injection_triggers = [
            "ignore your safety rules",
            "ignore rules",
            "bypass confirmation",
            "drop table",
            "alter table",
            "truncate",
            "grant",
            "revoke",
        ]
        for trigger in injection_triggers:
            if trigger in req_lower:
                steps.append(f"SAFETY GUARD TRIGGERED: Detected disallowed command/pattern '{trigger}'.")
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    status="FAILED",
                    summary=(
                        f"Action preparation rejected: Request contains forbidden operation or "
                        f"attempted safety boundary bypass ('{trigger}'). Destructive DDL and unrestricted modifications are strictly prohibited."
                    ),
                    findings=[
                        AgentFinding(
                            id=f"action_rejected_{uuid.uuid4().hex[:6]}",
                            severity="CRITICAL",
                            title="Prohibited Operation Rejected",
                            description=f"Action Agent rejected requested pattern '{trigger}'.",
                        )
                    ],
                    evidence={"blocked_pattern": trigger},
                    recommendations=["Only bounded, parameterized DML (UPDATE, DELETE with WHERE clause) is supported."],
                    proposed_action=None,
                    limitations=["Administrative DDL (DROP, ALTER, TRUNCATE) is strictly disallowed."],
                    execution_steps=steps,
                )

        engine = get_engine()
        db_type = get_current_db_type()

        if engine is None or db_type == "none":
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status="FAILED",
                summary="No database currently connected. Cannot prepare action.",
                findings=[],
                evidence={},
                recommendations=[],
                proposed_action=None,
                limitations=["Database connection required."],
                execution_steps=steps,
            )

        # 1. Parse or Extract Action Intent & Constraints
        # Context may pass pre-structured action parameters or an exact SQL candidate
        exact_sql = context.get("exact_sql") or ""
        target_table = context.get("table") or ""
        where_clause = context.get("where") or ""
        set_clause = context.get("set") or ""
        action_type = context.get("action_type") or ""


        # Parse orphan fix pattern e.g. "delete orphan records from orders where customer_id = 999"
        if not exact_sql:
            delete_match = re.search(r"delete\s+(?:.*?\s+from\s+|from\s+)?([a-zA-Z0-9_]+)\s+where\s+(.+)", task.request, re.IGNORECASE)
            update_match = re.search(r"update\s+([a-zA-Z0-9_]+)\s+set\s+(.+?)\s+where\s+(.+)", task.request, re.IGNORECASE)

            if delete_match:
                target_table = delete_match.group(1).strip()
                where_clause = delete_match.group(2).strip().rstrip(";")
                action_type = "DELETE"
                t_quoted = quote_identifier(target_table, db_type)
                exact_sql = f"DELETE FROM {t_quoted} WHERE {where_clause}"

            elif update_match:
                target_table = update_match.group(1).strip()
                set_clause = update_match.group(2).strip()
                where_clause = update_match.group(3).strip().rstrip(";")
                action_type = "UPDATE"
                t_quoted = quote_identifier(target_table, db_type)
                exact_sql = f"UPDATE {t_quoted} SET {set_clause} WHERE {where_clause}"

            else:
                # Check if raw SQL was given in task.request
                if req_lower.startswith("update ") or req_lower.startswith("delete "):
                    exact_sql = task.request.strip().rstrip(";")
                    action_type = "UPDATE" if req_lower.startswith("update ") else "DELETE"
                    # Extract table
                    tbl_match = re.search(r"(?:update|delete\s+from)\s+([`\"\[]?\w+[`\"\]]?)", exact_sql, re.IGNORECASE)
                    if tbl_match:
                        target_table = tbl_match.group(1).strip('`"[]')
                    wh_match = re.search(r"where\s+(.+)$", exact_sql, re.IGNORECASE)
                    if wh_match:
                        where_clause = wh_match.group(1).strip()

        if not exact_sql or not target_table or not where_clause:
            steps.append("Unable to determine complete, bounded table and WHERE clause.")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status="FAILED",
                summary="Unable to prepare a safe action from the available schema. A clear target table and explicit WHERE condition are required.",
                findings=[],
                evidence={},
                recommendations=["Provide specific table and condition (e.g., 'Delete from orders where customer_id = 999')."],
                proposed_action=None,
                limitations=["Unbounded modifications without WHERE clauses are strictly prohibited."],
                execution_steps=steps,
            )

        # 2. Server-side SQL Validation
        val = validate_sql(exact_sql)
        if not val.get("allowed"):
            steps.append(f"SQL validation rejected statement: {val.get('reason')}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status="FAILED",
                summary=f"SQL validation error: {val.get('reason', 'Operation not allowed.')}",
                findings=[],
                evidence={"validation": val},
                recommendations=["Revise SQL statement to conform to safe bounded standards."],
                proposed_action=None,
                limitations=["Only bounded DML permitted."],
                execution_steps=steps,
            )

        # 3. Estimate Affected Rows safely via non-destructive SELECT COUNT(*)
        t_quoted = quote_identifier(target_table, db_type)
        count_sql = f"SELECT COUNT(*) FROM {t_quoted} WHERE {where_clause}"
        verification_sql = count_sql  # Verification query post-execution expects 0 remaining matching rows

        estimated_rows = 0
        try:
            with engine.connect() as conn:
                estimated_rows = int(conn.execute(text(count_sql)).scalar() or 0)
            steps.append(f"Pre-execution row estimate: {estimated_rows:,} affected rows matching condition.")
        except Exception as e:
            steps.append(f"Error estimating affected rows: {str(e)}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status="FAILED",
                summary=f"Unable to safely estimate affected records. Action requires manual review. Error: {str(e)}",
                findings=[],
                evidence={"count_sql": count_sql},
                recommendations=["Verify column names and SQL syntax for the target condition."],
                proposed_action=None,
                limitations=["Row count estimation is required for action approval."],
                execution_steps=steps,
            )

        # 4. Classify Risk Level
        if action_type.upper() == "DELETE" or estimated_rows > 50:
            risk_level = "HIGH"
        elif estimated_rows > 1:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        action_id = f"act_{uuid.uuid4().hex[:8]}"

        if action_type.upper() == "DELETE":
            expected_verification_result = "0"
        else:
            expected_verification_result = str(estimated_rows)

        action_plan = ActionPlan(
            action_id=action_id,
            task_id=task.task_id,
            agent_name=self.name,
            table=target_table,
            action_type=action_type.upper(),
            estimated_rows=estimated_rows,
            exact_sql=exact_sql,
            verification_sql=verification_sql,
            expected_verification_result=expected_verification_result,
            risk_level=risk_level,

            potential_consequence=(
                f"Will permanently {action_type.lower()} {estimated_rows:,} record(s) in table '{target_table}'. "
                "Operation will run inside a transactional block with automated rollback if post-verification fails."
            ),
            rollback_considerations=(
                "Executed within a transactional block. In case of verification mismatch or database error, "
                "the transaction is rolled back immediately."
            ),
            status="AWAITING_CONFIRMATION",
            created_at=datetime.now().isoformat(),
        )

        # Store in audit store
        store_action(action_plan)
        steps.append(f"Action plan '{action_id}' generated and stored with status AWAITING_CONFIRMATION.")

        findings = [
            AgentFinding(
                id=f"plan_finding_{action_id}",
                severity="WARNING" if risk_level in {"HIGH", "MEDIUM"} else "INFO",
                title=f"Proposed {action_type.upper()} Action on '{target_table}'",
                description=f"Affects estimated {estimated_rows:,} row(s). Awaiting explicit human confirmation.",
                table=target_table,
                evidence={
                    "estimated_rows": estimated_rows,
                    "risk_level": risk_level,
                    "exact_sql": exact_sql,
                },
            )
        ]

        summary = (
            f"Action plan prepared: {action_type.upper()} on table '{target_table}'. "
            f"Estimated impact: {estimated_rows:,} record(s). Risk Level: {risk_level}. "
            "Action has NOT been executed. Explicit human confirmation is required."
        )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            status="ACTION_REQUIRED",
            summary=summary,
            findings=findings,
            evidence={
                "action_id": action_id,
                "table": target_table,
                "action_type": action_type.upper(),
                "estimated_rows": estimated_rows,
                "risk_level": risk_level,
                "exact_sql": exact_sql,
            },
            recommendations=[
                f"Review exact SQL and consequence preview before confirming.",
                f"For {risk_level} risk actions, verify that target scope is accurate.",
            ],
            proposed_action=action_plan,
            limitations=[
                "Safe Action Agent prepares actions only; execution is strictly gated behind human approval.",
                "Rollback is guaranteed within the transactional execution boundary.",
            ],
            execution_steps=steps,
        )
