
import sqlite3
from pathlib import Path

# Database file location
DB_PATH = Path(__file__).parent / "contractorflow.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                service TEXT NOT NULL,
                description TEXT,
                urgency TEXT NOT NULL,
                status TEXT DEFAULT 'New',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def add_lead(name, email, phone, service, description, urgency):
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO leads
            (name, email, phone, service, description, urgency)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, phone, service, description, urgency))

        return cursor.lastrowid


def get_leads():
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM leads
            ORDER BY created_at DESC, id DESC
        """).fetchall()

        return [dict(row) for row in rows]


def update_lead_status(lead_id, new_status):
    valid_statuses = {"New", "Contacted", "Quoted", "Won", "Lost"}

    if new_status not in valid_statuses:
        raise ValueError("Invalid lead status")

    with get_connection() as conn:
        cursor = conn.execute("""
            UPDATE leads
            SET status = ?
            WHERE id = ?
        """, (new_status, lead_id))

        return cursor.rowcount
