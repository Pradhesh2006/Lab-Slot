"""LabSlot user store: SQLite with salted + hashed passwords.

Password hashing itself (werkzeug.security) is done by the caller (app.py);
this module only stores and fetches the resulting hash.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_db_path():
    path = os.environ.get("DATABASE_PATH", "labslot.db")
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


@contextmanager
def get_connection():
    """Open a connection with a 20 s lock timeout; always commit/rollback and close."""
    conn = sqlite3.connect(get_db_path(), timeout=20.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create the users table if it does not exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def add_user(username, password_hash, email):
    """Insert a user. Returns the new user id, or None if the username is taken."""
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, email, created_at) VALUES (?, ?, ?, ?)",
                (username, password_hash, email, created_at),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user(username):
    """Return the user row (sqlite3.Row) for a username, or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, username, password_hash, email, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()


if __name__ == "__main__":
    init_db()
    print(f"LabSlot database initialised at {get_db_path()}")
