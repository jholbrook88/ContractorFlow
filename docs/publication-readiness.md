# Publication readiness review

Reviewed November 2, 2026. Verdict: **READY WITH LIMITATIONS** for a source-code portfolio and a local fictional-data demonstration. **Not approved or hardened for public production deployment.**

## A. Completed features

Customer intake includes server-side validation and persistent retry keys. Lead search, status filters, sorting, status updates, urgency-based tasks, completion history, reporting, date filters and explicit CSV exports are implemented. New inquiries atomically create customer/owner messages. The notification outbox supports local preview processing, history, filtering, one-time upcoming/overdue reminders, cancellation and explicit retry.

The development-only demo generator supplies 150 fictional inquiries and related tasks across 90 calendar dates. Reset creates a new file rather than overwriting the previous dataset. Demo launch forces local communications. Backup/recovery tooling creates verified snapshots and refuses to replace existing or operational destination files.

The existing two operational leads and one follow-up task were compared field-for-field with the pre-notification snapshot and preserved. The migration adds the outbox and intake-submission tables only. Database integrity and foreign-key checks pass.

## B. Validation

| Check | Result |
| --- | --- |
| pytest | 50 passed; 0 failed; 7 passing unittest subtests |
| Coverage | 90.83% across business, persistence and tooling modules; main.py and repository scan script are outside the measured scope |
| Ruff lint | Passed |
| Ruff format check | Passed |
| mypy | Passed for config.py, delivery.py and intake.py |
| Dependency consistency | pip check passed; development requirements install dry-run passed |
| Dependency vulnerability audit | No known vulnerabilities reported for the 35-package runtime lock at review time |
| SQLite | Operational integrity check passed; no foreign-key violations |
| Privacy scan | Tracked candidate and normal branch/tag history passed pattern/path checks; no operational email/phone matches in reviewed source/history |

Tests cover storage, additive initialization, legacy-record preservation, transaction rollback, duplicate submissions and concurrent workers, urgency deadlines, task completion, message templates, reminder boundaries, persistence, retries, sanitized failures, demo isolation, analytics, date filters, DST transitions, CSV escaping, charts, recovery and Streamlit workflows.

A Chrome browser review used a separate fictional review database on 127.0.0.1:8504. Dashboard date labels rendered correctly. A new fictional inquiry and an unchanged repeat submission produced the same inquiry number. Notification history showed local processing with Previewed status and no messages sent. Desktop and 390×844 Notification Center layouts were inspected. Automated AppTest coverage also exercised lead search/status management, task completion, filters, empty views, demo charts and notifications. This is not a complete browser/accessibility/device matrix.

The browser review exposed a mixed-format timestamp sorting bug. Lead and task queries now compare parsed SQLite dates, with a regression test. All tests passed after the cleanup and fix. Browser screenshots are held in ignored local artifacts for human selection; installed browser extension overlays should be removed by using a clean profile for publication captures.

License update verification: after adding the approved MIT license, pytest (50 passed), coverage (90.83%), Ruff lint/format, scoped mypy, pip consistency, development-install dry-run, runtime vulnerability audit, source/history privacy scan, Git whitespace checks, and operational SQLite preservation/integrity checks passed again. The browser review above belongs to the preceding implementation review; this update changes licensing and documentation only.

## C. Security findings

Resolved: parameterized queries, input length/format controls, idempotent intake, atomic writes, local-only adapters, demo delivery enforcement, stale reminder cancellation, explicit report formula escaping, safe error messages, local binding, hidden exception detail, secret/data exclusions and verified snapshots.

Remaining: no authentication, tenant isolation, encryption at rest, production worker, consent/retention system, abuse throttling or provider delivery implementation. Raw database exports and Streamlit's built-in table downloads are not the audited report-export interface. Dependency audits are point-in-time advisories, not proof of security. The repository scan is a targeted pattern review rather than a complete secret-detection service.

The local Git object store contains internal tool snapshot references with an ignored skill-directory link. Those references are not part of the normal publication branch/tag history. They were not rewritten or deleted. Publish only the reviewed branch; do not mirror or upload the .git directory, workspace, or local tool refs. No operational contact matches were found in the reviewed object content.

