from sqlalchemy import create_engine

engine = None
current_db_type = "sqlite"


def connect_sqlite(path: str):
    global engine, current_db_type
    current_db_type = "sqlite"
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False}
    )


def connect_mysql(host: str, port: int, database: str, username: str, password: str):
    global engine, current_db_type
    current_db_type = "mysql"
    engine = create_engine(
        f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
    )


def connect_postgres(host: str, port: int, database: str, username: str, password: str):
    global engine, current_db_type
    current_db_type = "postgres"
    engine = create_engine(
        f"postgresql://{username}:{password}@{host}:{port}/{database}"
    )


def get_engine():
    return engine


def get_current_db_type():
    return current_db_type
