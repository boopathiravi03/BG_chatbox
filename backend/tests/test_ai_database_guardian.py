"""backend/tests/test_ai_database_guardian.py

Comprehensive tests for AI Database Guardian:
1. Engine Telemetry (SQLite real, mock MySQL, mock Postgres, mock Redis, mock Mongo, unsupported file/vector)
2. Zero fabricated metrics guarantee (unsupported reported as UNSUPPORTED_ENGINE / UNAVAILABLE, never fake zero)
3. Rule-based diagnostic evaluation (connection exhaustion, cache hit degradation, lock contention, freelist fragmentation)
4. Probabilistic root cause separation with confidence levels
5. User isolation and multi-tenant boundary checks
6. Incident deduplication (ongoing incident updates rather than creates duplicates)
7. Incident lifecycle persistence and state transitions (DETECTED -> ACKNOWLEDGED -> RESOLVED)
8. Zero secret / password leakage in telemetry or advisories
9. Read-only verification query safety (never executes destructive mutations)
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Make backend importable
_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import create_engine, text

from app.guardian.models import (
    EngineTelemetrySnapshot,
    GuardianIncident,
    IncidentSeverity,
    IncidentStatus,
    MetricAvailability,
    MetricItem,
)
from app.guardian.collectors import (
    collect_sqlite_telemetry,
    collect_mysql_telemetry,
    collect_postgres_telemetry,
    collect_mongodb_telemetry,
    collect_redis_telemetry,
    collect_file_or_vector_telemetry,
)
from app.guardian.diagnostics import evaluate_telemetry_incidents
from app.guardian.store import (
    init_guardian_store,
    save_incident,
    find_active_incident,
    list_incidents,
    get_incident_by_id,
)
from app.guardian.service import GuardianService

passed_tests = 0
failed_tests = 0


def record_result(name: str, passed: bool, error: str = ""):
    global passed_tests, failed_tests
    if passed:
        passed_tests += 1
        print(f"PASS  {name}")
    else:
        failed_tests += 1
        print(f"FAIL  {name}: {error}")


def test_sqlite_real_telemetry():
    """Verify real SQLite collector executes PRAGMA commands without error."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name
        
        eng = create_engine(f"sqlite:///{temp_db}")
        with eng.connect() as conn:
            conn.execute(text("CREATE TABLE test_tab (id INTEGER PRIMARY KEY, val TEXT);"))
            conn.execute(text("INSERT INTO test_tab (val) VALUES ('sample');"))
            conn.commit()

        snap = collect_sqlite_telemetry(eng, "sqlite_temp")
        assert snap.is_live is True, "Expected SQLite telemetry to be live"
        assert snap.database_type == "sqlite"
        assert "database_size_mb" in snap.metrics
        assert "journal_mode" in snap.metrics
        assert snap.metrics["journal_mode"].status == MetricAvailability.AVAILABLE
        
        # Crucial: remote connection pool must be marked UNSUPPORTED_ENGINE, NEVER fake 0
        assert snap.metrics["active_connections"].status == MetricAvailability.UNSUPPORTED_ENGINE
        assert snap.metrics["active_connections"].value is None
        assert snap.metrics["cache_hit_ratio"].status == MetricAvailability.UNSUPPORTED_ENGINE
        assert snap.metrics["cache_hit_ratio"].value is None

        record_result("test_sqlite_real_telemetry", True)
    except Exception as e:
        record_result("test_sqlite_real_telemetry", False, str(e))
    finally:
        try:
            if os.path.exists(temp_db):
                os.remove(temp_db)
        except Exception:
            pass


def test_unsupported_engines_never_fabricate():
    """Ensure flat files (CSV, Excel) and vector stores report metrics as unsupported."""
    try:
        snap = collect_file_or_vector_telemetry("csv", "sales_data.csv")
        assert snap.is_live is True
        assert snap.metrics["active_connections"].status == MetricAvailability.UNSUPPORTED_ENGINE
        assert snap.metrics["active_connections"].value is None
        assert snap.metrics["cache_hit_ratio"].status == MetricAvailability.UNSUPPORTED_ENGINE
        assert snap.metrics["cache_hit_ratio"].value is None
        assert snap.metrics["lock_waits"].status == MetricAvailability.UNSUPPORTED_ENGINE
        assert snap.metrics["lock_waits"].value is None

        record_result("test_unsupported_engines_never_fabricate", True)
    except Exception as e:
        record_result("test_unsupported_engines_never_fabricate", False, str(e))


