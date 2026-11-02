"""Read-only analytics, local calendar filters and portable CSV reports."""

import csv
import io
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from followups import LEAD_STATUSES, parse_utc, utc_now
from followups import task_state as report_task_state

LOCAL_ZONE = ZoneInfo("America/New_York")
DATE_RANGES = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All time": None}
LEAD_COLUMNS = (
    "id",
    "name",
    "email",
    "phone",
    "service",
    "description",
    "urgency",
    "status",
    "created_at",
)
TASK_COLUMNS = (
    "id",
    "lead_id",
    "name",
    "email",
    "phone",
    "service",
    "urgency",
    "lead_status",
    "created_at",
    "due_at",
    "completed_at",
    "state",
)
TIME_COLUMNS = ("created_at", "due_at", "completed_at", "processed_at", "sent_at")


def local_timestamp(value):
    parsed = parse_utc(value)
    if parsed is None:
        return "Unknown" if value else ""
    return parsed.astimezone(LOCAL_ZONE).isoformat(sep=" ", timespec="seconds")


def localize_records(records):
    """Return display copies; UTC storage and caller inputs remain unchanged."""
    return [
        {
            key: local_timestamp(value) if key in TIME_COLUMNS else value
            for key, value in record.items()
        }
        for record in records
    ]


def filter_records(records, period="All time", now=None):
    days = DATE_RANGES[period]
    if days is None:
        return list(records)
    now = parse_utc(now or utc_now())
    start_date = now.astimezone(LOCAL_ZONE).date() - timedelta(days=days - 1)
    start = datetime.combine(start_date, time.min, tzinfo=LOCAL_ZONE).astimezone(timezone.utc)
    return [
        record
        for record in records
        if (created := parse_utc(record.get("created_at"))) is not None and start <= created <= now
    ]


def calculate_kpis(leads, tasks, now=None):
    now = now or utc_now()
    states = Counter(report_task_state(task, now) for task in tasks)
    won = sum(lead.get("status") == "Won" for lead in leads)
    return {
        "total_leads": len(leads),
        "new_inquiries": sum(lead.get("status") == "New" for lead in leads),
        "conversion_rate": won / len(leads) * 100 if leads else None,
        "pending_tasks": len(tasks) - states["Completed"],
        "overdue_tasks": states["Overdue"],
        "completed_followups": states["Completed"],
    }


def category_counts(leads, field, order=()):
    counts = Counter(str(lead.get(field) or "").strip() or "Unknown" for lead in leads)
    categories = list(order) + sorted(set(counts) - set(order))
    return [{"Category": category, "Leads": counts[category]} for category in categories]


def pipeline_report(leads):
    return category_counts(leads, "status", LEAD_STATUSES)


def inquiry_volume(leads, period="All time", now=None):
    """Daily counts including zero days; monthly bins for spans over a year."""
    now = parse_utc(now or utc_now())
    dates = [
        created.astimezone(LOCAL_ZONE).date()
        for lead in filter_records(leads, period, now)
        if (created := parse_utc(lead.get("created_at"))) is not None
    ]
    if not dates:
        return []
    days = DATE_RANGES[period]
    start = now.astimezone(LOCAL_ZONE).date() - timedelta(days=days - 1) if days else min(dates)
    end = now.astimezone(LOCAL_ZONE).date() if days else max(dates)
    monthly = (end - start).days > 366
    if monthly:
        counts = Counter(day.replace(day=1) for day in dates)
        current, end = start.replace(day=1), end.replace(day=1)
    else:
        counts = Counter(dates)
        current = start
    result = []
    while current <= end:
        result.append(
            {
                "Period": current.isoformat(),
                "Inquiries": counts[current],
                "Interval": "Month" if monthly else "Day",
            }
        )
        if current == end:
            break
        if monthly:
            current = current.replace(
                year=current.year + (current.month == 12), month=current.month % 12 + 1
            )
        else:
            current += timedelta(days=1)
    return result


def export_csv(records, report, now=None):
    """Stable headers even when empty; spreadsheet formula cells are escaped."""
    if report not in ("leads", "tasks"):
        raise ValueError("Unknown report type")
    columns = LEAD_COLUMNS if report == "leads" else TASK_COLUMNS
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [f"{column} (America/New_York)" if column in TIME_COLUMNS else column for column in columns]
    )
    now = now or utc_now()
    for source in records:
        record = localize_records([source])[0]
        if report == "tasks":
            record["state"] = report_task_state(source, now)
        values = []
        for column in columns:
            value = record.get(column)
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return output.getvalue().encode("utf-8-sig")
