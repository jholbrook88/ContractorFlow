"""Development-only fictional fixture generator and isolated local launcher."""

import argparse
import os
import random
import sqlite3
import subprocess
import sys
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import database
from analytics import LOCAL_ZONE, parse_utc
from followups import followup_deadline, timestamp, utc_now

ROOT = Path(__file__).resolve().parent
DEMO_ROOT = ROOT / "demo_data"
DEFAULT_PATH = DEMO_ROOT / "contractorflow-demo.db"
FIRST = (
    "Avery",
    "Jordan",
    "Morgan",
    "Taylor",
    "Casey",
    "Riley",
    "Cameron",
    "Jamie",
    "Alex",
    "Robin",
)
LAST = (
    "Bennett",
    "Carter",
    "Hayes",
    "Parker",
    "Reed",
    "Brooks",
    "Ellis",
    "Sutton",
    "Lane",
    "Foster",
    "Quinn",
    "Walsh",
    "Blake",
    "Hart",
    "Mills",
)
SERVICES = (
    "Plumbing",
    "Electrical",
    "HVAC",
    "Landscaping",
    "Roofing",
    "General Contracting",
    "Other",
)
DESCRIPTIONS = (
    "Repair a leaking kitchen faucet",
    "Install lighting in a home office",
    "Seasonal heating and cooling maintenance",
    "Refresh planting beds and lawn drainage",
    "Inspect a roof leak near the chimney",
    "Discuss a small bathroom renovation",
    "Assess minor home maintenance repairs",
)


@contextmanager
def selected_database(path):
    original = os.environ.get("CONTRACTORFLOW_DB_PATH")
    os.environ["CONTRACTORFLOW_DB_PATH"] = str(path)
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("CONTRACTORFLOW_DB_PATH", None)
        else:
            os.environ["CONTRACTORFLOW_DB_PATH"] = original


def demo_path(value):
    """Restrict every generated/launchable database to the ignored demo folder."""
    path = Path(value).resolve()
    if path.parent != DEMO_ROOT.resolve() or path.suffix != ".db":
        raise ValueError("Demo databases must be .db files directly inside demo_data/")
    if path.is_symlink() or (Path(value).exists() and Path(value).is_symlink()):
        raise ValueError("Demo database symlinks are not allowed")
    return path


def generate_demo(path=DEFAULT_PATH, seed=42, as_of=None):
    path = demo_path(path)
    reference = parse_utc(as_of) if as_of is not None else utc_now().replace(microsecond=0)
    if reference is None:
        raise ValueError("Use an ISO timestamp for --as-of")
    path.parent.mkdir(exist_ok=True)
    # Exclusive creation: never replace operational data or an existing demo.
    with path.open("xb"):
        pass
    rng = random.Random(seed)
    local = reference.astimezone(LOCAL_ZONE)
    with selected_database(path):
        database.initialize_database()
        with database.connection() as conn:
            conn.execute(
                "CREATE TABLE demo_metadata (seed INTEGER, as_of TEXT, inquiry_count INTEGER)"
            )
            conn.execute(
                "INSERT INTO demo_metadata VALUES (?, ?, 150)", (seed, timestamp(reference))
            )
            for index in range(150):
                # 90 guaranteed calendar days, plus 60 weighted toward recent weeks.
                age = index if index < 90 else int(rng.triangular(0, 89, 15))
                day = local.date() - timedelta(days=age)
                created_local = datetime.combine(day, datetime.min.time(), LOCAL_ZONE).replace(
                    hour=rng.randint(8, 17), minute=rng.randrange(60)
                )
                if age == 0:
                    midnight = datetime.combine(day, datetime.min.time(), LOCAL_ZONE)
                    created_local = local - (local - midnight) * rng.random()
                created = created_local.astimezone(timezone.utc)
                service = rng.choices(SERVICES, weights=(25, 19, 21, 11, 9, 12, 3))[0]
                urgency = rng.choices(
                    ("Low", "Normal", "High", "Emergency"), weights=(17, 59, 20, 4)
                )[0]
                status = rng.choices(
                    ("New", "Contacted", "Quoted", "Won", "Lost"),
                    weights=(65, 25, 8, 1, 1) if age < 4 else (4, 15, 25, 42, 14),
                )[0]
                due = followup_deadline(urgency, created)
                completion = None
                if (
                    status in ("Quoted", "Won", "Lost")
                    or (status == "Contacted" and rng.random() < 0.8)
                    or (status == "New" and rng.random() < 0.1)
                ):
                    completed = min(reference, created + timedelta(hours=rng.uniform(0.25, 40)))
                    completion = timestamp(completed)
                name = f"{FIRST[index % len(FIRST)]} {LAST[index // len(FIRST)]}"
                cursor = conn.execute(
                    """INSERT INTO leads
                    (name,email,phone,service,description,urgency,status,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        name,
                        f"customer{index + 1:03d}@example.invalid",
                        f"202-555-{100 + index % 100:04d}",
                        service,
                        "[FICTIONAL DEMO] " + DESCRIPTIONS[SERVICES.index(service)],
                        urgency,
                        status,
                        timestamp(created),
                    ),
                )
                conn.execute(
                    "INSERT INTO followup_tasks (lead_id,created_at,due_at,completed_at) VALUES (?,?,?,?)",
                    (cursor.lastrowid, timestamp(created), timestamp(due), completion),
                )
    return path


def launch_demo(path=DEFAULT_PATH):
    path = demo_path(path)
    if not path.is_file():
        raise ValueError("Generate the demo database first.")
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as conn:
        metadata = conn.execute("SELECT as_of FROM demo_metadata").fetchone()
        if not metadata:
            raise ValueError("Not a ContractorFlow demo database")
    env = dict(os.environ, CONTRACTORFLOW_DB_PATH=str(path), CONTRACTORFLOW_DEMO="1")
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "main.py"),
            "--server.address",
            "127.0.0.1",
            "--server.port",
            "8502",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=ROOT,
        env=env,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seed", "run", "reset"))
    parser.add_argument("--database", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of", help="Fixed ISO UTC snapshot, e.g. 2026-11-02T17:00:00Z")
    args = parser.parse_args()
    try:
        if args.action in ("seed", "reset"):
            destination = (
                (DEMO_ROOT / f"session-{utc_now():%Y%m%dT%H%M%S%f}.db")
                if args.action == "reset"
                else args.database
            )
            path = generate_demo(destination, args.seed, args.as_of)
            print(f"Created 150 fictional inquiries and follow-ups: {path}")
            print(f'Launch: {sys.executable} demo.py run --database "{path}"')
        else:
            return launch_demo(args.database)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Demo mode: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
