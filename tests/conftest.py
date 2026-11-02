import pytest

import database


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTRACTORFLOW_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CONTRACTORFLOW_DELIVERY_MODE", "local")
    monkeypatch.delenv("CONTRACTORFLOW_DEMO", raising=False)
    database.initialize_database()
    return tmp_path / "test.db"