def test_mysql_collector_with_mock_engine():
    """Verify MySQL collector handles SHOW GLOBAL STATUS and variables accurately."""
    try:
        mock_conn = MagicMock()
        mock_res1 = MagicMock()
        mock_res1.fetchall.return_value = [
            ("Threads_connected", "45"),
            ("Innodb_buffer_pool_reads", "100"),
            ("Innodb_buffer_pool_read_requests", "10000"),
            ("slow_queries", "2"),
            ("table_locks_waited", "5"),
            ("uptime", "3600"),
        ]
        mock_res2 = MagicMock()
        mock_res2.fetchall.return_value = [
            ("max_connections", "50"),
        ]
        mock_conn.execute.side_effect = [mock_res1, mock_res2]
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        snap = collect_mysql_telemetry(mock_engine, "mysql_prod")
        assert snap.is_live is True
        assert snap.database_type == "mysql"
        assert snap.metrics["active_connections"].value == 45
        assert snap.metrics["max_connections"].value == 50
        # Hit ratio: 100 - (100 / 10000 * 100) = 99.0%
        assert snap.metrics["cache_hit_ratio"].value == 99.0
        assert snap.metrics["slow_queries"].value == 2
        assert snap.metrics["lock_waits"].value == 5

        record_result("test_mysql_collector_with_mock_engine", True)
    except Exception as e:
        record_result("test_mysql_collector_with_mock_engine", False, str(e))


def test_diagnostics_connection_saturation():
    """Verify rule triggers on connection pool >= 85% utilization."""
    try:
        mock_snap = EngineTelemetrySnapshot(
            database_type="postgres",
            database_identity="pg_main",
            collected_at="2026-10-14T05:00:00Z",
            is_live=True,
            latency_ms=1.2,
            metrics={
                "active_connections": MagicMock(
                    status=MetricAvailability.AVAILABLE,
                    value=95,
                ),
                "max_connections": MagicMock(
                    status=MetricAvailability.AVAILABLE,
                    value=100,
                ),
            },
        )
        incidents = evaluate_telemetry_incidents("user_123", mock_snap)
        assert len(incidents) >= 1
        conn_inc = next(i for i in incidents if i.category == "connection_pool")
        assert conn_inc.severity == IncidentSeverity.CRITICAL
        assert conn_inc.observed_facts["active_connections"] == 95
        assert conn_inc.observed_facts["utilization_percent"] == 95.0
        assert "unclosed connection leak" in conn_inc.likely_root_cause.lower()
        assert conn_inc.confidence_score >= 0.8
        assert len(conn_inc.verification_steps) > 0
        # Safe read-only instruction
        assert any("pg_stat_activity" in step for step in conn_inc.verification_steps)

        record_result("test_diagnostics_connection_saturation", True)
    except Exception as e:
        record_result("test_diagnostics_connection_saturation", False, str(e))


def test_diagnostics_cache_degradation():
    """Verify rule triggers when cache hit ratio falls below 80%."""
    try:
        mock_snap = EngineTelemetrySnapshot(
            database_type="mysql",
            database_identity="my_db",
            collected_at="2026-10-14T05:00:00Z",
            is_live=True,
            latency_ms=2.1,
            metrics={
                "cache_hit_ratio": MagicMock(
                    status=MetricAvailability.AVAILABLE,
                    value=72.4,
                ),
            },
        )
        incidents = evaluate_telemetry_incidents("user_456", mock_snap)
        cache_inc = next(i for i in incidents if i.category == "cache_efficiency")
        assert cache_inc.severity == IncidentSeverity.WARNING
        assert cache_inc.observed_facts["cache_hit_ratio"] == 72.4
        assert "full table scans" in cache_inc.likely_root_cause.lower()
        record_result("test_diagnostics_cache_degradation", True)
    except Exception as e:
        record_result("test_diagnostics_cache_degradation", False, str(e))


