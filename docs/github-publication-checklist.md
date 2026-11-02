# GitHub publication checklist

Status: prepared locally; publication, deployment and remote pushes are not authorized. MIT licensing was approved November 2, 2026.

## Completed locally

- [x] Add the MIT license and link it from the README.
- [x] Retain existing commit history, attribution and provenance.
- [x] Prepare README, schema/architecture documentation, security limitations and demo instructions.
- [x] Prepare fictional-data generation, local-only notifications and a non-overwriting demo reset.
- [x] Prepare pinned runtime requirements, tests, formatting/linting, scoped type checks and Windows/Python 3.14 CI.
- [x] Exclude operational/demo databases, backups, secrets, local tooling and generated review artifacts.
- [x] Prepare a source/history privacy scan and a local source archive.

## Final owner review

- [ ] Review LICENSE, including the copyright holder shown as Jason.
- [ ] Approve repository name and visibility. Suggested name: `ContractorFlow`.
- [ ] Approve description: Local contractor CRM with customer intake, follow-up automation, SQLite notification previews, and a Streamlit/Plotly analytics dashboard.
- [ ] Approve topics: `python`, `streamlit`, `sqlite`, `plotly`, `crm`, `workflow-automation`, `business-intelligence`, `small-business`.
- [ ] Choose a security contact or GitHub private vulnerability-reporting policy.
- [ ] Select screenshots showing fictional data only; use a clean browser profile without personal overlays.
- [ ] Review the candidate commit, tracked-file list and normal branch/tag history. Confirm no private customer data or credentials appear.
- [ ] Accept the documented limitations: local trust boundary, no authentication, no live delivery, no production worker, and no validated public hosting.
- [ ] Explicitly authorize the intended GitHub publication and push destination.

## Checks immediately before an approved push

Run from the project directory with the development dependencies installed:

```powershell
.venv\Scripts\python -m pytest --cov --cov-report=term-missing --cov-fail-under=85
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
.venv\Scripts\python -m mypy
.venv\Scripts\python -m pip check
.venv\Scripts\python -m pip_audit -r requirements-lock.txt
.venv\Scripts\python scripts/check_repository.py
git diff --check
git status --short
```

- [ ] Resolve failed checks and review any new dependency advisories.
- [ ] Commit only the reviewed source and documentation; inspect the staged diff.
- [ ] Confirm the remote URL and selected branch match the approved destination.
- [ ] Push only the approved branch. Do not use a mirror push or upload the workspace/.git directory; internal local-tool references are outside the publication candidate.
- [ ] Never force-add excluded database, backup, secret or review-artifact files.

## After an approved publication

- [ ] Inspect the first GitHub Actions run; it has not been exercised on GitHub yet.
- [ ] Verify README links, MIT license detection, description, topics and screenshot privacy.
- [ ] Confirm repository contents contain no customer database or generated demo files.
- [ ] Enable the selected private security-reporting/contact policy.
- [ ] Advertise the repository only after the CI results and final contents are reviewed.

Public hosting and live communications require separate explicit approval and additional security implementation. A GitHub source publication does not authorize either action.
