import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import database
from backup import snapshot
from tests.test_notifications import add


def test_backup_recovery_preserves_records_and_outbox(store, tmp_path):
    add()
    backup = snapshot(store, tmp_path / "backup.db")
    recovered = snapshot(backup, tmp_path / "recovered.db")
    with closing(sqlite3.connect(store)) as source, closing(sqlite3.connect(recovered)) as restored:
        for table in ("leads", "followup_tasks", "notification_outbox", "intake_submissions"):
            assert (
                source.execute("SELECT * FROM " + table).fetchall()
                == restored.execute("SELECT * FROM " + table).fetchall()
            )
    original = store.read_bytes()
    with pytest.raises((ValueError, FileExistsError)):
        snapshot(backup, store)
    assert store.read_bytes() == original
    with pytest.raises(FileExistsError):
        snapshot(store, backup)
    with pytest.raises(ValueError):
        snapshot(tmp_path / "missing.db", tmp_path / "new.db")


def test_corrupt_source_is_rejected_without_destination(store, tmp_path):
    broken = tmp_path / "corrupt.db"
    broken.write_bytes(b"not sqlite")
    output = tmp_path / "output.db"
    with pytest.raises(sqlite3.DatabaseError):
        snapshot(broken, output)
    assert not output.exists()


def test_lead_search_status_and_sorting_ui(store):
    from streamlit.testing.v1 import AppTest

    add()
    database.add_lead("Avery", "avery@example.invalid", "", "Plumbing", "", "Normal")
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "main.py"), default_timeout=10
    ).run()
    app.sidebar.radio[0].set_value("Lead Management").run()
    app.text_input(key="lead_search").set_value("AVERY").run()
    assert len(app.dataframe[0].value) == 1
    app.text_input(key="lead_search").set_value("").run()
    app.selectbox(key="lead_sort").set_value("Customer name").run()
    assert app.dataframe[0].value.iloc[0]["name"] == "Avery"
    app.multiselect[0].set_value(["Won"]).run()
    assert not app.exception and not app.dataframe
