from sqlalchemy import create_engine, URL, text


# ============================================================
# ACTIVE DATABASE STATE
# ============================================================

current_db_type = "none"
engine = None


# ============================================================
# SQLITE
# ============================================================

def connect_sqlite(path: str):
    """
    Connect to the SQLite database selected by the user.
    """
    global current_db_type, engine

    disconnect_database(clear_profile=False)

    new_engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

    try:
        with new_engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        engine = new_engine
        current_db_type = "sqlite"

        return engine

    except Exception:
        try:
            new_engine.dispose()
        except Exception:
            pass

        engine = None
        current_db_type = "none"
        raise


# ============================================================
# MYSQL
# ============================================================

def connect_mysql(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
):
    """
    Connect to the MySQL database selected by the user.
    """

    global current_db_type, engine

    disconnect_database(clear_profile=False)

    mysql_url = URL.create(
        drivername="mysql+pymysql",
        username=username,
        password=password,
        host=host,
        port=int(port),
        database=database,
    )

    new_engine = create_engine(
        mysql_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

    try:
        with new_engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")

        engine = new_engine
        current_db_type = "mysql"

        return engine

    except Exception:
        try:
            new_engine.dispose()
        except Exception:
            pass

        engine = None
        current_db_type = "none"
        raise


# ============================================================
# POSTGRESQL
# ============================================================

def connect_postgres(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
):
    """
    Connect to the PostgreSQL database selected by the user.
    """

    global current_db_type, engine

    disconnect_database(clear_profile=False)

    postgres_url = URL.create(
        drivername="postgresql+psycopg2",
        username=username,
        password=password,
        host=host,
        port=int(port),
        database=database,
    )

    new_engine = create_engine(
        postgres_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

    try:
        with new_engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")

        engine = new_engine
        current_db_type = "postgres"

        return engine

    except Exception:
        try:
            new_engine.dispose()
        except Exception:
            pass

        engine = None
        current_db_type = "none"
        raise


# ============================================================
# DISCONNECT
# ============================================================

def disconnect_database(clear_profile=True):
    """
    Completely remove the active database connection.
    """

    global engine, current_db_type

    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            pass

    engine = None
    current_db_type = "none"

    if clear_profile:
        try:
            from app.database.database_context import clear_database_profile
            clear_database_profile()
        except Exception:
            pass


# ============================================================
# CURRENT DATABASE TYPE
# ============================================================

def get_current_db_type():
    try:
        from app.database.connection_context import get_request_db_type, get_request_user_id
        if get_request_user_id() is not None:
            return get_request_db_type()
        req_type = get_request_db_type()
        if req_type and req_type != "none":
            return req_type
    except Exception:
        pass
    return current_db_type


# ============================================================
# CURRENT ENGINE
# ============================================================

def get_engine():
    """
    ALWAYS return the currently connected database engine.
    In Phase 7, checks the user's isolated request context first.
    """
    try:
        from app.database.connection_context import get_request_engine, get_request_user_id
        if get_request_user_id() is not None:
            return get_request_engine()
        req_engine = get_request_engine()
        if req_engine is not None:
            return req_engine
    except Exception:
        pass

    return engine



# ============================================================
# CONNECTION STATUS
# ============================================================

def is_database_connected():
    return engine is not None


# ============================================================
# DATABASE CONNECTION INFORMATION
# ============================================================

def get_database_connection_info():
    active_eng = get_engine()
    active_type = get_current_db_type()

    if active_eng is None or active_type == "none":
        return {
            "connected": False,
            "db_type": "none",
        }

    try:
        url = active_eng.url

        return {
            "connected": True,
            "db_type": active_type,
            "host": url.host,
            "port": url.port,
            "database": url.database,
            "username": url.username,
            "driver": url.drivername,
        }

    except Exception as e:

        return {
            "connected": True,
            "db_type": active_type,
            "error": str(e),
        }


# ============================================================
# TEST ACTIVE CONNECTION
# ============================================================

def test_active_connection():
    active_eng = get_engine()
    active_type = get_current_db_type()

    if active_eng is None or active_type == "none":
        return {
            "connected": False,
            "db_type": "none",
            "message": "No database connected.",
        }

    try:

        with active_eng.connect() as conn:
            conn.execute(text("SELECT 1"))

        return {
            "connected": True,
            "db_type": active_type,
            "message": "Database connection is active.",
        }

    except Exception as e:

        return {
            "connected": False,
            "db_type": current_db_type,
            "message": str(e),
        }
