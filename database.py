"""SQLite persistence. Existing leads are never rewritten by migrations."""

import sqlite3
from contextlib import contextmanager

from config import database_path
from followups import LEAD_STATUSES, followup_deadline, timestamp, utc_now
from intake import inquiry_fingerprint, validate_inquiry
from notification_messages import inquiry_messages


def get_connection():
    conn = sqlite3.connect(database_path(), timeout=10)
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
        initialize_schema(conn)


def initialize_schema(conn):
    """Apply additive schema statements to an explicitly supplied SQLite connection."""
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notification_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_key TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,
            lead_id INTEGER NOT NULL REFERENCES leads(id),
            task_id INTEGER REFERENCES followup_tasks(id),
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending'
                CHECK(status IN ('Pending','Previewed','Sent','Failed','Cancelled')),
            created_at TEXT NOT NULL,
            processed_at TEXT,
            sent_at TEXT,
            reminder_due_at TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            receipt TEXT,
            last_error TEXT,
            delivery_mode TEXT NOT NULL DEFAULT 'local' CHECK(delivery_mode='local')
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outbox_status ON notification_outbox(status, id)")

    conn.execute("""CREATE TABLE IF NOT EXISTS intake_submissions (
        submission_key TEXT PRIMARY KEY,
        lead_id INTEGER NOT NULL REFERENCES leads(id),
        fingerprint TEXT NOT NULL
    )""")


def add_lead(name, email, phone, service, description, urgency, submission_key=None):
    values = validate_inquiry(name, email, phone, service, description, urgency)
    name, email, phone, service, description, urgency = values
    if submission_key is not None and (
        not isinstance(submission_key, str) or not 1 <= len(submission_key) <= 128
    ):
        raise ValueError("Invalid submission key")
    fingerprint = inquiry_fingerprint(values)
    created = utc_now()
    due = followup_deadline(urgency, created)
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if submission_key:
            previous = conn.execute(
                "SELECT lead_id, fingerprint FROM intake_submissions WHERE submission_key=?",
                (submission_key,),
            ).fetchone()
            if previous:
                if previous["fingerprint"] != fingerprint:
                    raise ValueError("This submission key was already used for another inquiry.")
                return previous["lead_id"]

        cursor = conn.execute(
            """
            INSERT INTO leads
            (name, email, phone, service, description, urgency)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (name, email, phone, service, description, urgency),
        )
        lead_id = cursor.lastrowid
        task_cursor = conn.execute(
            """INSERT INTO followup_tasks (lead_id, created_at, due_at)
                        VALUES (?, ?, ?)""",
            (lead_id, timestamp(created), timestamp(due)),
        )
        inquiry_messages(
            conn,
            dict(
                id=lead_id,
                name=name,
                email=email,
                phone=phone,
                service=service,
                description=description,
                urgency=urgency,
            ),
            task_cursor.lastrowid,
            timestamp(due),
            created,
        )
        if submission_key:
            conn.execute(
                "INSERT INTO intake_submissions VALUES (?,?,?)",
                (submission_key, lead_id, fingerprint),
            )
        return lead_id


def get_leads():
    with connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM leads ORDER BY julianday(created_at) DESC, id DESC"
            )
        ]


def update_lead_status(lead_id, new_status):
    if new_status not in LEAD_STATUSES:
        raise ValueError("Invalid lead status")
    with connection() as conn:
        return conn.execute(
            "UPDATE leads SET status = ? WHERE id = ?", (new_status, lead_id)
        ).rowcount


def get_tasks():
    with connection() as conn:
        return [
            dict(row)
            for row in conn.execute("""
            SELECT t.*, l.name, l.email, l.phone, l.service, l.urgency,
                   l.status AS lead_status
            FROM followup_tasks t JOIN leads l ON l.id = t.lead_id
            ORDER BY t.completed_at IS NOT NULL, julianday(t.due_at) IS NULL, julianday(t.due_at), t.id
        """)
        ]


def complete_task(task_id):
    """Idempotent completion preserves the first completion timestamp."""
    with connection() as conn:
        updated = conn.execute(
            """UPDATE followup_tasks SET completed_at = ?
                               WHERE id = ? AND completed_at IS NULL""",
            (timestamp(utc_now()), task_id),
        ).rowcount
        if updated:
            conn.execute(
                """UPDATE notification_outbox SET status='Cancelled', processed_at=?
                            WHERE task_id=? AND kind IN ('Upcoming reminder','Overdue reminder')
                            AND status IN ('Pending','Failed')""",
                (timestamp(utc_now()), task_id),
            )
        return updated
