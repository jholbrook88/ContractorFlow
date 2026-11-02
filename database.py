"""SQLite persistence. Existing leads are never rewritten by migrations."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

from followups import LEAD_STATUSES, followup_deadline, timestamp, utc_now

DB_PATH = Path(__file__).resolve().parent / "contractorflow.db"


def get_connection():
    # Optional override also lets tests use isolated temporary databases.
    conn = sqlite3.connect(os.environ.get("CONTRACTORFLOW_DB_PATH", DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection():
    """Commit/rollback and explicitly close, including on exceptions."""
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize_database():
    """Idempotent additive migration; intentionally no historical task backfill."""
    with connection() as conn:
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS followup_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL UNIQUE REFERENCES leads(id),
                created_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_followup_pending_due
                        ON followup_tasks(completed_at, due_at)""")


def add_lead(name, email, phone, service, description, urgency):
    name, email, service = name.strip(), email.strip(), service.strip()
    if not name or not email or not service:
        raise ValueError("Customer name, email and service are required")
    created = utc_now()
    due = followup_deadline(urgency, created)
    with connection() as conn:
        cursor = conn.execute("""
            INSERT INTO leads
            (name, email, phone, service, description, urgency)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, phone, service, description, urgency))
        lead_id = cursor.lastrowid
        conn.execute("""INSERT INTO followup_tasks (lead_id, created_at, due_at)
                        VALUES (?, ?, ?)""", (lead_id, timestamp(created), timestamp(due)))
        return lead_id


def get_leads():
    with connection() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM leads ORDER BY created_at DESC, id DESC")]


def update_lead_status(lead_id, new_status):
    if new_status not in LEAD_STATUSES:
        raise ValueError("Invalid lead status")
    with connection() as conn:
        return conn.execute("UPDATE leads SET status = ? WHERE id = ?",
                            (new_status, lead_id)).rowcount


def get_tasks():
    with connection() as conn:
        return [dict(row) for row in conn.execute("""
            SELECT t.*, l.name, l.email, l.phone, l.service, l.urgency,
                   l.status AS lead_status
            FROM followup_tasks t JOIN leads l ON l.id = t.lead_id
            ORDER BY t.completed_at IS NOT NULL, t.due_at, t.id
        """)]


def complete_task(task_id):
    """Idempotent completion preserves the first completion timestamp."""
    with connection() as conn:
        return conn.execute("""UPDATE followup_tasks SET completed_at = ?
                               WHERE id = ? AND completed_at IS NULL""",
                            (timestamp(utc_now()), task_id)).rowcount
