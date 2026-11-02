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


def parse_utc(value):
    """Original SQLite naive timestamps are UTC, never machine-local time."""
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def task_state(task, now=None):
    if task.get("completed_at"):
        return "Completed"
    due = parse_utc(task.get("due_at"))
    if due is None:
        return "Unknown deadline"
    return "Overdue" if due < parse_utc(now or utc_now()) else "Pending"