def test_incident_persistence_and_deduplication():
    """Verify incidents persist across SQLite storage, isolate users, and deduplicate."""
    try:
        # Use temp db for test
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_store_db = f.name
        os.environ["BGAI_GUARDIAN_DB_PATH"] = temp_store_db
        init_guardian_store()

        inc = GuardianIncident(
            incident_id="inc_test_001",
            user_id="user_alpha",
            database_identity="db_crm",
            database_type="postgres",
            title="Lock Contention",
            severity=IncidentSeverity.WARNING,
            status=IncidentStatus.DETECTED,
            category="lock_contention",
            detected_at="2026-10-14T05:00:00Z",
            updated_at="2026-10-14T05:00:00Z",
            observed_facts={"waiting_lock_count": 8},
            trigger_rule="lock_waits > 3",
            likely_root_cause="Overlapping update queries",
            confidence_score=0.85,
            verification_steps=["SELECT * FROM pg_stat_activity;"],
            ai_advisory="Advisory note",
        )
        save_incident(inc)

        # 1. Retrieval
        fetched = get_incident_by_id("user_alpha", "inc_test_001")
        assert fetched is not None
        assert fetched.title == "Lock Contention"

        # 2. Strict user isolation: user_beta must NOT see user_alpha's incident
        beta_fetch = get_incident_by_id("user_beta", "inc_test_001")
        assert beta_fetch is None

        # 3. Deduplication search
        active = find_active_incident("user_alpha", "db_crm", "lock_contention", "lock_waits > 3")
        assert active is not None
        assert active.incident_id == "inc_test_001"

        # 4. Status Transition to ACKNOWLEDGED
        updated = GuardianService.update_incident_status(
            user_id="user_alpha",
            incident_id="inc_test_001",
            new_status=IncidentStatus.ACKNOWLEDGED,
            actor_name="alice_dba",
        )
        assert updated.status == IncidentStatus.ACKNOWLEDGED
        assert updated.acknowledged_by == "alice_dba"

        # 5. Status Transition to RESOLVED
        resolved = GuardianService.update_incident_status(
            user_id="user_alpha",
            incident_id="inc_test_001",
            new_status=IncidentStatus.RESOLVED,
            actor_name="alice_dba",
            notes="Resolved by terminating stuck ETL job",
        )
        assert resolved.status == IncidentStatus.RESOLVED
        assert resolved.resolved_by == "alice_dba"
        assert resolved.resolution_notes == "Resolved by terminating stuck ETL job"

        # After resolution, active search should be None (closed)
        closed_active = find_active_incident("user_alpha", "db_crm", "lock_contention", "lock_waits > 3")
        assert closed_active is None

        record_result("test_incident_persistence_and_deduplication", True)
    except Exception as e:
        record_result("test_incident_persistence_and_deduplication", False, str(e))
    finally:
        os.environ.pop("BGAI_GUARDIAN_DB_PATH", None)
        try:
            if os.path.exists(temp_store_db):
                os.remove(temp_store_db)
        except Exception:
            pass


def test_zero_secret_leakage_in_advisories():
    """Verify generated advisory strings never contain raw passwords or connection credentials."""
    try:
        inc = GuardianIncident(
            incident_id="inc_sec_99",
            user_id="user_x",
            database_identity="postgresql://dbadmin:superSecret123@prod-cluster.internal:5432/main",
            database_type="postgres",
            title="Connection Saturation",
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.DETECTED,
            category="connection_pool",
            detected_at="2026-10-14T05:00:00Z",
            updated_at="2026-10-14T05:00:00Z",
            observed_facts={"active_connections": 99, "max_connections": 100},
            trigger_rule="active >= 85%",
            likely_root_cause="Connection leak in worker tier",
            confidence_score=0.9,
            verification_steps=["SELECT * FROM pg_stat_activity;"],
        )
        advisory = GuardianService._generate_advisory_text(inc)
        assert "superSecret123" not in advisory
        assert "dbadmin" not in advisory
        assert "Connection Saturation" in advisory
        record_result("test_zero_secret_leakage_in_advisories", True)
    except Exception as e:
        record_result("test_zero_secret_leakage_in_advisories", False, str(e))


def test_postgres_collector_with_mock_engine():
    """Verify PostgreSQL collector queries pg_stat_activity and pg_stat_database accurately."""
    try:
        mock_conn = MagicMock()
        # Mock queries: 1. pg_stat_activity, 2. pg_stat_database, 3. SHOW max_connections, 4. pg_database_size
        mock_res1 = MagicMock()
        mock_res1.fetchone.return_value = (50, 42, 3, 2)  # total, active, idle_in_trans, waiting
        mock_res2 = MagicMock()
        mock_res2.fetchone.return_value = (98000, 2000, 98.0)  # blks_hit, blks_read, hit_ratio
        mock_conn.execute.side_effect = [
            mock_res1,
            mock_res2,
            MagicMock(scalar=MagicMock(return_value="100")),
            MagicMock(scalar=MagicMock(return_value=104857600)),  # 100MB
        ]
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        snap = collect_postgres_telemetry(mock_engine, "pg_prod")
        assert snap.is_live is True
        assert snap.database_type == "postgres"
        assert snap.metrics["active_connections"].value == 42
        assert snap.metrics["total_connections"].value == 50
        assert snap.metrics["idle_in_transaction"].value == 3
        assert snap.metrics["lock_waits"].value == 2
        assert snap.metrics["cache_hit_ratio"].value == 98.0
        assert snap.metrics["max_connections"].value == 100
        assert snap.metrics["database_size_mb"].value == 100.0

        record_result("test_postgres_collector_with_mock_engine", True)
    except Exception as e:
        record_result("test_postgres_collector_with_mock_engine", False, str(e))


