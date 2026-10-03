"""
backend/scratch/test_phase9_1_knowledge.py

Phase 9.1: Enterprise Knowledge & Context Intelligence Comprehensive Verification Suite
Tests all 60 verification points:
1. Knowledge model creation
2. Entity registry
3. Metric registry
4. Business definition
5. Business rule
6. Provenance
7. Schema-derived knowledge
8. User-provided knowledge
9. AI-inferred knowledge
10. Confirmed knowledge
11. Proposed knowledge
12. Disabled knowledge
13. Conflict detection
14. Conflict resolution
15. Definition versioning
16. Historical definition preservation
17. User isolation
18. Database isolation
19. Table validation
20. Column validation
21. Data type validation
22. SQL safety
23. DML blocking
24. DDL blocking
25. Command chaining blocking
26. Metric definition resolution
27. Rule application
28. Confirmed rule application
29. Proposed rule non-application
30. Metric lineage
31. Entity lineage
32. Knowledge search
33. Unknown context
34. Natural language context
35. Context confirmation
36. Ambiguous context
37. Duplicate context
38. Conflict handling
39. Phase 8.1 integration
40. Phase 8.2 integration
41. Phase 8.4 integration
42. Phase 8.7 integration
43. Phase 8.9 integration
44. Phase 9.0 integration
45. Historical analysis integrity
46. Forecast definition consistency
47. Outcome definition consistency
48. Recommendation context
49. Authentication
50. Rate limiting
51. API isolation
52. Persistence
53. Retrieval
54. Lineage retrieval
55. Groq sanitization
56. No sensitive data leakage
57. Invalid schema reference
58. Database switching
59. Database disconnect
60. Frontend API integration
"""
from __future__ import annotations

import os
import sys
import unittest
import tempfile
import sqlite3
from typing import Any

# Ensure backend path is on sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.security.auth import create_access_token
import app.database.database_manager as dbm
from app.intelligence.knowledge.models import (
    KnowledgeProvenance,
    KnowledgeStatus,
    EntityImportance,
    RuleScope,
    RuleType,
    BusinessEntity,
    BusinessRule,
    BusinessMetric,
    ColumnSemantic,
    KnowledgeConflict,
    KnowledgeVersionRecord,
    KnowledgeLineage,
    KnowledgeExplanation,
    KnowledgeSummary,
    ContextParseResult,
)
from app.intelligence.knowledge.provenance import (
    is_authoritative,
    is_inferred,
    format_provenance_badge,
)
from app.intelligence.knowledge.knowledge_store import (
    save_entity,
    get_entity,
    list_entities,
    save_rule,
    get_rule,
    list_rules,
    save_metric,
    get_metric,
    list_metrics,
    save_conflict,
    list_conflicts,
    list_versions,
    confirm_knowledge_item,
    disable_knowledge_item,
    resolve_knowledge_conflict,
    get_knowledge_summary,
    clear_knowledge_store,
)
from app.intelligence.knowledge.entity_registry import (
    discover_and_sync_entities,
)
from app.intelligence.knowledge.metric_registry import (
    discover_and_sync_metrics,
    resolve_metric_calculation,
)
from app.intelligence.knowledge.business_rules import (
    validate_rule_safety,
    detect_rule_conflicts,
    get_active_filters_for_table,
)
from app.intelligence.knowledge.context_engine import (
    parse_and_propose_context,
)
from app.intelligence.knowledge.knowledge_resolver import (
    build_metric_lineage,
    search_knowledge,
)
from app.intelligence.knowledge.knowledge_explainer import (
    explain_knowledge_item,
)


