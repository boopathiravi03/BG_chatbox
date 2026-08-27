from app.database.database_manager import (
    get_engine,
    get_current_db_type,
)
from app.tools.analyze_database import analyze_database

_current_profile = None


def refresh_database_profile():
    global _current_profile

    engine = get_engine()

    if engine is None:
        _current_profile = None
        return None

    profile = analyze_database()
    profile.database_type = get_current_db_type()
    profile.analyzed = True

    _current_profile = profile

    return profile


def get_database_profile():
    return _current_profile


def clear_database_profile():
    global _current_profile
    _current_profile = None