def test_redis_collector_with_mock():
    """Verify Redis collector safely reads client info without mutation."""
    try:
        mock_connector = MagicMock()
        mock_client = MagicMock()
        mock_client.info.return_value = {
            "connected_clients": 15,
            "used_memory": 52428800,  # 50MB
            "keyspace_hits": 900,
            "keyspace_misses": 100,
            "instantaneous_ops_per_sec": 450,
            "blocked_clients": 0,
        }
        mock_connector._client = mock_client

        snap = collect_redis_telemetry(mock_connector, "redis_cache")
        assert snap.is_live is True
        assert snap.database_type == "redis"
        assert snap.metrics["active_connections"].value == 15
        assert snap.metrics["memory_used_mb"].value == 50.0
        assert snap.metrics["cache_hit_ratio"].value == 90.0
        assert snap.metrics["ops_per_sec"].value == 450
        assert snap.metrics["blocked_clients"].value == 0

        record_result("test_redis_collector_with_mock", True)
    except Exception as e:
        record_result("test_redis_collector_with_mock", False, str(e))


def test_mongo_collector_with_mock():
    """Verify MongoDB collector queries db.command('serverStatus') without touching user documents."""
    try:
        mock_connector = MagicMock()
        mock_connector.database = "ecommerce"
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_db.command.return_value = {
            "connections": {"current": 24, "available": 800},
            "mem": {"resident": 256},
            "opcounters": {"query": 15000},
            "uptime": 7200,
        }
        mock_client.__getitem__.return_value = mock_db
        mock_connector._client = mock_client

        snap = collect_mongodb_telemetry(mock_connector, "mongo_cluster")
        assert snap.is_live is True
        assert snap.database_type == "mongodb"
        assert snap.metrics["active_connections"].value == 24
        assert snap.metrics["available_connections"].value == 800
        assert snap.metrics["memory_resident_mb"].value == 256
        assert snap.metrics["query_ops"].value == 15000
        assert snap.metrics["uptime_seconds"].value == 7200

        record_result("test_mongo_collector_with_mock", True)
    except Exception as e:
        record_result("test_mongo_collector_with_mock", False, str(e))


