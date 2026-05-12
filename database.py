"""
database.py
-----------
Handles everything that touches the SQLite database file.

Why SQLite?
  - Built into Python (no install needed)
  - Stored as a single file (matrix_app.db) — easy to share, easy to reset
  - Perfect for school projects

If your DB groupmate wants to switch to MySQL/PostgreSQL later, they only
need to change THIS file. All other files call functions from here, so the
rest of the project won't care which database is underneath.
"""

import sqlite3
import json
from datetime import datetime

# Name of the SQLite file (created automatically on first run)
DATABASE_FILE = "matrix_app.db"


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------
def get_connection():
    """
    Open a new connection to the database.

    `row_factory = sqlite3.Row` lets us access columns by name like a dict
    (e.g. row['email']) instead of by index (row[1]) — much more readable.
    """
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


# ---------------------------------------------------------------------------
# Initial setup — creates tables if they don't exist yet
# ---------------------------------------------------------------------------
def init_database():
    """
    Create the tables we need, but only if they don't already exist.
    Safe to call every time the app starts.
    """
    connection = get_connection()
    cursor = connection.cursor()

    # Table for user accounts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            first_name    TEXT    NOT NULL,
            last_name     TEXT    NOT NULL,
            created_at    TEXT    NOT NULL
        )
    """)

    # Table for saved matrix calculations (history)
    # We store matrices as JSON text — simple and flexible.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calculations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            rows        INTEGER NOT NULL,
            cols        INTEGER NOT NULL,
            matrix_a    TEXT    NOT NULL,
            matrix_b    TEXT    NOT NULL,
            result      TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()


# ---------------------------------------------------------------------------
# User functions
# ---------------------------------------------------------------------------
def create_user(email, password_hash, first_name, last_name):
    """
    Insert a new user.

    Returns the new user's id on success, or None if the email is already taken.
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO users (email, password_hash, first_name, last_name, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email, password_hash, first_name, last_name, datetime.now().isoformat()),
        )
        connection.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # This happens when the UNIQUE constraint on email is violated
        return None
    finally:
        connection.close()


def find_user_by_email(email):
    """
    Look up a user by email.
    Returns a dict-like row, or None if not found.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user_row = cursor.fetchone()
    connection.close()
    return user_row


def find_user_by_id(user_id):
    """Look up a user by their numeric id. Returns row or None."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    connection.close()
    return user_row


# ---------------------------------------------------------------------------
# Calculation history functions
# ---------------------------------------------------------------------------
def save_calculation(user_id, matrix_a, matrix_b, result):
    """
    Save one matrix-addition calculation for a user.

    Matrices come in as Python 2D lists. We store them as JSON strings.
    Returns a dict describing the new history entry (ready for the frontend).
    """
    connection = get_connection()
    cursor = connection.cursor()

    rows = len(matrix_a)
    cols = len(matrix_a[0]) if rows > 0 else 0
    created_at = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO calculations (user_id, rows, cols, matrix_a, matrix_b, result, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            rows,
            cols,
            json.dumps(matrix_a),
            json.dumps(matrix_b),
            json.dumps(result),
            created_at,
        ),
    )
    connection.commit()
    new_id = cursor.lastrowid
    connection.close()

    return {
        "id": new_id,
        "rows": rows,
        "cols": cols,
        "matrix_a": matrix_a,
        "matrix_b": matrix_b,
        "result": result,
        "created_at": created_at,
    }


def get_user_history(user_id, limit=50):
    """
    Get a user's saved calculations, newest first.
    Returns a list of dicts ready to send to the frontend.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT id, rows, cols, matrix_a, matrix_b, result, created_at
        FROM calculations
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = cursor.fetchall()
    connection.close()

    history_list = []
    for row in rows:
        history_list.append({
            "id": row["id"],
            "rows": row["rows"],
            "cols": row["cols"],
            "matrix_a": json.loads(row["matrix_a"]),
            "matrix_b": json.loads(row["matrix_b"]),
            "result": json.loads(row["result"]),
            "created_at": row["created_at"],
        })
    return history_list


def delete_calculation(user_id, calculation_id):
    """
    Delete one calculation, but only if it belongs to this user.
    Returns True if a row was deleted, False otherwise.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM calculations WHERE id = ? AND user_id = ?",
        (calculation_id, user_id),
    )
    connection.commit()
    deleted_count = cursor.rowcount
    connection.close()
    return deleted_count > 0


def clear_user_history(user_id):
    """Delete all calculations for one user. Returns the number deleted."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM calculations WHERE user_id = ?", (user_id,))
    connection.commit()
    deleted_count = cursor.rowcount
    connection.close()
    return deleted_count


# ---------------------------------------------------------------------------
# Profile / account update functions
# ---------------------------------------------------------------------------
def get_user_stats(user_id):
    """
    Return a dict of account statistics for the profile sidebar.
    Queries the DB so numbers are always accurate.
    """
    connection = get_connection()
    cursor = connection.cursor()

    # Total calculations this user has run
    cursor.execute(
        "SELECT COUNT(*) as total FROM calculations WHERE user_id = ?", (user_id,)
    )
    total_row = cursor.fetchone()
    total_calcs = total_row["total"] if total_row else 0

    # Most-used matrix size (the size that appears most in their history)
    cursor.execute(
        """
        SELECT rows || 'x' || cols AS size, COUNT(*) AS cnt
        FROM calculations WHERE user_id = ?
        GROUP BY size ORDER BY cnt DESC LIMIT 1
        """,
        (user_id,),
    )
    size_row = cursor.fetchone()
    preferred_size = size_row["size"] if size_row else "N/A"

    # Date the account was created
    cursor.execute("SELECT created_at FROM users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    joined = user_row["created_at"][:10] if user_row else "Unknown"  # just the date part

    # Most-recent calculation timestamp
    cursor.execute(
        "SELECT created_at FROM calculations WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    )
    last_row = cursor.fetchone()
    last_active = last_row["created_at"][:10] if last_row else "Never"

    connection.close()
    return {
        "total_calculations": total_calcs,
        "preferred_size": preferred_size,
        "joined": joined,
        "last_active": last_active,
    }


def update_user_name(user_id, first_name, last_name):
    """Update a user's first and last name. Returns True on success."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE users SET first_name = ?, last_name = ? WHERE id = ?",
        (first_name, last_name, user_id),
    )
    connection.commit()
    updated = cursor.rowcount > 0
    connection.close()
    return updated


def update_user_email(user_id, new_email):
    """
    Change a user's email address.
    Returns True on success, False if the new email is already taken.
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET email = ? WHERE id = ?", (new_email, user_id)
        )
        connection.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        # UNIQUE constraint — another account already uses this email
        return False
    finally:
        connection.close()


def update_user_password(user_id, new_password_hash):
    """Replace the stored password hash for a user. Returns True on success."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_password_hash, user_id),
    )
    connection.commit()
    updated = cursor.rowcount > 0
    connection.close()
    return updated