import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

import database
from delivery import LocalPreviewService, configured_service
from notifications import get_notifications, process_outbox, queue_reminders, retry_notification

NOW = datetime(2026, 11, 2, 17, tzinfo=timezone.utc)


def add(key=None):
    with patch("database.utc_now", return_value=NOW):
        return database.add_lead(
            "Test Customer",
            "test@example.invalid",
            "",
            "HVAC",
            "Maintenance",
            "High",
            submission_key=key,
        )


def test_confirmation_owner_and_persistence(store):
    lead_id = add()
    messages = get_notifications()
    assert len(messages) == 2
    assert {row["kind"] for row in messages} == {"Owner inquiry", "Customer confirmation"}
    assert all(row["status"] == "Pending" and row["lead_id"] == lead_id for row in messages)
    for row in messages:
        assert "HVAC" in row["body"] and "High" in row["body"]
        assert "2026-11-02 16:00:00-05:00" in row["body"]
    database.initialize_database()
    assert get_notifications() == messages
    assert process_outbox(NOW) == {"previewed": 2, "failed": 0, "cancelled": 0}
    assert all(
        row["status"] == "Previewed" and row["sent_at"] is None for row in get_notifications()
    )
    assert process_outbox(NOW)["previewed"] == 0


def test_initial_outbox_failure_rolls_back_entire_inquiry(store):
    with database.connection() as conn:
        conn.execute(
            "CREATE TRIGGER reject_outbox BEFORE INSERT ON notification_outbox BEGIN SELECT RAISE(ABORT, 'failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        add()
    assert database.get_leads() == []
    assert database.get_tasks() == []
    assert get_notifications() == []


def test_duplicate_submission_concurrent_and_changed_payload(store):
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: add("request-1"), range(2)))
    assert ids[0] == ids[1]
    assert len(database.get_leads()) == len(database.get_tasks()) == 1
    assert len(get_notifications()) == 2
    with pytest.raises(ValueError):
        database.add_lead(
            "Changed", "test@example.invalid", "", "HVAC", "", "High", submission_key="request-1"
        )
    assert len(get_notifications()) == 2


def test_reminder_boundaries_duplicates_and_completion(store):
    add()
    assert queue_reminders(NOW - timedelta(hours=21)) == 0
    assert queue_reminders(NOW - timedelta(hours=20)) == 1  # exactly 24h before due
    assert queue_reminders(NOW) == 0
    assert queue_reminders(NOW + timedelta(hours=4)) == 0  # due exactly now is upcoming
    assert queue_reminders(NOW + timedelta(hours=4, microseconds=1)) == 1
    assert queue_reminders(NOW + timedelta(days=2)) == 0
    assert len(get_notifications()) == 4
    task = database.get_tasks()[0]
    database.complete_task(task["id"])
    assert queue_reminders(NOW + timedelta(days=3)) == 0
    reminders = [row for row in get_notifications() if "reminder" in row["kind"]]
    assert all(row["status"] == "Cancelled" for row in reminders)


def test_stale_upcoming_reminder_cancelled_before_processing(store):
    add()
    queue_reminders(NOW)
    result = process_outbox(NOW + timedelta(days=1))
    assert result == {"previewed": 2, "failed": 0, "cancelled": 1}


def test_failure_retry_and_sanitized_error(store):
    add()
    with patch("delivery.LocalPreviewService.deliver", side_effect=RuntimeError("private-token")):
        assert process_outbox(NOW)["failed"] == 2
    failed = get_notifications()
    assert all(row["status"] == "Failed" and row["attempts"] == 1 for row in failed)
    assert all("private-token" not in row["last_error"] for row in failed)
    assert process_outbox(NOW)["previewed"] == 0  # failures are not retried on rerun
    assert retry_notification(failed[0]["id"]) == 1
    assert retry_notification(failed[0]["id"]) == 0
    assert process_outbox(NOW)["previewed"] == 1
    row = next(row for row in get_notifications() if row["id"] == failed[0]["id"])
    assert row["attempts"] == 2 and row["last_error"] is None


def test_concurrent_preview_workers(store):
    add()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: process_outbox(NOW), range(2)))
    assert sum(result["previewed"] for result in results) == 2
    assert all(row["attempts"] == 1 for row in get_notifications())


def test_demo_forces_local_and_live_mode_rejected(store, monkeypatch):
    add()
    monkeypatch.setenv("CONTRACTORFLOW_DELIVERY_MODE", "live")
    with pytest.raises(ValueError):
        process_outbox(NOW)
    assert all(row["status"] == "Pending" for row in get_notifications())
    monkeypatch.setenv("CONTRACTORFLOW_DEMO", "1")
    assert isinstance(configured_service(), LocalPreviewService)
    assert process_outbox(NOW)["previewed"] == 2
    assert all(row["sent_at"] is None for row in get_notifications())


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", ""),
        ("name", "x" * 121),
        ("email", "invalid"),
        ("email", "a\x00@example.invalid"),
        ("email", "a\r\nb@example.com"),
        ("phone", "not a phone"),
        ("service", "unsupported"),
        ("urgency", "invalid"),
        ("description", "x" * 10001),
    ],
)
def test_intake_validation(store, field, value):
    values = dict(
        name="Customer",
        email="test@example.invalid",
        phone="",
        service="HVAC",
        description="",
        urgency="Normal",
    )
    values[field] = value
    with pytest.raises(ValueError):
        database.add_lead(**values)
    assert database.get_leads() == []


def test_notification_ui_and_unchanged_form_idempotency(store):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "main.py"), default_timeout=10
    ).run()
    app.sidebar.radio[0].set_value("Customer Inquiries").run()
    app.text_input[0].set_value("Customer")
    app.text_input[1].set_value("customer@example.invalid")
    app.button[0].click().run()
    app.button[0].click().run()
    assert not app.exception
    assert len(database.get_leads()) == 1
    app.sidebar.radio[0].set_value("Notification Center").run()
    assert not app.exception
    assert app.dataframe
    before = len(get_notifications())
    app.button[0].click().run()
    assert len(get_notifications()) == before
    app.button[1].click().run()
    assert not app.exception
    assert all(row["status"] == "Previewed" for row in get_notifications())
    app.selectbox[0].set_value("Failed").run()
    assert not app.exception
    assert not app.dataframe


def test_mixed_legacy_and_iso_timestamp_order(store):
    first, second = add(), add()
    with database.connection() as conn:
        conn.execute("UPDATE leads SET created_at='2026-11-02 23:00:00' WHERE id=?", (first,))
        conn.execute(
            "UPDATE leads SET created_at='2026-11-02T01:00:00+00:00' WHERE id=?", (second,)
        )
    assert [lead["id"] for lead in database.get_leads()] == [first, second]
