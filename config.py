"""Application configuration without credentials or network dependencies."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVICES = (
    "Plumbing",
    "Electrical",
    "HVAC",
    "Landscaping",
    "Roofing",
    "General Contracting",
    "Other",
)


def database_path() -> Path:
    return Path(os.environ.get("CONTRACTORFLOW_DB_PATH", ROOT / "contractorflow.db")).resolve()


def delivery_mode() -> str:
    if os.environ.get("CONTRACTORFLOW_DEMO") == "1":
        return "local"
    return os.environ.get("CONTRACTORFLOW_DELIVERY_MODE", "local").lower()
