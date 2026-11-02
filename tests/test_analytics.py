"""Deterministic dashboard calculations, New York filters, and CSV contracts."""

import csv
import io
import unittest
from datetime import datetime, timedelta, timezone

from analytics import (
    DATE_RANGES,
    LOCAL_ZONE,
    calculate_kpis,
    category_counts,
    export_csv,
    filter_records,
    inquiry_volume,
    local_timestamp,
    localize_records,
    parse_utc,
    pipeline_report,
    report_task_state,
)

NOW = datetime(2026, 11, 2, 17, tzinfo=timezone.utc)


class AnalyticsTests(unittest.TestCase):
    def test_kpis_and_zero_denominator(self):
        leads = [{"status": s} for s in ["New", "Contacted", "Quoted", "Won", "Lost", None]]
        tasks = [
            {"due_at": "2026-11-02T16:00:00Z"},
            {"due_at": NOW.isoformat()},
            {"due_at": None},
            {"completed_at": "2026-11-01T10:00:00Z", "due_at": "2020-01-01"},
        ]
        kpis = calculate_kpis(leads, tasks, NOW)
        self.assertAlmostEqual(kpis.pop("conversion_rate"), 100 / 6)
        self.assertEqual(
            kpis,
            {
                "total_leads": 6,
                "new_inquiries": 1,
                "pending_tasks": 3,
                "overdue_tasks": 1,
                "completed_followups": 1,
            },
        )
        empty = calculate_kpis([], [], NOW)
        self.assertIsNone(empty["conversion_rate"])
        self.assertEqual(empty["pending_tasks"], 0)

    def test_filters_all_ranges_calendar_boundaries(self):
        for label, days in DATE_RANGES.items():
            if days is None:
                continue
            with self.subTest(label=label):
                start_date = NOW.astimezone(LOCAL_ZONE).date() - timedelta(days=days - 1)
                start = datetime.combine(start_date, datetime.min.time(), LOCAL_ZONE).astimezone(
                    timezone.utc
                )
                records = [
                    {"id": 1, "created_at": start.isoformat()},
                    {"id": 2, "created_at": (start - timedelta(microseconds=1)).isoformat()},
                    {"id": 3, "created_at": NOW.isoformat()},
                    {"id": 4, "created_at": (NOW + timedelta(microseconds=1)).isoformat()},
                    {"id": 5, "created_at": "invalid"},
                    {"id": 6},
                ]
                self.assertEqual([r["id"] for r in filter_records(records, label, NOW)], [1, 3])
                self.assertEqual(filter_records(records, "All time", NOW), records)
        with self.assertRaises(KeyError):
            filter_records([], "Invalid", NOW)

    def test_local_time_handles_dst_and_legacy_utc(self):
        self.assertEqual(local_timestamp("2026-07-01 12:00:00"), "2026-07-01 08:00:00-04:00")
        self.assertEqual(local_timestamp("2026-01-01T12:00:00Z"), "2026-01-01 07:00:00-05:00")
        # Both instants map to 1:30am, but different offsets disambiguate fallback.
        self.assertEqual(local_timestamp("2026-11-01T05:30:00Z"), "2026-11-01 01:30:00-04:00")
        self.assertEqual(local_timestamp("2026-11-01T06:30:00Z"), "2026-11-01 01:30:00-05:00")
        self.assertEqual(local_timestamp(None), "")
        self.assertEqual(local_timestamp("bad"), "Unknown")
        self.assertIsNone(parse_utc("bad"))
        original = [{"created_at": "2026-01-01 12:00:00", "name": "Test"}]
        displayed = localize_records(original)
        self.assertNotEqual(displayed, original)
        self.assertEqual(original[0]["created_at"], "2026-01-01 12:00:00")

    def test_spring_forward_filter(self):
        now = datetime(2026, 3, 10, 12, tzinfo=timezone.utc)
        records = [
            {"id": 1, "created_at": "2026-03-04T04:59:59Z"},
            {"id": 2, "created_at": "2026-03-04T05:00:00Z"},
        ]
        self.assertEqual(filter_records(records, "Last 7 days", now), records[1:])

    def test_pipeline_and_missing_categories(self):
        leads = [
            {"status": "Won", "service": "HVAC"},
            {"status": None, "service": " "},
            {"status": "Legacy", "service": None},
        ]
        pipeline = pipeline_report(leads)
        self.assertEqual(
            [r["Category"] for r in pipeline[:5]], ["New", "Contacted", "Quoted", "Won", "Lost"]
        )
        self.assertEqual(sum(r["Leads"] for r in pipeline), 3)
        self.assertEqual(
            dict((r["Category"], r["Leads"]) for r in category_counts(leads, "service")),
            {"HVAC": 1, "Unknown": 2},
        )
        self.assertEqual(len(pipeline_report([])), 5)

    def test_timeline_local_days_gaps_and_missing_dates(self):
        leads = [
            {"created_at": "2026-11-01T03:59:59Z"},  # Oct 31 locally
            {"created_at": "2026-11-02T05:00:00Z"},  # Nov 2 locally
            {"created_at": None},
            {"created_at": "bad"},
        ]
        volume = inquiry_volume(leads, now=NOW)
        self.assertEqual(
            [(r["Period"], r["Inquiries"]) for r in volume],
            [("2026-10-31", 1), ("2026-11-01", 0), ("2026-11-02", 1)],
        )
        self.assertEqual(len(inquiry_volume(leads[:1], "Last 7 days", NOW)), 7)
        self.assertEqual(inquiry_volume([{"created_at": None}]), [])

    def test_monthly_bins_for_long_spans(self):
        volume = inquiry_volume(
            [{"created_at": "2024-01-01 12:00:00"}, {"created_at": "2026-01-01 12:00:00"}]
        )
        self.assertEqual(len(volume), 25)
        self.assertEqual(volume[0]["Interval"], "Month")
        self.assertEqual(sum(r["Inquiries"] for r in volume), 2)

    def test_exports_roundtrip_headers_local_dates_and_formula_escape(self):
        leads = [
            {
                "id": 1,
                "name": 'Doe, "Jane"\nSecond line',
                "email": '=HYPERLINK("bad")',
                "phone": "+15551234567",
                "description": "\t@SUM(A1)",
                "created_at": "2026-07-01 12:00:00",
            }
        ]
        blob = export_csv(leads, "leads", NOW)
        self.assertTrue(blob.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.DictReader(io.StringIO(blob.decode("utf-8-sig"))))
        self.assertEqual(rows[0]["name"], leads[0]["name"])
        self.assertEqual(rows[0]["email"], "'" + leads[0]["email"])
        self.assertEqual(rows[0]["phone"], "'+15551234567")
        self.assertEqual(rows[0]["description"], "'\t@SUM(A1)")
        self.assertEqual(rows[0]["created_at (America/New_York)"], "2026-07-01 08:00:00-04:00")
        for report in ["leads", "tasks"]:
            empty = list(csv.reader(io.StringIO(export_csv([], report).decode("utf-8-sig"))))
            self.assertEqual(len(empty), 1)
            self.assertIn("created_at (America/New_York)", empty[0])
        with self.assertRaises(ValueError):
            export_csv([], "invalid")

    def test_task_export_state_and_unknown_deadlines(self):
        tasks = [
            {"id": 1, "due_at": "2026-11-02T16:00:00Z"},
            {"id": 2, "due_at": "bad"},
            {"id": 3, "completed_at": "2026-11-01T05:30:00Z"},
        ]
        rows = list(
            csv.DictReader(io.StringIO(export_csv(tasks, "tasks", NOW).decode("utf-8-sig")))
        )
        self.assertEqual([r["state"] for r in rows], ["Overdue", "Unknown deadline", "Completed"])
        self.assertEqual(report_task_state({"due_at": NOW.isoformat()}, NOW), "Pending")
        # Display precision must not change deadline comparisons in CSV reports.
        due = NOW + timedelta(microseconds=1)
        blob = export_csv([{"due_at": due.isoformat()}], "tasks", NOW)
        row = next(csv.DictReader(io.StringIO(blob.decode("utf-8-sig"))))
        self.assertEqual(row["state"], "Pending")


if __name__ == "__main__":
    unittest.main()
