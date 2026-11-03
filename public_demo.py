"""Fictional, read-only public snapshots. No database paths or delivery services."""

import sqlite3
from contextlib import contextmanager
from datetime import timedelta

from analytics import local_timestamp, parse_utc
from database import initialize_schema
from demo import populate_demo
from followups import timestamp, utc_now
from notification_messages import inquiry_messages, insert_message


@contextmanager
def demo_connection(reference):
    """Generate a disposable in-memory database, then reject all SQL mutations."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        initialize_schema(conn)
        populate_demo(conn, 42, reference)
        for lead in conn.execute("SELECT * FROM leads").fetchall():
            lead = dict(lead)
            task = conn.execute(
                "SELECT * FROM followup_tasks WHERE lead_id=?", (lead["id"],)
            ).fetchone()
            inquiry_messages(conn, lead, task["id"], task["due_at"], parse_utc(lead["created_at"]))
            due = parse_utc(task["due_at"])
            if not task["completed_at"] and due <= reference + timedelta(hours=24):
                kind = "Overdue reminder" if due < reference else "Upcoming reminder"
                insert_message(
                    conn,
                    event_key=f"demo:{task['id']}:{kind}",
                    kind=kind,
                    lead_id=lead["id"],
                    task_id=task["id"],
                    recipient="Business owner (local inbox)",
                    subject=f"{kind}: {lead['service']}",
                    body=f"Fictional follow-up for {lead['name']}. Deadline (America/New_York): {local_timestamp(task['due_at'])}. Demo preview only; no message was sent.",
                    now=reference,
                    due_at=task["due_at"],
                )
        conn.execute(
            "UPDATE notification_outbox SET status='Previewed', processed_at=?, attempts=1, receipt='Fictional demo preview'",
            (timestamp(reference),),
        )
        conn.commit()
        conn.execute("PRAGMA query_only = ON")
        yield conn
    finally:
        conn.close()


def build_snapshot(reference=None):
    reference = parse_utc(reference or utc_now())
    if reference is None:
        raise ValueError("Use a valid UTC snapshot time.")
    with demo_connection(reference) as conn:
        leads = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM leads ORDER BY julianday(created_at) DESC, id DESC"
            )
        ]
        tasks = [
            dict(row)
            for row in conn.execute("""SELECT t.*, l.name, l.email, l.phone, l.service, l.urgency, l.status AS lead_status
            FROM followup_tasks t JOIN leads l ON l.id=t.lead_id
            ORDER BY t.completed_at IS NOT NULL, julianday(t.due_at), t.id""")
        ]
        messages = [
            dict(row) for row in conn.execute("SELECT * FROM notification_outbox ORDER BY id DESC")
        ]
    return dict(leads=leads, tasks=tasks, messages=messages, as_of=reference)
