# ContractorFlow

Local business automation for small contractors, built with Python, Streamlit and SQLite. Includes customer inquiries, lead status management, lead metrics, automatic follow-up tasks and completion history. No paid services or external APIs are required.

## Setup and run

Tested with Python 3.14, Streamlit 1.66.1, pandas 3.1.0 and Plotly 7.1.0. The tzdata package provides portable New York timezone rules, including on Windows.

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
- All displayed and exported timestamps use America/New_York with explicit UTC offsets, including daylight saving time. SQLite values remain UTC; legacy naive lead timestamps are interpreted as UTC.

## Architecture and storage

- `main.py`: Streamlit forms, dashboard, lead and task management, settings.
- `database.py`: parameterized SQLite operations, connection lifecycle and additive schema initialization.
- `followups.py`: urgency policy, UTC timestamp formatting and task state calculation.
- `analytics.py`: read-only KPI calculations, calendar filters, category/pipeline aggregation, local timestamp formatting and CSV exports.
- `tests/test_analytics.py`: analytics, timezone, filter and export tests.
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


## Business intelligence dashboard (0.3.0)

The dashboard provides six KPI cards, interactive Plotly service/urgency/status charts, a pipeline report with every standard stage, an inquiry timeline, pending tasks, lead details and two CSV downloads. Plotly runs locally and requires no service account. Bar charts use the [official Plotly API](https://plotly.com/python/bar-charts/).

Date ranges are Last 7, 30, 90 days and All time (default). Last N days starts at New York midnight N-1 days ago and ends at the current instant. This uses calendar days rather than N times 24 hours, accounting for daylight saving transitions. Future dates are excluded from finite windows. All time includes all records, even those with unknown or future timestamps.

Leads use submission dates; tasks independently use task creation dates. All task KPIs and task exports use that same creation cohort, including completed tasks whose completion happened later. They do not measure how many completions occurred during the period. Current lead/task states are evaluated at refresh time. Historical status transitions are not stored and no historical conversion funnel is inferred.

Conversion rate is Won divided by all filtered leads, including open/lost/unknown statuses. Empty cohorts show N/A. New inquiries means currently New leads. Pending includes all unfinished tasks; overdue is the subset with known deadlines earlier than now. A task due exactly now remains pending. Completion does not change lead status.

Missing categories are labeled Unknown; unrecognized statuses remain visible alongside the five standard pipeline stages. Records with unknown dates are flagged and included only in All time, never in the timeline. Tasks without valid deadlines count as pending and show Unknown deadline. Missing/invalid display dates remain blank/Unknown. Small datasets show a caution; there are no invented revenue or trend metrics.

The timeline counts inquiries by New York day and fills zero days between dates (or throughout a finite range). All-time spans over 366 days use monthly bins to avoid an excessively dense chart. All time spans the earliest through latest valid inquiry dates, not dates before the first inquiry.

CSV exports contain the selected filtered records, stable headers even when empty, New York timestamps with UTC offsets, and a UTF-8 BOM for spreadsheet compatibility. Commas, quotes and newlines are handled by the standard CSV writer. Text that could be interpreted as a spreadsheet formula is prefixed with an apostrophe; this can also affect phone numbers beginning with +. Downloads include customer contact information.

The pre-analytics source checkpoint is `187d39f`; the local database backup is `backups/before-analytics.db`. This milestone requires no database schema or stored-data changes. Analytics tests use isolated temporary databases.
