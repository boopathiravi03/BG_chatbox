"""
backend/app/intelligence/proactive/__init__.py

Phase 8.3: Proactive Data Intelligence Module
Exports data models and user-isolated alert store operations.
"""
from app.intelligence.proactive.models import (
    MetricSnapshot,
    BusinessAlert,
    AlertRule,
    AlertStatus,
    AlertSeverity,
    AlertCategory,
)
from app.intelligence.proactive.alert_store import (
    save_alert,
    get_alerts,
    get_alert,
    update_alert_status,
    find_active_alert,
    clear_user_alerts,
    set_alert_store_engine,
)

__all__ = [
    "MetricSnapshot",
    "BusinessAlert",
    "AlertRule",
    "AlertStatus",
    "AlertSeverity",
    "AlertCategory",
    "save_alert",
    "get_alerts",
    "get_alert",
    "update_alert_status",
    "find_active_alert",
    "clear_user_alerts",
    "set_alert_store_engine",
]
