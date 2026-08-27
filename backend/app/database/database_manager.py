from sqlalchemy import create_engine, URL, text

current_db_type = "none"
engine = None


def connect_sqlite(path: str):
    """
    Explicitly connect to a SQLite database selected by the user.
    """
    global current_db_type, engine

    disconnect_database()

    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        current_db_type = "sqlite"
        return engine

    except Exception:
        disconnect_database()
        raise


def connect_mysql(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
):
    """
    Connect to the MySQL database explicitly selected by the user.
    """
    global current_db_type, engine

    disconnect_database()

    mysql_url = URL.create(
        drivername="mysql+pymysql",
        username=username,
        password=password,
        host=host,
        port=int(port),
        database=database,
    )

    engine = create_engine(
        mysql_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")

        current_db_type = "mysql"
        return engine

    except Exception:
        disconnect_database()
        raise


def connect_postgres(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
):
    """
    Connect to the PostgreSQL database explicitly selected by the user.
    """
    global current_db_type, engine

    disconnect_database()

    postgres_url = URL.create(
        drivername="postgresql+psycopg2",
        username=username,
        password=password,
        host=host,
        port=int(port),
        database=database,
    )

    engine = create_engine(
        postgres_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")

        current_db_type = "postgres"
        return engine

    except Exception:
        disconnect_database()
        raise


def disconnect_database():
    """
    Completely remove the current database connection
    and clear the associated database analysis.
    """
    global engine, current_db_type

    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            pass

    engine = None
    current_db_type = "none"

    try:
        from app.database.database_context import clear_database_profile
        clear_database_profile()
    except Exception:
        pass


def get_current_db_type():
    return current_db_type


def get_engine():
    if engine is None:
        return None

    return engine


def get_database_connection_info():
    global engine, current_db_type

    if engine is None:
        return {
            "connected": False,
            "db_type": "none",
        }

    try:
        url = engine.url

        return {
            "connected": True,
            "db_type": current_db_type,
            "host": url.host,
            "port": url.port,
            "database": url.database,
            "username": url.username,
        }
    except Exception:
        return {
            "connected": True,
            "db_type": current_db_type,
        }
