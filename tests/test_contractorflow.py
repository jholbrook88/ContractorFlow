"""Tests always isolate storage from the real customer database."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import database as db
from followups import followup_deadline, task_state, timestamp


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.db'
        self.env = patch.dict(os.environ, CONTRACTORFLOW_DB_PATH=str(self.path))
        self.env.start()
        db.initialize_database()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def add(self, urgency='Normal'):
        return db.add_lead(' Ada ', ' ada@example.com ', '123', 'Plumbing', 'Leak', urgency)

    def test_deadlines_and_single_task(self):
        now = datetime(2026, 11, 2, tzinfo=timezone.utc)
        for urgency, hours in [('Low', 72), ('Normal', 24), ('High', 4), ('Emergency', 1)]:
            with self.subTest(urgency=urgency), patch('database.utc_now', return_value=now):
                lead_id = self.add(urgency)
                tasks = [t for t in db.get_tasks() if t['lead_id'] == lead_id]
                self.assertEqual(len(tasks), 1)
                self.assertEqual(tasks[0]['due_at'], timestamp(now + timedelta(hours=hours)))
        self.assertEqual(db.get_leads()[0]['name'], 'Ada')

    def test_legacy_migration_preserves_all_values(self):
        legacy = Path(self.temp.name) / 'legacy.db'
        # Exact original schema/code, obtained from the checkpoint, is not needed at runtime.
        with db.connection() as source, closing(sqlite3.connect(legacy)) as target:
            schema = source.execute("SELECT sql FROM sqlite_master WHERE name='leads'").fetchone()[0]
            target.execute(schema)
            target.execute("INSERT INTO leads VALUES (17,'Original','a@b','555','HVAC','Notes','High','Quoted','2020-01-01 10:00:00')")
            target.commit()
            before = target.execute('SELECT * FROM leads').fetchall()
        with patch.dict(os.environ, CONTRACTORFLOW_DB_PATH=str(legacy)):
            db.initialize_database()
            db.initialize_database()
            with db.connection() as conn:
                self.assertEqual([tuple(r) for r in conn.execute('SELECT * FROM leads')], before)
            self.assertEqual(db.get_tasks(), [])
            self.assertGreater(self.add(), 17)

    def test_atomic_rollback_when_task_insert_fails(self):
        with db.connection() as conn:
            conn.execute("CREATE TRIGGER reject_task BEFORE INSERT ON followup_tasks BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.add()
        self.assertEqual(db.get_leads(), [])
        self.assertEqual(db.get_tasks(), [])

    def test_validation_writes_nothing(self):
        for urgency in ['Unknown', 'normal', '']:
            with self.assertRaises(ValueError):
                self.add(urgency)
        with self.assertRaises(ValueError):
            db.add_lead(' ', 'a@b', '', 'HVAC', '', 'Normal')
        self.assertEqual(db.get_leads(), [])

    def test_completion_is_persistent_and_idempotent(self):
        self.add()
        task_id = db.get_tasks()[0]['id']
        self.assertEqual(db.complete_task(task_id), 1)
        original = db.get_tasks()[0]['completed_at']
        self.assertEqual(db.complete_task(task_id), 0)
        db.initialize_database()
        self.assertEqual(db.get_tasks()[0]['completed_at'], original)
        self.assertEqual(db.get_leads()[0]['status'], 'New')
        self.assertEqual(db.complete_task(999), 0)

    def test_status_updates_and_validation(self):
        lead_id = self.add()
        for status in ['Contacted', 'Quoted', 'Won', 'Lost', 'New']:
            self.assertEqual(db.update_lead_status(lead_id, status), 1)
            self.assertEqual(db.get_leads()[0]['status'], status)
        with self.assertRaises(ValueError):
            db.update_lead_status(lead_id, 'invalid')
        self.assertEqual(db.update_lead_status(999, 'New'), 0)

    def test_foreign_key_and_unique_task_constraints(self):
        self.add()
        task = db.get_tasks()[0]
        for lead_id in [task['lead_id'], 999]:
            with self.assertRaises(sqlite3.IntegrityError), db.connection() as conn:
                conn.execute('INSERT INTO followup_tasks (lead_id, created_at, due_at) VALUES (?,?,?)',
                             (lead_id, task['created_at'], task['due_at']))

    def test_queries_preserve_literal_input(self):
        name = "O'Brien; DROP TABLE leads;--"
        db.add_lead(name, 'a@b', '', 'HVAC', '', 'Normal')
        self.assertEqual(db.get_leads()[0]['name'], name)

    def test_state_boundary_and_completed_overdue(self):
        now = datetime(2026, 11, 2, tzinfo=timezone.utc)
        task = {'due_at': timestamp(now), 'completed_at': None}
        self.assertEqual(task_state(task, now), 'Pending')
        self.assertEqual(task_state(task, now + timedelta(microseconds=1)), 'Overdue')
        task['completed_at'] = timestamp(now)
        self.assertEqual(task_state(task, now + timedelta(days=1)), 'Completed')
        with self.assertRaises(ValueError):
            timestamp(datetime(2026, 11, 2))


class UITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, CONTRACTORFLOW_DB_PATH=str(Path(self.temp.name) / 'ui.db'))
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_inquiry_to_dashboard_to_completion(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'main.py')).run()
        self.assertFalse(app.exception)
        app.sidebar.radio[0].set_value('Customer Inquiries').run()
        app.button[0].click().run()
        self.assertTrue(app.error)
        self.assertEqual(db.get_leads(), [])
        app.text_input[0].set_value('Test customer')
        app.text_input[1].set_value('test@example.com')
        app.selectbox[1].set_value('Emergency')
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(db.get_leads()), 1)
        self.assertEqual(len(db.get_tasks()), 1)
        app.sidebar.radio[0].set_value('Lead Management').run()
        app.selectbox[1].set_value('Contacted')
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(db.get_leads()[0]['status'], 'Contacted')
        # Make the task overdue to verify dashboard and filters.
        with db.connection() as conn:
            conn.execute("UPDATE followup_tasks SET due_at='2020-01-01T00:00:00.000000+00:00'")
        app.sidebar.radio[0].set_value('Dashboard').run()
        self.assertFalse(app.exception)
        self.assertEqual([m.value for m in app.metric], ['1', '0', '1', '1'])
        app.sidebar.radio[0].set_value('Task Management').run()
        app.selectbox[0].set_value('Overdue').run()
        self.assertFalse(app.exception)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIsNotNone(db.get_tasks()[0]['completed_at'])
        app.selectbox[0].set_value('Completed').run()
        self.assertEqual(len(app.dataframe[0].value), 1)
        app.sidebar.radio[0].set_value('Dashboard').run()
        self.assertEqual([m.value for m in app.metric][-2:], ['0', '0'])
        app.sidebar.radio[0].set_value('Settings').run()
        self.assertFalse(app.exception)

    def test_empty_pages(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'main.py')).run()
        for page in ['Dashboard', 'Lead Management', 'Task Management', 'Settings']:
            app.sidebar.radio[0].set_value(page).run()
            self.assertFalse(app.exception)


if __name__ == '__main__':
    unittest.main()
