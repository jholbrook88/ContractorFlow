# Streamlit Community Cloud portfolio demo

Status: deployed at [contractorflow.streamlit.app](https://contractorflow.streamlit.app/). The read-only demo was merged through [pull request #1](https://github.com/jholbrook88/ContractorFlow/pull/1) after Windows and Ubuntu CI passed. A separate browser session loaded the dashboard without signing in.

## Deployment fields

| Field | Select |
| --- | --- |
| Repository | `jholbrook88/ContractorFlow` |
| Branch | `main` |
| Main file path | `cloud_demo/streamlit_app.py` |
| Advanced settings: Python | **3.14** |
| App URL / subdomain | `contractorflow` |
| Secrets | Leave empty; none are needed |

The deployed entry point is `cloud_demo/streamlit_app.py`, not `main.py`. The feature branch remains available as development history; hosting follows the reviewed main branch.

## Data and notification boundaries

The entry point uses `public_demo.build_snapshot`, which creates a fresh `:memory:` SQLite database with the same schema and 150-customer generator as the existing local demo. It never reads an existing database, selects a database path or changes process environment variables. It calls the explicitly supplied-connection schema/fixture helpers, not the operational storage API. The connection enables `PRAGMA query_only=ON` before reporting and is closed after returning plain record copies.

The generated data uses `example.invalid` email addresses, fictional 555-01xx phone numbers and marked fictional project descriptions. The snapshot includes leads, tasks and notification message snapshots. Confirmation and owner previews use the existing message templates. Reminder previews are included only when their task deadlines qualify; a filter with no qualifying messages returns an empty state rather than invented events.

Notifications have local Previewed status with no sent timestamp. No delivery adapter, scheduler, email credentials, SMS service or outbox processor is called by the public entry point. A generated Previewed fixture is a demonstration snapshot, not evidence of communication.

No visitor can submit an inquiry, change a lead, complete a follow-up or process messages. Intake is an example display; editing buttons are disabled and have no write callback. There are no uploads, customer contact forms, file selectors, authentication requirements or operational settings. Filters and widget selections are per Streamlit visitor session. Reports and downloads contain only the generated fictional data.

Streamlit caches the serializable snapshot in memory for up to one hour with one cache entry; cache reads provide copies. All visitors may see the same fictional snapshot, but there is no shared writable database or editing interface. Reports use the snapshot's reference time so overdue counts stay consistent during exploration. A rerun after cache expiry generates a fresh snapshot. A host restart also regenerates it; there is nothing to recover or persist. No reset button is needed for a read-only demo.

## Local application preservation

`main.py` remains the editable local application. Its root `.streamlit/config.toml` remains bound to `127.0.0.1`. The dedicated `cloud_demo/.streamlit/config.toml` sets `0.0.0.0` for hosting, with CORS and XSRF protection enabled. The installed Streamlit configuration loader was tested for both entry points.

The dashboard rendering was extracted into `dashboard.py` and is reused by both entry points. Schema setup and fictional population now accept explicit connections; local wrappers retain their existing storage behavior. The existing regression suite passes. No operational database or existing demo database was opened for this preparation, and no historical customer/task records were rewritten.

To preview locally while keeping the server on loopback:

```powershell
.venv\Scripts\python -m streamlit run cloud_demo/streamlit_app.py --server.address=127.0.0.1
```

## Runtime and Linux preparation

The supported deployment target is CPython 3.14, matching the tested development environment. Select it explicitly; do not rely on Community Cloud's default. `cloud_demo/requirements.txt` references the existing pinned `requirements-lock.txt`. Streamlit 1.66.1 was confirmed to be the latest available version during this preparation. No new runtime packages, apt packages, credentials, databases or external APIs are required.

All 35 pinned runtime packages successfully resolved/downloaded as CPython 3.14 compatible Linux x86-64 wheels or universal wheels. This proves wheel availability and dependency resolution, not that the application has run on Debian. Docker was unavailable and WSL was not installed, so local Linux execution was not attempted. Subsequent GitHub CI passed on both Windows and Ubuntu with Python 3.14, including all 59 tests and startup checks. The Community Cloud build then succeeded and the deployed application rendered in the browser.

Community Cloud runs from the repository root and loads script-level configuration after root configuration. Its hosting platform can override configuration, including telemetry and error display. The demo requires no application-managed secrets, but Streamlit/GitHub still provide the hosting platform and its normal access logs/telemetry. Do not claim the hosted platform is offline or collects no connection metadata.

## Checks completed locally

- Full pytest suite: 59 passed, including the original local workflows and nine public-demo checks. Coverage and final quality results are recorded in the task report.
- AppTest rendered all six public pages, four dashboard date filters, charts and CSV controls; a second visitor's filters remain independent.
- Public-demo tests reject file-backed SQLite connections, operational initialization and all configured delivery/processing calls, even with a hostile database-path or delivery-mode environment. Sentinel data remains untouched and process configuration unchanged.
- Generated data integrity, read-only SQL, closed connections, fictional contact details, preview-only messages and invalid snapshot-time handling were verified.
- A localhost-only server startup probe returned HTTP 200 for health and root, without creating the sentinel operational file. AppTest separately verifies actual page execution; HTTP health alone is not treated as a UI test.
- The application code and configuration do not require Windows-specific paths or libraries. Linux binary dependencies resolved as above.

Reproduce the checks:

```powershell
.venv\Scripts\python -m pytest --cov --cov-report=term-missing --cov-fail-under=85
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
.venv\Scripts\python -m mypy
.venv\Scripts\python -m pip check
.venv\Scripts\python -m pip_audit -r requirements-lock.txt
.venv\Scripts\python scripts/check_cloud_startup.py
.venv\Scripts\python scripts/check_repository.py
```

The repository scan checks tracked files and reachable normal history for blocked artifacts and credential patterns. It is not proof against every possible secret; do not add databases, secrets, backups or review output to the approved diff.

## Deployment procedure for future setup or recovery

1. For future changes, review and approve the diff before pushing/merging it. No new GitHub repository is needed. Require the Windows and Ubuntu CI jobs on that revision to pass before hosting it.
2. In the existing Streamlit Community Cloud deployment screen, connect your GitHub account if requested and select the repository, approved branch and exact file path in the table above. These owner setup steps require an account; public visitors do not.
3. Enter `contractorflow` for the subdomain. If unavailable, stop and agree on another name; do not claim the requested URL is reserved.
4. Open Advanced settings, choose Python 3.14 and leave Secrets empty. If 3.14 is not offered, stop and revalidate a supported target rather than silently changing versions.
5. Only after deployment approval, select Deploy and inspect the build/startup logs. Check that no secret or operational database is configured or copied.
6. In app settings, open Sharing and choose public visibility. Verify the actual URL in a private/incognito browser window while signed out of GitHub and Streamlit. Confirm the dashboard appears without a visitor account.
7. In two independent browser sessions, compare filters, navigate every page, preview messages and download the fictional reports. Browser navigation and a cross-session filter check passed for the initial deployment; CSV contents are covered by automated export tests, while a hosted download has not been independently inspected. Check the Demo Mode banner, mobile layout, chart interactions and absence of editable records. AppTest cannot certify the actual Cloud proxy or frontend display.
8. Record the deployed revision and actual URL. Only then add the working live-demo link to the repository README and, after separate review, the profile README. Do not insert a guessed link.

Community Cloud may sleep or restart an inactive application. Initial public access was verified in a browser session separate from the signed-in owner session. Wake-up after prolonged inactivity, broad mobile/accessibility coverage and sustained load testing remain unverified. This demo does not promise an uptime guarantee.

Official references:

- [Deploy an app and select Python](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Repository and entry-point configuration](https://docs.streamlit.io/deploy/streamlit-community-cloud/status)
- [Dependency files](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
- [Public sharing settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app)
