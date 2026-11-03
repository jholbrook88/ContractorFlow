"""Public demo boundaries: generated records, read-only SQL and no operational access."""

import os
import sqlite3
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import database
import delivery
import notifications
from analytics import export_csv, report_task_state
from public_demo import build_snapshot, demo_connection

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "cloud_demo" / "streamlit_app.py"
REFERENCE = datetime(2026, 11, 2, 17, tzinfo=timezone.utc)


@pytest.fixture
def safe_demo(tmp_path, monkeypatch):
    sentinel = tmp_path / "must-not-open.db"
    sentinel.write_bytes(b"Private-data sentinel; not a customer database")
    monkeypatch.setenv("CONTRACTORFLOW_DB_PATH", str(sentinel))
    monkeypatch.setenv("CONTRACTORFLOW_DELIVERY_MODE", "smtp")
    monkeypatch.delenv("CONTRACTORFLOW_DEMO", raising=False)
    before = {key: value for key, value in os.environ.items() if key.startswith("CONTRACTORFLOW_")}
    original = sqlite3.connect
    opened = []

    def memory_only(path, *args, **kwargs):
        assert path == ":memory:", f"Unexpected file-backed SQLite access: {path}"
        opened.append(path)
        return original(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("Public demo attempted operational storage or delivery")

    monkeypatch.setattr(sqlite3, "connect", memory_only)
    monkeypatch.setattr(database, "get_connection", forbidden)
    monkeypatch.setattr(database, "initialize_database", forbidden)
    monkeypatch.setattr(delivery, "configured_service", forbidden)
    monkeypatch.setattr(delivery.LocalPreviewService, "deliver", forbidden)
    monkeypatch.setattr(notifications, "process_outbox", forbidden)
    monkeypatch.setattr(notifications, "queue_reminders", forbidden)
    yield opened
    assert sentinel.read_bytes() == b"Private-data sentinel; not a customer database"
    assert {
        key: value for key, value in os.environ.items() if key.startswith("CONTRACTORFLOW_")
    } == before
    assert list(tmp_path.iterdir()) == [sentinel]


def test_snapshot_uses_only_memory_and_matches_existing_fictional_fixture(safe_demo):
    first = build_snapshot(REFERENCE)
    second = build_snapshot(REFERENCE)
    assert first == second
    assert safe_demo == [":memory:", ":memory:"]
    assert len(first["leads"]) == len(first["tasks"]) == 150
    assert len({row["name"] for row in first["leads"]}) == 150
    assert all(row["email"].endswith("@example.invalid") for row in first["leads"])
    assert all(row["description"].startswith("[FICTIONAL DEMO]") for row in first["leads"])
    assert all("202-555-01" in row["phone"] for row in first["leads"])
    assert {report_task_state(task, REFERENCE) for task in first["tasks"]} == {
        "Pending",
        "Overdue",
        "Completed",
    }
    assert len({row["status"] for row in first["leads"]}) == 5
    assert len({row["service"] for row in first["leads"]}) == 7
    assert len({row["urgency"] for row in first["leads"]}) == 4
    first["leads"][0]["name"] = "Changed only in this copy"
    assert second["leads"][0]["name"] != first["leads"][0]["name"]


def test_sql_rejects_writes_after_seed_and_connection_closes(safe_demo):
    with demo_connection(REFERENCE) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        for statement in [
            "UPDATE leads SET name='Changed'",
            "DELETE FROM followup_tasks",
            "CREATE TABLE unwanted(id INTEGER)",
        ]:
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                conn.execute(statement)
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")


def test_notifications_are_fictional_snapshots_without_delivery(safe_demo):
    data = build_snapshot(REFERENCE)
    assert (
        {"Customer confirmation", "Owner inquiry", "Overdue reminder"}
        <= {message["kind"] for message in data["messages"]}
        <= {
            "Customer confirmation",
            "Owner inquiry",
            "Upcoming reminder",
            "Overdue reminder",
        }
    )
    assert all(
        message["status"] == "Previewed"
        and message["sent_at"] is None
        and message["delivery_mode"] == "local"
        for message in data["messages"]
    )
    assert all(
        message["recipient"].endswith("@example.invalid")
        or message["recipient"] == "Business owner (local inbox)"
        for message in data["messages"]
    )
    assert (
        export_csv(data["leads"], "leads", REFERENCE).decode("utf-8-sig").count("@example.invalid")
        == 150
    )


def test_public_pages_start_and_never_offer_writes(safe_demo):
    app = AppTest.from_file(str(ENTRY), default_timeout=15).run()
    assert not app.exception
    assert any("Demo Mode" in notice.value and "fictional" in notice.value for notice in app.info)
    assert app.metric[0].value == "150"
    assert len(app.get("plotly_chart")) == 4
    assert len(app.get("download_button")) == 2
    for period in ["Last 7 days", "Last 30 days", "Last 90 days", "All time"]:
        app.selectbox[0].set_value(period).run()
        assert not app.exception
    for page in [
        "Lead management",
        "Follow-up tasks",
        "Notification previews",
        "Customer intake",
        "About this demo",
    ]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
        assert all(button.disabled for button in app.button)
        assert not app.get("file_uploader")
        assert not app.get("form")


def test_filters_are_separate_between_visitors_and_reruns(safe_demo):
    first = AppTest.from_file(str(ENTRY), default_timeout=15).run()
    first.sidebar.radio[0].set_value("Lead management").run()
    first.text_input[0].set_value("No matching fictional customer").run()
    assert not first.dataframe
    second = AppTest.from_file(str(ENTRY), default_timeout=15).run()
    assert second.metric[0].value == "150"
    second.sidebar.radio[0].set_value("Lead management").run()
    assert len(second.dataframe[0].value) == 150
    assert second.text_input[0].value == ""
    first.text_input[0].set_value("").run()
    assert len(first.dataframe[0].value) == 150
    assert not first.exception and not second.exception


def test_cloud_configuration_keeps_localhost_local_and_uses_pinned_runtime():
    local = tomllib.loads((ROOT / ".streamlit/config.toml").read_text(encoding="utf-8"))
    cloud = tomllib.loads((ROOT / "cloud_demo/.streamlit/config.toml").read_text(encoding="utf-8"))
    assert local["server"]["address"] == "127.0.0.1"
    assert cloud["server"]["address"] == "0.0.0.0"
    assert cloud["server"]["headless"]
    assert cloud["server"]["enableCORS"] and cloud["server"]["enableXsrfProtection"]
    assert cloud["client"]["showErrorDetails"] == "none"
    assert (
        ROOT / "cloud_demo/requirements.txt"
    ).read_text().strip() == "-r ../requirements-lock.txt"
    assert "streamlit==1.66.1" in (ROOT / "requirements-lock.txt").read_text()
    assert ENTRY.exists()


@pytest.mark.parametrize(
    "entry,address", [("cloud_demo/streamlit_app.py", "0.0.0.0"), ("main.py", "127.0.0.1")]
)
def test_streamlit_loads_the_correct_entrypoint_configuration(entry, address):
    import subprocess
    import sys

    # Run the installed Streamlit config loader in its own process, avoiding AppTest globals.
    probe = """
import sys
from streamlit import config
config._main_script_path = sys.argv[1]
config.get_config_options(force_reparse=True)
assert config.get_option("server.address") == sys.argv[2]
assert config.get_option("server.enableXsrfProtection")
"""
    result = subprocess.run(
        [sys.executable, "-c", probe, str(ROOT / entry), address],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_invalid_snapshot_time_is_rejected():
    with pytest.raises(ValueError, match="UTC snapshot"):
        build_snapshot("not a date")