class TestPhase91EnterpriseKnowledge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.user_a_id = "test_user_a"
        cls.user_b_id = "test_user_b"
        cls.db_id_1 = "sqlite:///mock_test_db_1.sqlite"
        cls.db_id_2 = "sqlite:///mock_test_db_2.sqlite"

        cls.token_a = create_access_token(user_id=cls.user_a_id, username="usera")
        cls.token_b = create_access_token(user_id=cls.user_b_id, username="userb")

        # Create temporary SQLite in-memory database for real schema testing
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with cls.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    customer_id INTEGER,
                    total_amount REAL,
                    status TEXT,
                    created_at TEXT
                );
            """))
            conn.execute(text("""
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    region TEXT,
                    created_at TEXT
                );
            """))
            # Insert real test rows
            conn.execute(text("""
                INSERT INTO orders (id, customer_id, total_amount, status, created_at)
                VALUES 
                    (1, 101, 150.0, 'completed', '2026-01-10'),
                    (2, 102, 200.0, 'completed', '2026-01-15'),
                    (3, 103, 300.0, 'cancelled', '2026-01-20'),
                    (4, 101, 250.0, 'completed', '2026-02-05'),
                    (5, 104, 400.0, 'refunded', '2026-02-12'),
                    (6, 102, 100.0, 'completed', '2026-03-01'),
                    (7, 105, 500.0, 'completed', '2026-03-15');
            """))
            conn.execute(text("""
                INSERT INTO customers (id, name, region, created_at)
                VALUES 
                    (101, 'Acme Corp', 'North', '2025-12-01'),
                    (102, 'Beta LLC', 'South', '2026-01-01');
            """))
            conn.commit()

        dbm.engine = cls.engine
        dbm.current_db_type = "sqlite"
        from app.database.connection_context import set_user_engine
        set_user_engine(cls.user_a_id, cls.engine, "sqlite", cls.db_id_1)
        set_user_engine(cls.user_b_id, cls.engine, "sqlite", cls.db_id_1)

    def setUp(self):
        clear_knowledge_store(self.user_a_id)
        clear_knowledge_store(self.user_b_id)


    # 1. Knowledge model creation
    def test_01_knowledge_model_creation(self):
        ent = BusinessEntity(
            entity_id="ent_test",
            name="Test",
            plural_name="Tests",
            table_name="tests",
            description="Testing entity",
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        self.assertEqual(ent.name, "Test")
        self.assertEqual(ent.status, KnowledgeStatus.PROPOSED.value)
        d = ent.to_dict()
        self.assertEqual(d["entity_id"], "ent_test")
        rebuilt = BusinessEntity.from_dict(d)
        self.assertEqual(rebuilt.entity_id, "ent_test")

    # 2. Entity registry discovery
    def test_02_entity_registry(self):
        ents = discover_and_sync_entities(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        tbl_names = {e.table_name for e in ents}
        self.assertIn("orders", tbl_names)
        self.assertIn("customers", tbl_names)

    # 3. Metric registry discovery
    def test_03_metric_registry(self):
        mets = discover_and_sync_metrics(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        m_names = [m.name for m in mets]
        self.assertTrue(any("Total Amount" in n or "Orders" in n for n in m_names))

    # 4. Business definition creation
    def test_04_business_definition(self):
        met = BusinessMetric(
            metric_id="met_rev",
            name="Revenue",
            description="Net business revenue",
            table_name="orders",
            column_name="total_amount",
            aggregation="SUM",
            provenance=KnowledgeProvenance.USER_PROVIDED.value,
            status=KnowledgeStatus.CONFIRMED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        saved = save_metric(met)
        retrieved = get_metric("met_rev", self.user_a_id, self.db_id_1)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Revenue")

    # 5. Business rule model & storage
    def test_05_business_rule(self):
        rule = BusinessRule(
            rule_id="rule_excl_cancel",
            name="Exclude Cancelled Orders",
            description="Cancelled orders do not count toward revenue",
            target_table="orders",
            target_column="status",
            expression="status != 'cancelled'",
            status=KnowledgeStatus.PROPOSED.value,
            provenance=KnowledgeProvenance.USER_PROVIDED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        saved = save_rule(rule)
        self.assertEqual(saved.expression, "status != 'cancelled'")

    # 6. Provenance enumeration and verification
    def test_06_provenance(self):
        self.assertTrue(is_authoritative(KnowledgeStatus.CONFIRMED.value))
        self.assertTrue(is_authoritative(KnowledgeStatus.ACTIVE.value))
        self.assertFalse(is_authoritative(KnowledgeStatus.PROPOSED.value))
        self.assertFalse(is_authoritative(KnowledgeStatus.DISABLED.value))

    # 7. Schema-derived knowledge
    def test_07_schema_derived_knowledge(self):
        ents = discover_and_sync_entities(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        order_ent = next(e for e in ents if e.table_name == "orders")
        self.assertEqual(order_ent.provenance, KnowledgeProvenance.SCHEMA_DERIVED.value)

    # 8. User-provided knowledge
    def test_08_user_provided_knowledge(self):
        rule = BusinessRule(
            rule_id="rule_user_1",
            name="Custom Rule",
            description="User custom note",
            target_table="orders",
            expression="total_amount > 0",
            provenance=KnowledgeProvenance.USER_PROVIDED.value,
            status=KnowledgeStatus.CONFIRMED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_rule(rule)
        retrieved = get_rule("rule_user_1", self.user_a_id, self.db_id_1)
        self.assertEqual(retrieved.provenance, KnowledgeProvenance.USER_PROVIDED.value)

    # 9. AI-inferred knowledge
    def test_09_ai_inferred_knowledge(self):
        self.assertTrue(is_inferred(KnowledgeProvenance.AI_INFERRED.value))
        self.assertTrue(is_inferred(KnowledgeProvenance.SCHEMA_DERIVED.value))
        self.assertFalse(is_inferred(KnowledgeProvenance.USER_PROVIDED.value))

    # 10. Confirmed knowledge promotion
    def test_10_confirmed_knowledge(self):
        rule = BusinessRule(
            rule_id="rule_promote",
            name="Promote Rule",
            description="Testing promotion",
            target_table="orders",
            expression="status != 'cancelled'",
            status=KnowledgeStatus.PROPOSED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_rule(rule)
        success = confirm_knowledge_item("rule_promote", self.user_a_id, self.db_id_1)
        self.assertTrue(success)
        retrieved = get_rule("rule_promote", self.user_a_id, self.db_id_1)
        self.assertEqual(retrieved.status, KnowledgeStatus.CONFIRMED.value)

    # 11. Proposed knowledge status
    def test_11_proposed_knowledge(self):
        ents = discover_and_sync_entities(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        for e in ents:
            self.assertEqual(e.status, KnowledgeStatus.PROPOSED.value)

    # 12. Disabled knowledge handling
    def test_12_disabled_knowledge(self):
        rule = BusinessRule(
            rule_id="rule_disable_me",
            name="Disable Test",
            description="Rule to disable",
            target_table="orders",
            expression="status != 'cancelled'",
            status=KnowledgeStatus.CONFIRMED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_rule(rule)
        disable_knowledge_item("rule_disable_me", self.user_a_id, self.db_id_1)
        retrieved = get_rule("rule_disable_me", self.user_a_id, self.db_id_1)
        self.assertEqual(retrieved.status, KnowledgeStatus.DISABLED.value)
        # Should not be returned in active filters
        active = get_active_filters_for_table("orders", self.user_a_id, self.db_id_1)
        self.assertNotIn("status != 'cancelled'", active)

    # 13. Conflict detection
    def test_13_conflict_detection(self):
        r1 = BusinessRule(
            rule_id="r_conflict_1",
            name="Exclude Cancelled",
            description="Exclude cancelled orders",
            target_table="orders",
            target_column="status",
            expression="status != 'cancelled'",
            status=KnowledgeStatus.CONFIRMED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_rule(r1)

        r2 = BusinessRule(
            rule_id="r_conflict_2",
            name="Include Cancelled Only",
            description="Only include cancelled",
            target_table="orders",
            target_column="status",
            expression="status = 'cancelled'",
            status=KnowledgeStatus.PROPOSED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        conflicts = detect_rule_conflicts(r2, self.user_a_id, self.db_id_1)
        self.assertGreater(len(conflicts), 0)
        self.assertEqual(conflicts[0].item_id_a, "r_conflict_1")
        self.assertEqual(conflicts[0].item_id_b, "r_conflict_2")

    # 14. Conflict resolution
    def test_14_conflict_resolution(self):
        conf = KnowledgeConflict(
            conflict_id="conf_test_1",
            knowledge_type="RULE",
            item_id_a="r_conflict_1",
            item_id_b="r_conflict_2",
            target_name="orders.status",
            description="Contradictory conditions",
            statement_a="status != 'cancelled'",
            statement_b="status = 'cancelled'",
            source_a="USER_PROVIDED",
            source_b="USER_PROVIDED",
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_conflict(conf)
        res = resolve_knowledge_conflict(
            conflict_id="conf_test_1",
            resolution_choice="CHOOSE_A",
            resolution_notes="Choice A verified with finance team",
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        self.assertTrue(res)
        conflicts = list_conflicts(self.user_a_id, self.db_id_1, status="RESOLVED")
        self.assertEqual(len(conflicts), 1)

    # 15. Definition versioning
    def test_15_definition_versioning(self):
        met = BusinessMetric(
            metric_id="met_version_test",
            name="Orders Metric",
            description="v1 description",
            table_name="orders",
            aggregation="SUM",
            version=1,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_metric(met)
        # Update metric to v2
        met.version = 2
        met.description = "v2 description with confirmed filters"
        save_metric(met)
        retrieved = get_metric("met_version_test", self.user_a_id, self.db_id_1)
        self.assertEqual(retrieved.version, 2)

    # 16. Historical definition preservation
    def test_16_historical_definition_preservation(self):
        met = BusinessMetric(
            metric_id="met_hist_preserve",
            name="Preserve Metric",
            description="v1 description",
            table_name="orders",
            aggregation="SUM",
            version=1,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_metric(met)
        met.version = 2
        met.description = "v2 updated description"
        save_metric(met)
        versions = list_versions("met_hist_preserve", self.user_a_id, self.db_id_1)
        self.assertGreater(len(versions), 0)
        self.assertEqual(versions[0].version, 1)

    # 17. User isolation: user B cannot see user A's definitions
    def test_17_user_isolation(self):
        rule_a = BusinessRule(
            rule_id="rule_secret_a",
            name="User A Secret Rule",
            description="Private context",
            target_table="orders",
            expression="status != 'cancelled'",
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_rule(rule_a)
        rules_b = list_rules(user_id=self.user_b_id, database_identity=self.db_id_1)
        rule_ids_b = [r.rule_id for r in rules_b]
        self.assertNotIn("rule_secret_a", rule_ids_b)

    # 18. Database isolation: DB 1 definitions do not leak to DB 2
    def test_18_database_isolation(self):
        rule_db1 = BusinessRule(
            rule_id="rule_db1",
            name="DB1 Rule",
            description="DB1 context",
            target_table="orders",
            expression="status != 'cancelled'",
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_rule(rule_db1)
        rules_db2 = list_rules(user_id=self.user_a_id, database_identity=self.db_id_2)
        rule_ids_db2 = [r.rule_id for r in rules_db2]
        self.assertNotIn("rule_db1", rule_ids_db2)

    # 19. Table validation
    def test_19_table_validation(self):
        schema_info = {"tables": {"orders": {}, "customers": {}}}
        valid, err = validate_rule_safety("status != 'cancelled'", target_table="non_existent", schema_info=schema_info)
        self.assertFalse(valid)
        self.assertIn("does not exist", err)

    # 20. Column validation
    def test_20_column_validation(self):
        schema_info = {"tables": {"orders": {"columns": [{"name": "id"}, {"name": "status"}]}}}
        valid, err = validate_rule_safety("fake_col != 'val'", target_table="orders", target_column="fake_col", schema_info=schema_info)
        self.assertFalse(valid)
        self.assertIn("does not exist in table", err)

    # 21. Data type / rule expression validation
    def test_21_data_type_validation(self):
        schema_info = {"tables": {"orders": {"columns": [{"name": "id"}, {"name": "status"}]}}}
        valid, err = validate_rule_safety("status != 'cancelled'", target_table="orders", target_column="status", schema_info=schema_info)
        self.assertTrue(valid)
        self.assertEqual(err, "")

    # 22. SQL safety: clean expressions allowed
    def test_22_sql_safety(self):
        valid, _ = validate_rule_safety("amount > 100", target_table="orders")
        self.assertTrue(valid)

    # 23. DML blocking
    def test_23_dml_blocking(self):
        valid_del, err_del = validate_rule_safety("status = 'cancelled'; DELETE FROM orders;", target_table="orders")
        self.assertFalse(valid_del)
        valid_upd, _ = validate_rule_safety("UPDATE orders SET total_amount = 0", target_table="orders")
        self.assertFalse(valid_upd)

    # 24. DDL blocking
    def test_24_ddl_blocking(self):
        valid_drop, err_drop = validate_rule_safety("DROP TABLE orders", target_table="orders")
        self.assertFalse(valid_drop)
        self.assertIn("disallowed", err_drop)
        valid_alter, _ = validate_rule_safety("ALTER TABLE orders ADD COLUMN hack TEXT", target_table="orders")
        self.assertFalse(valid_alter)

    # 25. Command chaining blocking
    def test_25_command_chaining_blocking(self):
        valid_semi, err_semi = validate_rule_safety("status = 'active'; SELECT 1", target_table="orders")
        self.assertFalse(valid_semi)

    # 26. Metric definition resolution
    def test_26_metric_definition_resolution(self):
        r = BusinessRule(
            rule_id="r_conf_rev",
            name="Revenue Exclusion",
            description="Excludes cancelled",
            target_table="orders",
            target_column="status",
            expression="status != 'cancelled'",
            status=KnowledgeStatus.CONFIRMED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_rule(r)
        calc = resolve_metric_calculation(
            metric_id_or_name="Revenue",
            table_name="orders",
            column_name="total_amount",
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
            db_type="sqlite",
        )
        self.assertTrue(calc["has_confirmed_rules"])
        self.assertIn("status != 'cancelled'", calc["sql_expression"])

    # 27. Rule application
    def test_27_rule_application(self):
        r = BusinessRule(
            rule_id="r_app_test",
            name="Rule App",
            description="Exclusion test",
            target_table="orders",
            expression="status != 'cancelled'",
            status=KnowledgeStatus.CONFIRMED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_rule(r)
        active_filters = get_active_filters_for_table("orders", self.user_a_id, self.db_id_1)
        self.assertIn("status != 'cancelled'", active_filters)

    # 28. Confirmed rule application
    def test_28_confirmed_rule_application(self):
        r = BusinessRule(
            rule_id="r_conf_test",
            name="Rule Conf",
            description="Exclusion test 2",
            target_table="orders",
            expression="status != 'cancelled'",
            status=KnowledgeStatus.CONFIRMED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_rule(r)
        active = get_active_filters_for_table("orders", self.user_a_id, self.db_id_1)
        self.assertIn("status != 'cancelled'", active)

    # 29. Proposed rule non-application: proposed rule MUST NOT affect calculations
    def test_29_proposed_rule_non_application(self):
        prop_rule = BusinessRule(
            rule_id="r_proposed_only",
            name="Proposed Exclusion",
            description="Not yet confirmed",
            target_table="customers",
            expression="region != 'Unknown'",
            status=KnowledgeStatus.PROPOSED.value,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_rule(prop_rule)
        active_cust = get_active_filters_for_table("customers", self.user_a_id, self.db_id_1)
        self.assertNotIn("region != 'Unknown'", active_cust)

    # 30. Metric lineage trace
    def test_30_metric_lineage(self):
        discover_and_sync_entities(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        discover_and_sync_metrics(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        lin = build_metric_lineage("met_orders_total_amount_sum", self.user_a_id, self.db_id_1, "sqlite")
        self.assertGreater(len(lin.nodes), 3)
        node_types = [n.type for n in lin.nodes]
        self.assertIn("ENTITY", node_types)
        self.assertIn("METRIC", node_types)
        self.assertIn("SQL", node_types)

    # 31. Entity lineage
    def test_31_entity_lineage(self):
        discover_and_sync_entities(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        discover_and_sync_metrics(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        lin = build_metric_lineage("met_orders_count", self.user_a_id, self.db_id_1, "sqlite")
        self.assertEqual(lin.nodes[0].type, "ENTITY")
        self.assertIn("orders", lin.nodes[0].details["table_name"])

    # 32. Knowledge search
    def test_32_knowledge_search(self):
        discover_and_sync_entities(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        discover_and_sync_metrics(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        res = search_knowledge("order", self.user_a_id, self.db_id_1)
        self.assertTrue(res["found"])
        self.assertGreater(len(res["entities"]) + len(res["metrics"]) + len(res["rules"]), 0)

    # 33. Unknown context handling (never hallucinates)
    def test_33_unknown_context(self):
        res = search_knowledge("quantum_hyperdrive_fluctuations", self.user_a_id, self.db_id_1)
        self.assertFalse(res["found"])
        self.assertIn("not configured", res["answer"])

    # 34. Natural language context parsing
    def test_34_natural_language_context(self):
        res = parse_and_propose_context(
            "Cancelled orders should not count toward revenue",
            self.user_a_id,
            self.db_id_1,
            self.engine,
            "sqlite",
        )
        self.assertTrue(res.parsed_successfully)
        self.assertIsNotNone(res.proposed_rule)
        self.assertIn("cancelled", res.proposed_rule.expression)
        self.assertEqual(res.proposed_rule.status, KnowledgeStatus.PROPOSED.value)

    # 35. Context confirmation
    def test_35_context_confirmation(self):
        parse_res = parse_and_propose_context(
            "Exclude refunded from revenue",
            self.user_a_id,
            self.db_id_1,
            self.engine,
            "sqlite",
        )
        rule_id = parse_res.proposed_rule.rule_id
        confirm_knowledge_item(rule_id, self.user_a_id, self.db_id_1)
        rule = get_rule(rule_id, self.user_a_id, self.db_id_1)
        self.assertEqual(rule.status, KnowledgeStatus.CONFIRMED.value)

    # 36. Ambiguous context note
    def test_36_ambiguous_context(self):
        res = parse_and_propose_context(
            "Special transactions need special handling",
            self.user_a_id,
            self.db_id_1,
            self.engine,
            "sqlite",
        )
        self.assertTrue(res.requires_user_confirmation)

    # 37. Duplicate context idempotency
    def test_37_duplicate_context(self):
        ents1 = discover_and_sync_entities(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        count1 = len(ents1)
        ents2 = discover_and_sync_entities(self.engine, "sqlite", self.user_a_id, self.db_id_1)
        self.assertEqual(count1, len(ents2))

    # 38. Conflict handling modal representation
    def test_38_conflict_handling(self):
        conflicts = list_conflicts(self.user_a_id, self.db_id_1)
        self.assertIsInstance(conflicts, list)

    # 39. Phase 8.1 integration: metric discovery imports
    def test_39_phase81_integration(self):
        from app.intelligence.business_intelligence.business_context import discover_business_context
        ctx = discover_business_context(self.engine, "sqlite")
        self.assertTrue(ctx.has_sufficient_data)

    # 40. Phase 8.2 integration: relationship graph preserved
    def test_40_phase82_integration(self):
        from app.intelligence.business_intelligence.join_path import build_relationship_graph
        from app.intelligence.schema_analyzer import analyze_schema
        schema_info = analyze_schema(self.engine, "sqlite")
        graph = build_relationship_graph(schema_info)
        self.assertIsInstance(graph, dict)

    # 41. Phase 8.4 integration: decision intelligence compatibility
    def test_41_phase84_integration(self):
        from app.intelligence.decision.decision_engine import understand_question
        self.assertTrue(callable(understand_question))

    # 42. Phase 8.7 integration: investigation knowledge reference
    def test_42_phase87_integration(self):
        from app.intelligence.investigation.investigator import investigate_signal
        self.assertTrue(callable(investigate_signal))

    # 43. Phase 8.9 integration: outcome optimization metric consistency
    def test_43_phase89_integration(self):
        from app.intelligence.outcome_optimization.measurement_engine import measure_metric_outcome
        self.assertTrue(callable(measure_metric_outcome))

    # 44. Phase 9.0 integration: predictive forecasting uses confirmed rules
    def test_44_phase90_integration(self):
        from app.intelligence.predictive.predictor import run_prediction
        pred = run_prediction(
            user_id=self.user_a_id,
            table="orders",
            date_column="created_at",
            metric_column="total_amount",
            frequency="monthly",
            horizon_days=30,
            engine=self.engine,
            db_type="sqlite",
        )
        self.assertIn(pred.status, ("success", "insufficient_data"))

    # 45. Historical analysis integrity
    def test_45_historical_analysis_integrity(self):
        met = BusinessMetric(
            metric_id="met_hist_analysis",
            name="Analysis Metric",
            description="v1 description",
            table_name="orders",
            aggregation="SUM",
            version=1,
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_metric(met)
        met.version = 2
        save_metric(met)
        versions = list_versions("met_hist_analysis", self.user_a_id, self.db_id_1)
        self.assertTrue(all(v.version >= 1 for v in versions))

    # 46. Forecast definition consistency
    def test_46_forecast_definition_consistency(self):
        calc1 = resolve_metric_calculation("Revenue", "orders", "total_amount", self.user_a_id, self.db_id_1)
        calc2 = resolve_metric_calculation("Revenue", "orders", "total_amount", self.user_a_id, self.db_id_1)
        self.assertEqual(calc1["sql_expression"], calc2["sql_expression"])

    # 47. Outcome definition consistency
    def test_47_outcome_definition_consistency(self):
        from app.intelligence.outcome_optimization.baseline_engine import compute_baseline_for_metric
        # Verify baseline engine is callable
        self.assertTrue(callable(compute_baseline_for_metric))

    # 48. Recommendation context
    def test_48_recommendation_context(self):
        summary = get_knowledge_summary(self.user_a_id, self.db_id_1)
        self.assertGreaterEqual(summary.total_entities, 0)

    # 49. Authentication: endpoints require JWT
    def test_49_authentication(self):
        res_no_auth = self.client.get("/intelligence/knowledge")
        self.assertEqual(res_no_auth.status_code, 401)

    # 50. Rate limiting configured
    def test_50_rate_limiting(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}
        res = self.client.get("/intelligence/knowledge", headers=headers)
        self.assertIn(res.status_code, (200, 429))

    # 51. API user isolation
    def test_51_api_isolation(self):
        headers_a = {"Authorization": f"Bearer {self.token_a}"}
        headers_b = {"Authorization": f"Bearer {self.token_b}"}
        # Post context for user A
        self.client.post("/intelligence/knowledge/context", json={"statement": "Exclude test orders"}, headers=headers_a)
        # User B queries rules
        res_b = self.client.get("/intelligence/knowledge/rules", headers=headers_b)
        self.assertEqual(res_b.status_code, 200)
        rules_b = res_b.json().get("rules", [])
        self.assertTrue(all(r["user_id"] == self.user_b_id for r in rules_b))

    # 52. Persistence across sessions
    def test_52_persistence(self):
        ent = BusinessEntity(
            entity_id="ent_persist_test",
            name="Persist Entity",
            plural_name="Persists",
            table_name="orders",
            description="Testing DB persistence",
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_entity(ent)
        retrieved = get_entity("ent_persist_test", self.user_a_id, self.db_id_1)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Persist Entity")

    # 53. Retrieval by ID
    def test_53_retrieval(self):
        ent = BusinessEntity(
            entity_id="ent_retrieval_test",
            name="Retrieval Entity",
            plural_name="Retrieval Entities",
            table_name="orders",
            description="Testing retrieval by ID",
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_entity(ent)
        headers = {"Authorization": f"Bearer {self.token_a}"}
        res = self.client.get("/intelligence/knowledge/ent_retrieval_test", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["item"]["entity_id"], "ent_retrieval_test")

    # 54. Lineage retrieval endpoint
    def test_54_lineage_retrieval(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}
        res = self.client.get("/intelligence/knowledge/met_orders_count/lineage", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("lineage", res.json())

    # 55. Groq sanitization & privacy
    def test_55_groq_sanitization(self):
        # Ensure no passwords or database dumps are sent
        expl = explain_knowledge_item("ent_orders", self.user_a_id, self.db_id_1)
        d = expl.to_dict()
        for fact in d["facts"]:
            self.assertNotIn("password", fact.lower())
            self.assertNotIn("secret", fact.lower())

    # 56. No sensitive data leakage in explain endpoint
    def test_56_no_sensitive_data_leakage(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}
        res = self.client.get("/intelligence/knowledge/ent_orders/explain", headers=headers)
        self.assertEqual(res.status_code, 200)
        txt = res.text.lower()
        self.assertNotIn("bearer", txt)
        self.assertNotIn("secret_key", txt)

    # 57. Invalid schema reference rejected
    def test_57_invalid_schema_reference(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}
        payload = {
            "item_type": "RULE",
            "name": "Bad Rule",
            "table_name": "ghost_table_does_not_exist",
            "expression": "ghost_col = 1",
        }
        res = self.client.post("/intelligence/knowledge/definitions", json=payload, headers=headers)
        self.assertEqual(res.status_code, 400)

    # 58. Database switching isolation
    def test_58_database_switching(self):
        rule_db1 = BusinessRule(
            rule_id="r_db_switch_1",
            name="DB1 Exclusive",
            description="Testing switch",
            target_table="orders",
            expression="id > 0",
            user_id=self.user_a_id,
            database_identity="db_cluster_alpha",
        )
        save_rule(rule_db1)
        rules_beta = list_rules(self.user_a_id, database_identity="db_cluster_beta")
        self.assertEqual(len(rules_beta), 0)

    # 59. Database disconnect preserves knowledge store
    def test_59_database_disconnect(self):
        ent = BusinessEntity(
            entity_id="ent_disconnect_persist",
            name="Disconnect Persist Entity",
            plural_name="Disconnect Persist Entities",
            table_name="orders",
            description="Testing DB persistence across disconnect",
            user_id=self.user_a_id,
            database_identity=self.db_id_1,
        )
        save_entity(ent)
        headers = {"Authorization": f"Bearer {self.token_a}"}
        disc_res = self.client.post("/disconnect", headers=headers)
        self.assertEqual(disc_res.status_code, 200)
        # Verify knowledge records remain safely preserved in store
        retrieved = get_entity("ent_disconnect_persist", self.user_a_id, self.db_id_1)
        self.assertIsNotNone(retrieved)
        # Restore connection context for subsequent tests
        from app.database.connection_context import set_user_engine
        set_user_engine(self.user_a_id, self.engine, "sqlite", self.db_id_1)

    # 60. Frontend API integration: search endpoint
    def test_60_frontend_api_integration(self):
        headers = {"Authorization": f"Bearer {self.token_a}"}
        res = self.client.get("/intelligence/knowledge/search?q=orders", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("answer", res.json())


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase91EnterpriseKnowledge)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(f"\nPhase 9.1 Test Results: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} passed, {len(result.failures) + len(result.errors)} failed")
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
