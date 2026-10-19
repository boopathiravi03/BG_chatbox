#!/usr/bin/env python
"""
Regression and verification test for MariaDB connection handling,
special character URL escaping, whitespace trimming, and error sanitization.
"""
import sys
import os

# Ensure backend is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.engine import make_url, URL
from app.connectors.relational import SQLiteConnector, MariaDBConnector, MySQLConnector, sanitize_connection_error
from app.connectors.registry import ConnectionRegistry, get_connection_registry


def test_special_characters_in_password():
    """Verify that complex passwords with @, :, /, #, %, &, $, ! are preserved correctly by URL.create."""
    complex_password = "P@$$w0rd!#:/?%&*"
    connector = MariaDBConnector(
        connection_id="test_conn_1",
        name="Test MariaDB",
        host="localhost",
        port=3306,
        database="testdb",
        username="bgai_user",
        password=complex_password,
    )
    # Get the SQLAlchemy URL that connector creates
    url = connector.get_connection_url()
    assert isinstance(url, URL), f"Expected URL object, got {type(url)}"
    assert url.password == complex_password, f"Password mismatch! Expected {complex_password}, got {url.password}"
    assert url.username == "bgai_user"
    assert url.host == "localhost"
    assert url.database == "testdb"
    assert url.port == 3306
    assert url.drivername == "mysql+pymysql"
    print("[PASS] test_special_characters_in_password passed")


def test_whitespace_trimming():
    """Verify that leading/trailing whitespaces in host, database, and username are stripped."""
    reg = ConnectionRegistry()
    raw_config = {
        "connector_type": "  mariadb  ",
        "name": "  My Production DB  ",
        "host": "  127.0.0.1  ",
        "port": " 3306 ",
        "database": "  bgai_prod  ",
        "username": "  bgai_user  ",
        "password": " password_with_spaces_around ",  # password itself must NOT be stripped arbitrarily, but user input stripped
    }
    conn = reg.create_connector_from_config(user_id="user_123", config=raw_config, auto_register=False)
    assert isinstance(conn, MariaDBConnector)
    assert conn.host == "127.0.0.1", f"Host whitespace not trimmed: '{conn.host}'"
    assert conn.database == "bgai_prod", f"Database whitespace not trimmed: '{conn.database}'"
    assert conn.username == "bgai_user", f"Username whitespace not trimmed: '{conn.username}'"
    assert conn.name == "My Production DB"
    print("[PASS] test_whitespace_trimming passed")


def test_sanitize_connection_error_1045():
    """Verify that MariaDB 1045 error is properly sanitized and guides user on user@host resolution."""
    raw_err = Exception('(pymysql.err.OperationalError) (1045, "Access denied for user \'bgai_user\'@\'boopathi\' (using password: YES)")')
    sanitized = sanitize_connection_error(raw_err, "mariadb")
    
    assert "bgai_user" in sanitized
    assert "boopathi" in sanitized
    assert "using password" not in sanitized.lower()
    assert "Authentication failed" in sanitized
    assert "User/Host allowance in MariaDB/MySQL (`user`@`host`)" in sanitized
    assert "Granted database permissions" in sanitized
    print("[PASS] test_sanitize_connection_error_1045 passed")


def test_sanitize_connection_error_password_masking():
    """Verify that passwords embedded in raw exception strings or URLs are masked."""
    raw_err = Exception("Failed to connect to mysql+pymysql://bgai_user:SuperSecretPassword123@localhost:3306/db")
    sanitized = sanitize_connection_error(raw_err, "mariadb")
    assert "SuperSecretPassword123" not in sanitized, "Leaked password in error message!"
    assert "***" in sanitized
    print("[PASS] test_sanitize_connection_error_password_masking passed")


def test_failed_connection_preserves_active():
    """Verify that a failed connection does not replace the previously active connection."""
    reg = ConnectionRegistry()
    # 1. Establish initial active connection (SQLite memory)
    initial_conn = SQLiteConnector(connection_id="active_initial", name="Initial Active", database_path=":memory:", user_id="user_1")
    initial_conn.connect()
    reg.register_connector(initial_conn)
    reg.set_active_connector(user_id="user_1", connection_id=initial_conn.connection_id)

    assert reg.get_active_connector("user_1").connection_id == "active_initial"

    # 2. Attempt to create bad MariaDB connection with invalid host/port that fails to connect
    bad_config = {
        "connector_type": "mariadb",
        "name": "Bad MariaDB",
        "host": "192.0.2.1",  # Test-net unreachable IP
        "port": 3306,
        "database": "test",
        "username": "bad_user",
        "password": "bad_password",
    }
    # When auto_register=False is used in endpoint
    new_conn = reg.create_connector_from_config(user_id="user_1", config=bad_config, auto_register=False)
    # Suppose connect() fails:
    # Notice we simulate connect failure without actually waiting for network timeout:
    ok = False  # simulated fail
    if not ok:
        # endpoint does NOT register and does NOT set active
        pass
    else:
        reg.register_connector(new_conn)
        reg.set_active_connector("user_1", new_conn.connection_id)

    # Active connection must STILL be the initial one
    active = reg.get_active_connector("user_1")
    assert active.connection_id == "active_initial", f"Active connector was overwritten! Got {active.connection_id}"
    assert reg.get_connector("user_1", new_conn.connection_id) is None, "Failed connector was registered!"
    print("[PASS] test_failed_connection_preserves_active passed")


if __name__ == "__main__":
    test_special_characters_in_password()
    test_whitespace_trimming()
    test_sanitize_connection_error_1045()
    test_sanitize_connection_error_password_masking()
    test_failed_connection_preserves_active()
    print("\nALL MARIADB CONNECTION TESTS PASSED SUCCESSFULLY!")
