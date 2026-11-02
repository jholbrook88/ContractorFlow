"""Persistent local outbox and idempotent follow-up reminder checks."""

import argparse
from datetime import timedelta

import database
from analytics import parse_utc
from delivery import configured_service
from followups import timestamp, utc_now
from notification_messages import insert_message

REMINDERS = ("Upcoming reminder", "Overdue reminder")


def get_notifications():
    with database.connection() as conn:
        return [
            dict(row) for row in conn.execute("SELECT * FROM notification_outbox ORDER BY id DESC")
        ]


def queue_reminders(now=None):
    """One upcoming (within 24h) and one overdue event per task/deadline."""
    now = parse_utc(now or utc_now())
    count = 0
    with database.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        tasks = conn.execute("""SELECT t.*, l.name, l.service, l.urgency
                                FROM followup_tasks t JOIN leads l ON l.id=t.lead_id
                                WHERE t.completed_at IS NULL""").fetchall()
        for task in tasks:
            due = parse_utc(task["due_at"])
            if due is None or due > now + timedelta(hours=24):
                continue
            kind = "Overdue reminder" if due < now else "Upcoming reminder"
            from analytics import local_timestamp

            count += insert_message(
                conn,
                event_key=f"task:{task['id']}:{task['due_at']}:{kind}",
                kind=kind,
                lead_id=task["lead_id"],
                task_id=task["id"],
                recipient="Business owner (local inbox)",
                subject=f"{kind}: #{task['id']} - {task['name']}",
                body=f"{kind} for inquiry #{task['lead_id']}.\nCustomer: {task['name']}\n"
                f"Service: {task['service']}\nUrgency: {task['urgency']}\n"
                f"Deadline (America/New_York): {local_timestamp(task['due_at'])}",
                now=now,
                due_at=task["due_at"],
            )
    return count


def process_outbox(now=None):
    """Serialize local previews so concurrent workers cannot process the same row."""
    service = configured_service()  # Reject unsupported modes before changing any rows.
    now = parse_utc(now or utc_now())
    result = {"previewed": 0, "failed": 0, "cancelled": 0}
    with database.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for row in conn.execute(
            "SELECT * FROM notification_outbox WHERE status='Pending' ORDER BY id"
        ).fetchall():
            message = dict(row)
            if message["kind"] in REMINDERS:
                task = conn.execute(
                    "SELECT * FROM followup_tasks WHERE id=?", (message["task_id"],)
                ).fetchone()
                due = parse_utc(task["due_at"]) if task else None
                stale = (
                    not task
                    or task["completed_at"]
                    or not due
                    or task["due_at"] != message["reminder_due_at"]
                    or (message["kind"] == "Upcoming reminder" and due < now)
                    or (message["kind"] == "Overdue reminder" and due >= now)
                )
                if stale:
                    conn.execute(
                        "UPDATE notification_outbox SET status='Cancelled', processed_at=? WHERE id=?",
                        (timestamp(now), message["id"]),
                    )
                    result["cancelled"] += 1
                    continue
            try:
                receipt = service.deliver(message)
                if not isinstance(receipt, str) or not receipt:
                    raise ValueError("Local adapter returned no receipt")
            except Exception as exc:
                # Persist failure, but never store arbitrary exception text (may contain secrets).
                conn.execute(
                    """UPDATE notification_outbox SET status='Failed', attempts=attempts+1,
                                last_error=?, processed_at=? WHERE id=?""",
                    (
                        f"Local preview failed ({type(exc).__name__}).",
                        timestamp(now),
                        message["id"],
                    ),
                )
                result["failed"] += 1
            else:
                conn.execute(
                    """UPDATE notification_outbox SET status='Previewed', attempts=attempts+1,
                                receipt=?, last_error=NULL, processed_at=? WHERE id=?""",
                    (receipt, timestamp(now), message["id"]),
                )
                result["previewed"] += 1
    return result


def retry_notification(notification_id):
    with database.connection() as conn:
        return conn.execute(
            "UPDATE notification_outbox SET status='Pending' WHERE id=? AND status='Failed'",
            (notification_id,),
        ).rowcount


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "preview"))
    args = parser.parse_args()
    database.initialize_database()
    print(queue_reminders() if args.action == "check" else process_outbox())


if __name__ == "__main__":
    main()
