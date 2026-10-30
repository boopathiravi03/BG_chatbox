"""backend/app/intelligence/monitoring/scheduler.py

Resilient background scheduler for Sprint 2 Autonomous Business Intelligence & Monitoring.
Maintains persistent schedule configurations across server restarts,
prevents overlapping jobs, enforces user isolation, and coordinates recurring health scans.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from app.intelligence.monitoring.baseline_store import (
    save_schedule_config,
    get_schedule_config,
    list_active_schedules,
    update_schedule_execution_state,
    claim_schedule_execution,
)
from app.intelligence.monitoring.quality_monitor import run_database_health_monitoring

logger = logging.getLogger("bgai.monitoring.scheduler")

_scheduler_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_scheduler_lock = threading.Lock()


def configure_schedule(
    user_id: str,
    connection_id: str,
    interval_minutes: int = 60,
    is_enabled: bool = True,
) -> Dict[str, Any]:
    """
    Configures, enables, or adjusts the schedule interval for an authorized connection.
    """
    res = save_schedule_config(
        user_id=user_id,
        connection_id=connection_id,
        interval_minutes=max(1, interval_minutes),
        is_enabled=is_enabled,
        status="idle" if is_enabled else "paused",
    )
    # Ensure background runner is active
    start_monitoring_scheduler()
    return res


def pause_schedule(user_id: str, connection_id: str) -> Optional[Dict[str, Any]]:
    """Pauses monitoring for a specific user connection."""
    cfg = get_schedule_config(user_id, connection_id)
    if not cfg:
        return None
    return save_schedule_config(
        user_id=user_id,
        connection_id=connection_id,
        interval_minutes=cfg["interval_minutes"],
        is_enabled=False,
        status="paused",
    )


def resume_schedule(user_id: str, connection_id: str) -> Optional[Dict[str, Any]]:
    """Resumes monitoring for a specific user connection."""
    cfg = get_schedule_config(user_id, connection_id)
    if not cfg:
        return None
    res = save_schedule_config(
        user_id=user_id,
        connection_id=connection_id,
        interval_minutes=cfg["interval_minutes"],
        is_enabled=True,
        status="idle",
    )
    start_monitoring_scheduler()
    return res


def trigger_immediate_scan(user_id: str, connection_id: str) -> Dict[str, Any]:
    """Manually triggers an immediate monitoring scan for an authorized connection."""
    now = datetime.now(timezone.utc)
    res = run_database_health_monitoring(user_id=user_id, connection_id=connection_id, manual=True)

    # Update schedule execution state if scheduled
    cfg = get_schedule_config(user_id, connection_id)
    if cfg and cfg.get("is_enabled"):
        next_run = now + timedelta(minutes=cfg["interval_minutes"])
        update_schedule_execution_state(
            user_id=user_id,
            connection_id=connection_id,
            status="idle",
            last_run_at=now,
            next_run_at=next_run,
        )

    return res


def get_schedule_status(user_id: str, connection_id: str) -> Dict[str, Any]:
    """Returns current schedule status or default idle config."""
    cfg = get_schedule_config(user_id, connection_id)
    if not cfg:
        return {
            "user_id": user_id,
            "connection_id": connection_id,
            "interval_minutes": 60,
            "is_enabled": False,
            "status": "not_configured",
            "last_run_at": None,
            "next_run_at": None,
        }
    return cfg


def _scheduler_loop() -> None:
    """Background daemon loop that executes due monitoring scans."""
    logger.info("BG AI autonomous monitoring scheduler loop started.")
    while not _stop_event.is_set():
        try:
            now = datetime.now(timezone.utc)
            active_schedules = list_active_schedules()

            for item in active_schedules:
                uid = item["user_id"]
                cid = item["connection_id"]
                interval = item["interval_minutes"]
                last_run = item.get("last_run_at")
                next_run = item.get("next_run_at")

                is_due = False
                if next_run is None:
                    is_due = True
                else:
                    # Normalize next_run timezone if naive
                    if next_run.tzinfo is None:
                        next_run = next_run.replace(tzinfo=timezone.utc)
                    if now >= next_run:
                        is_due = True

                if is_due:
                    # Atomic claim to prevent multi-worker concurrency
                    if not claim_schedule_execution(uid, cid, lease_minutes=5):
                        continue

                    logger.info(f"Executing scheduled monitoring scan for user='{uid}' conn='{cid}'.")
                    try:
                        run_database_health_monitoring(user_id=uid, connection_id=cid, manual=False)
                        new_next_run = now + timedelta(minutes=interval)
                        update_schedule_execution_state(
                            uid, cid, status="idle", last_run_at=now, next_run_at=new_next_run
                        )
                    except Exception as scan_err:
                        logger.error(f"Scheduled scan failed for conn='{cid}': {scan_err}", exc_info=True)
                        new_next_run = now + timedelta(minutes=interval)
                        update_schedule_execution_state(
                            uid, cid, status="error", last_run_at=now, next_run_at=new_next_run, error=str(scan_err)
                        )

        except Exception as loop_err:
            logger.error(f"Error in monitoring scheduler loop: {loop_err}", exc_info=True)

        # Sleep in small slices to respond promptly to stop events
        for _ in range(30):
            if _stop_event.is_set():
                break
            time.sleep(1)

    logger.info("BG AI autonomous monitoring scheduler loop stopped.")


def start_monitoring_scheduler() -> None:
    """Starts the background scheduler thread if not already running."""
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread is None or not _scheduler_thread.is_alive():
            _stop_event.clear()
            _scheduler_thread = threading.Thread(
                target=_scheduler_loop,
                name="BGAI-MonitoringScheduler",
                daemon=True,
            )
            _scheduler_thread.start()


def stop_monitoring_scheduler() -> None:
    """Signals the scheduler daemon to shut down."""
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            _stop_event.set()
            _scheduler_thread.join(timeout=2.0)
            _scheduler_thread = None
