"""Presentation and demo tooling regression coverage without production writes."""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import demo
from analytics import LOCAL_ZONE, parse_utc, report_task_state
from charts import category_figure, volume_figure
from followups import followup_deadline

REFERENCE = datetime(2026, 11, 2, 17, tzinfo=timezone.utc)


class ChartTests(unittest.TestCase):
    def test_empty_and_single_day(self):
        self.assertEqual(len(volume_figure([]).data), 0)
        self.assertTrue(volume_figure([]).layout.annotations)
        fig = volume_figure([{"Period": "2026-11-02", "Inquiries": 1, "Interval": "Day"}])
        self.assertEqual(list(fig.layout.xaxis.ticktext), ["Nov 2"])
        self.assertEqual(fig.layout.xaxis.type, "date")
        self.assertLess(datetime.fromisoformat(fig.layout.xaxis.range[0]), datetime(2026, 11, 2))
        self.assertGreater(datetime.fromisoformat(fig.layout.xaxis.range[1]), datetime(2026, 11, 2))
        self.assertEqual(fig.layout.yaxis.dtick, 1)
        self.assertGreater(fig.data[0].width, 0)

    def test_many_days_and_month_labels(self):
        volume = [
            {
                "Period": (REFERENCE.date() - timedelta(days=89 - i)).isoformat(),
                "Inquiries": i % 5,
                "Interval": "Day",
            }
            for i in range(90)
        ]
        fig = volume_figure(volume)
        self.assertLessEqual(len(fig.layout.xaxis.tickvals), 8)
        self.assertEqual(fig.layout.xaxis.ticktext[-1], "Nov 2")
        self.assertTrue(all(":" not in label for label in fig.layout.xaxis.ticktext))
        monthly = volume_figure([{"Period": "2026-11-01", "Inquiries": 150, "Interval": "Month"}])
        self.assertEqual(list(monthly.layout.xaxis.ticktext), ["Nov 2026"])
        self.assertIn("%Y", monthly.data[0].hovertemplate)

    def test_category_layouts_and_colors(self):
        self.assertEqual(
            category_figure([{"Category": "HVAC", "Leads": 1}], "service").data[0].orientation, "h"
        )
        fig = category_figure([{"Category": "Emergency", "Leads": 1}], "urgency")
        self.assertEqual(fig.data[0].marker.color[0], "#dc2626")
        self.assertEqual(fig.layout.yaxis.dtick, 1)
        self.assertEqual(len(category_figure([], "service").data[0].x), 0)


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "demo_data"
        self.patch = patch.object(demo, "DEMO_ROOT", self.root)
        self.patch.start()
        self.path = self.root / "fixture.db"

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def rows(self, path, table):
        with closing(sqlite3.connect(path)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute("SELECT * FROM " + table + " ORDER BY rowid")]

    def test_reproducible_realistic_fixture_and_integrity(self):
        demo.generate_demo(self.path, as_of=REFERENCE, seed=42)
        second = self.root / "second.db"
        demo.generate_demo(second, as_of=REFERENCE, seed=42)
        for table in ["leads", "followup_tasks", "demo_metadata"]:
            self.assertEqual(self.rows(self.path, table), self.rows(second, table))
        leads = self.rows(self.path, "leads")
        tasks = self.rows(self.path, "followup_tasks")
        self.assertEqual(len(leads), 150)
        self.assertEqual(len(tasks), 150)
        dates = {parse_utc(lead["created_at"]).astimezone(LOCAL_ZONE).date() for lead in leads}
        self.assertEqual(len(dates), 90)
        self.assertEqual((max(dates) - min(dates)).days, 89)
        self.assertEqual(len({lead["name"] for lead in leads}), 150)
        self.assertEqual(len({lead["service"] for lead in leads}), 7)
        self.assertEqual(len({lead["urgency"] for lead in leads}), 4)
        self.assertEqual(len({lead["status"] for lead in leads}), 5)
        self.assertTrue(all(lead["email"].endswith("@example.invalid") for lead in leads))
        self.assertEqual(
            {report_task_state(task, REFERENCE) for task in tasks},
            {"Pending", "Overdue", "Completed"},
        )
        for lead, task in zip(leads, tasks):
            created = parse_utc(lead["created_at"])
            self.assertEqual(parse_utc(task["due_at"]), followup_deadline(lead["urgency"], created))
            self.assertLessEqual(created, REFERENCE)
            if task["completed_at"]:
                self.assertLessEqual(created, parse_utc(task["completed_at"]))
                self.assertLessEqual(parse_utc(task["completed_at"]), REFERENCE)
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_no_overwrites_or_operational_paths_and_environment_restored(self):
        operational = Path(self.temp.name) / "operational.db"
        operational.write_bytes(b"untouched")
        with patch.dict(os.environ, CONTRACTORFLOW_DB_PATH=str(operational)):
            demo.generate_demo(self.path, as_of=REFERENCE)
            self.assertEqual(os.environ["CONTRACTORFLOW_DB_PATH"], str(operational))
        original = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            demo.generate_demo(self.path, as_of=REFERENCE)
        self.assertEqual(self.path.read_bytes(), original)
        for path in [operational, self.root / ".." / "escape.db", self.root / "wrong.sqlite"]:
            with self.assertRaises(ValueError):
                demo.generate_demo(path, as_of=REFERENCE)
        self.assertEqual(operational.read_bytes(), b"untouched")
        with self.assertRaises(ValueError):
            demo.generate_demo(self.root / "bad.db", as_of="not a date")
        self.assertFalse((self.root / "bad.db").exists())

    def test_launcher_explicitly_overrides_database_for_child_only(self):
        demo.generate_demo(self.path, as_of=REFERENCE)
        with (
            patch.dict(os.environ, CONTRACTORFLOW_DB_PATH="operational.db"),
            patch("demo.subprocess.call", return_value=0) as run,
        ):
            self.assertEqual(demo.launch_demo(self.path), 0)
            env = run.call_args.kwargs["env"]
            self.assertEqual(env["CONTRACTORFLOW_DB_PATH"], str(self.path.resolve()))
            self.assertEqual(env["CONTRACTORFLOW_DEMO"], "1")
            self.assertEqual(os.environ["CONTRACTORFLOW_DB_PATH"], "operational.db")
            self.assertIn("127.0.0.1", run.call_args.args[0])
            self.assertIn("8502", run.call_args.args[0])
        with self.assertRaises(ValueError):
            demo.launch_demo(self.root / "missing.db")

    def test_demo_dashboard_smoke(self):
        from streamlit.testing.v1 import AppTest

        demo.generate_demo(self.path, as_of=REFERENCE)
        with (
            patch.dict(os.environ, CONTRACTORFLOW_DB_PATH=str(self.path), CONTRACTORFLOW_DEMO="1"),
            patch("followups.utc_now", return_value=REFERENCE),
        ):
            app = AppTest.from_file(str(demo.ROOT / "main.py"), default_timeout=10).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, "150")
            self.assertTrue(any("Fictional" in alert.value for alert in app.info))
            self.assertEqual(len(app.get("plotly_chart")), 4)
            for period in ["Last 7 days", "Last 30 days", "Last 90 days", "All time"]:
                app.selectbox[0].set_value(period).run()
                self.assertFalse(app.exception)
            app.sidebar.radio[0].set_value("Task Management").run()
            self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
