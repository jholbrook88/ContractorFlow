# ContractorFlow

Local business automation for small contractors, built with Python, Streamlit and SQLite. Includes customer inquiries, lead status management, lead metrics, automatic follow-up tasks and completion history. No paid services or external APIs are required.

## Setup and run

Tested with Python 3.14, Streamlit 1.66.1 and pandas 3.1.0.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run main.py
```

Open the local address printed by Streamlit. Keep the app on a trusted local computer; authentication and production hosting are not configured.

## Workflow

- Submit an inquiry with customer name, email, service and urgency.
- Every successful submission saves one lead and one follow-up in a single SQLite transaction. A failed task insert rolls back the lead too.
- Deadlines use elapsed time from submission: **Emergency: 1 hour; High: 4 hours; Normal: 24 hours; Low: 72 hours**. Weekends and holidays count.
- Dashboard pending count includes every unfinished task; overdue is the subset whose deadline has passed. Refresh or navigate to recalculate the display.
- Task Management supports Open, Overdue, Completed and All views, includes customer contact details, and records completion time. Completion is idempotent and independent of lead status.
- Lead Management retains the original New, Contacted, Quoted, Won and Lost statuses.
- Task timestamps display in UTC. Original lead timestamps retain SQLite's existing UTC format.

## Architecture and storage

- `main.py`: Streamlit forms, dashboard, lead and task management, settings.
- `database.py`: parameterized SQLite operations, connection lifecycle and additive schema initialization.
- `followups.py`: urgency policy, UTC timestamp formatting and task state calculation.
- `tests/test_contractorflow.py`: storage/policy tests and headless Streamlit interaction tests.

By default, data lives in `contractorflow.db` beside the application, independent of the working directory. Optionally set `CONTRACTORFLOW_DB_PATH` to an absolute SQLite path (the parent directory must exist). Tests always override it to temporary storage.

Initialization preserves the original `leads` schema and all existing records. It adds `followup_tasks` and an index only if absent. Repeated initialization is safe. Tasks have a unique lead reference and enforced foreign keys. Historical leads are intentionally not backfilled; only new submissions create tasks. Future schema changes must remain additive or use explicit, tested migrations with backups.

Connections commit or roll back and close explicitly, with a 10-second SQLite lock timeout. SQLite is suitable for local use; multi-user deployments need additional operational planning.

## Tests

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

No extra test dependencies are needed. Tests cover all urgency deadlines, legacy migration preservation, transaction rollback, validation, foreign keys, task uniqueness, completion persistence, status updates, overdue boundaries, literal SQL-like input, empty views and the inquiry-to-completion UI workflow. Tests never use the real database.

## Backup and source control

Git excludes virtual environments, databases and their journals, backups, secrets, environment files, caches and machine-local configuration. Git is not a database backup. Keep separate secured SQLite backups; use SQLite's backup API for a consistent snapshot while the application is open. Do not copy an active database file directly.

The initial local source checkpoint is commit `3d06c4f`. A pre-change SQLite backup is stored locally at `backups/before-followups.db`; it contains private data and is intentionally untracked. Stop the application before any manual restore, retain a copy of the current database, and restore only after verifying the intended backup. No restore is needed for this upgrade.

The checkpoint uses the per-command author `ContractorFlow local checkpoint <checkpoint@localhost>` because Git had no user identity configured. No global Git settings were changed. Set your own Git identity before creating personal commits. Nothing is pushed or deployed automatically.

## Next steps

Before commercial use, add authentication/authorization, stronger email and phone validation, backup/restore tooling, configurable business hours and time zones, pagination and a deployment/security review. Follow-ups are local tasks; this version does not send email, SMS or background notifications. Each explicit form submission is a new inquiry; duplicate-submission detection is not implemented.
