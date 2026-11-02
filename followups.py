"""Follow-up policy, independent of persistence and presentation."""
from datetime import datetime, timedelta, timezone

URGENCY_HOURS = {"Low": 72, "Normal": 24, "High": 4, "Emergency": 1}
LEAD_STATUSES = ("New", "Contacted", "Quoted", "Won", "Lost")


def utc_now():
    return datetime.now(timezone.utc)


def timestamp(value):
    """Store fixed-width UTC timestamps for safe SQLite ordering."""
    if value.tzinfo is None:
        raise ValueError("A timezone-aware datetime is required")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def followup_deadline(urgency, created_at):
    if urgency not in URGENCY_HOURS:
        raise ValueError("Invalid inquiry urgency")
    return created_at + timedelta(hours=URGENCY_HOURS[urgency])


def task_state(task, now=None):
    if task["completed_at"]:
        return "Completed"
    due = datetime.fromisoformat(task["due_at"])
    return "Overdue" if due < (now or utc_now()) else "Pending"