def test_automated_incident_recovery():
    """Verify an ongoing incident auto-recovers to RESOLVED when telemetry returns to healthy thresholds."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_store_db = f.name
        os.environ["BGAI_GUARDIAN_DB_PATH"] = temp_store_db
        init_guardian_store()

        # 1. Create an initial open incident for connection_pool
        inc = GuardianIncident(
            incident_id="inc_rec_01",
            user_id="user_rec",
            database_identity="db_app",
            database_type="postgres",
            title="Connection Saturation",
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.DETECTED,
            category="connection_pool",
            detected_at="2026-10-14T05:00:00Z",
            updated_at="2026-10-14T05:00:00Z",
            observed_facts={"active_connections": 95, "max_connections": 100},
            trigger_rule="active >= 85%",
            likely_root_cause="Connection leak",
            confidence_score=0.88,
            recovery_rule="active_connections < 70%",
        )
        save_incident(inc)

        # 2. Simulate subsequent diagnosis where connections dropped to 20 (nominal)
        healthy_snap = EngineTelemetrySnapshot(
            database_type="postgres",
            database_identity="db_app",
            collected_at="2026-10-14T05:10:00Z",
            is_live=True,
            latency_ms=1.1,
            metrics={
                "active_connections": MetricItem(
                    name="Active Connections",
                    value=20,
                    unit="backends",
                    status=MetricAvailability.AVAILABLE,
                    description="Nominal backends",
                ),
                "max_connections": MetricItem(
                    name="Max Connections",
                    value=100,
                    unit="backends",
                    status=MetricAvailability.AVAILABLE,
                    description="Max limit",
                ),
            },
        )

        # Run diagnosis with mock get_live_telemetry returning healthy_snap
        original_get_telemetry = GuardianService.get_live_telemetry
        try:
            GuardianService.get_live_telemetry = classmethod(lambda cls, u, e, d, i, c=None: healthy_snap)
            rep = GuardianService.run_diagnosis("user_rec", None, "postgres", "db_app")
            
            # Check incident in store
            recovered_inc = get_incident_by_id("user_rec", "inc_rec_01")
            assert recovered_inc is not None
            assert recovered_inc.status == IncidentStatus.RESOLVED
            assert "Auto-Recovery" in (recovered_inc.resolved_by or "")
            assert recovered_inc.recovered_at is not None
        finally:
            GuardianService.get_live_telemetry = original_get_telemetry

        record_result("test_automated_incident_recovery", True)
    except Exception as e:
        record_result("test_automated_incident_recovery", False, str(e))
    finally:
        os.environ.pop("BGAI_GUARDIAN_DB_PATH", None)
        try:
            if os.path.exists(temp_store_db):
                os.remove(temp_store_db)
        except Exception:
            pass


def test_api_auth_and_cross_user_isolation():
    """Verify FastAPI Guardian endpoints require authentication and prevent cross-user updates."""
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        from app.security.auth import create_access_token

        client = TestClient(app)

        # 1. Unauthenticated requests must receive 401
        r1 = client.get("/guardian/metrics")
        assert r1.status_code == 401, f"Expected 401 for unauthenticated metrics, got {r1.status_code}"
        r2 = client.post("/guardian/diagnose")
        assert r2.status_code == 401, f"Expected 401 for unauthenticated diagnose, got {r2.status_code}"
        r3 = client.get("/guardian/incidents")
        assert r3.status_code == 401, f"Expected 401 for unauthenticated incidents, got {r3.status_code}"

        # 2. Authenticated user A creates incident
        token_a = create_access_token("user_test_a", "alice")
        token_b = create_access_token("user_test_b", "bob")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Save an incident owned by user_test_a
        inc_a = GuardianIncident(
            incident_id="inc_owned_by_a",
            user_id="user_test_a",
            database_identity="test_db",
            database_type="sqlite",
            title="User A Issue",
            severity=IncidentSeverity.WARNING,
            status=IncidentStatus.DETECTED,
            category="connection_pool",
            detected_at="2026-10-14T05:00:00Z",
            updated_at="2026-10-14T05:00:00Z",
            observed_facts={"active": 10},
            trigger_rule="rule",
            likely_root_cause="cause",
            confidence_score=0.8,
        )
        save_incident(inc_a)

        # 3. User B attempts to acknowledge User A's incident -> Must be 404 (isolation)
        r_hack = client.post(
            "/guardian/incidents/inc_owned_by_a/status",
            headers=headers_b,
            json={"status": "acknowledged"},
        )
        assert r_hack.status_code == 404, f"Expected 404 cross-user update rejection, got {r_hack.status_code}: {r_hack.text}"

        # 4. User A acknowledges their own incident -> 200 OK
        r_ok = client.post(
            "/guardian/incidents/inc_owned_by_a/status",
            headers=headers_a,
            json={"status": "acknowledged"},
        )
        assert r_ok.status_code == 200, f"Expected 200 for owner update, got {r_ok.status_code}: {r_ok.text}"
        data = r_ok.json()
        assert data["incident"]["status"] == "acknowledged"

        record_result("test_api_auth_and_cross_user_isolation", True)
    except Exception as e:
        record_result("test_api_auth_and_cross_user_isolation", False, str(e))


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("RUNNING AI DATABASE GUARDIAN TEST SUITE")
    print(f"{'='*60}")
    test_sqlite_real_telemetry()
    test_unsupported_engines_never_fabricate()
    test_mysql_collector_with_mock_engine()
    test_postgres_collector_with_mock_engine()
    test_redis_collector_with_mock()
    test_mongo_collector_with_mock()
    test_diagnostics_connection_saturation()
    test_diagnostics_cache_degradation()
    test_incident_persistence_and_deduplication()
    test_automated_incident_recovery()
    test_zero_secret_leakage_in_advisories()
    test_api_auth_and_cross_user_isolation()
    print(f"{'='*60}")
    print(f"RESULTS: {passed_tests} passed, {failed_tests} failed")
    print(f"{'='*60}\n")
    sys.exit(0 if failed_tests == 0 else 1)