## D. Deployment recommendation

Prefer a recorded walkthrough or local demonstration for the current release. If a hosted fictional demo is later approved, use a separate environment with ephemeral or per-session generated data, no operational volumes, local-only notification previews, and a restricted/resettable interface. Add authentication if any user-specific records persist. Evaluate the host's storage lifecycle, TLS, access controls, resource limits and backup requirements before deployment. No host has been configured or certified.

## E. GitHub preparation

Prepared: product README, architecture/schema documentation, security limitations, demo/capture guide, safe configuration examples, direct and locked runtime requirements, development requirements, .gitignore, pytest configuration, Ruff formatting/linting, scoped mypy checks, repository scan, and Windows/Python 3.14 GitHub Actions CI.

CI definitions are locally reviewed; they have not run on GitHub. The runtime lock has been checked in the existing Windows/Python 3.14 environment, not through an independently provisioned clean installation. Other platforms are not certified. Developer-tool direct versions are pinned, but their transitive dependencies are not separately locked.

Final repository description: **Local contractor CRM with customer intake, automated follow-ups, SQLite notification previews, and a Streamlit/Plotly analytics dashboard.**

Final topics: `python`, `streamlit`, `sqlite`, `plotly`, `crm`, `workflow-automation`, `business-intelligence`, `small-business`.

The owner approved the MIT license on November 2, 2026. LICENSE contains the standard MIT text with Copyright (c) 2026 Jason Holbrook. Six fictional-data screenshots have been captured in a clean in-app browser and reviewed locally; the owner can review the final gallery before publication. The security contact also remains an owner decision. The final publication checklist is [documented separately](github-publication-checklist.md).

## F. Known limitations

Reminder checks run on app reruns or CLI invocation; no always-running scheduler is installed. A fixed demo snapshot ages against the real clock. Similar inquiries in independent sessions can be distinct records. Status-transition history is not stored, so analytics report current states. Reports load local records in memory and do not implement large-dataset pagination. Local preview processing holds a SQLite write transaction; future network delivery needs leases, provider idempotency and crash-recovery semantics. SMS, revenue, invoicing and paid services are intentionally excluded.

## G. Approval checklist

Before public publication, the owner must:

1. Review the publication candidate, documentation, commit authorship and privacy scan scope.
2. Completed: MIT license approved and added; copyright attribution updated to Jason Holbrook as approved.
3. Select reviewed fictional-data screenshots and a security contact.
4. Approve the GitHub repository name, description, topics and visibility.
5. Explicitly approve publishing/pushing the reviewed branch. Do not use a mirror push.
6. After any approved push, inspect the first CI run before advertising the project.

Public hosting and live email/SMS require separate explicit approval, implementation and security validation. No publication, deployment, external messaging or credential setup has occurred in this work.

## H. Codebase and authorship cleanup

Formatting and imports are standardized with Ruff. Duplicate timestamp parsing/task-state logic was consolidated. Shared configuration and intake validation have dedicated modules. Redundant comments and placeholder settings were removed. Documentation now describes behavior, contracts and limitations rather than development narration or promotional claims. Developer instructions, chats, caches, database files and generated artifacts are excluded from the publication candidate.

Existing commits and attribution remain intact. No authorship, provenance, license or commit history was fabricated or rewritten. Local implementation commits describe the resulting changes. Remaining comments document invariants, security choices and non-obvious date/transaction behavior.


Portfolio asset update: six JPEG screenshots are included in docs/screenshots, with a gallery in [github-portfolio.md](github-portfolio.md). The dashboard/charts show the original 150-row fictional snapshot; the intake and Notification Center views demonstrate an additional fictional inquiry. Images contain no operational records, browser account overlays, local paths or EXIF metadata. Repository description/topics are finalized locally in .github/repository-metadata.json; no remote settings were changed.


Final attribution review: the owner approved Copyright (c) 2026 Jason Holbrook and developer attribution in the README. Existing commits, author metadata and historical first-name notices remain unchanged. The approved public name is intentional; operational contact information, credentials, databases and local artifacts are excluded from the publication candidate. Publication still requires separate explicit approval.
