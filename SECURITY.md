# Security

## Supported use

Run ContractorFlow on a trusted local computer. The default server binds to 127.0.0.1. Use only fictional data for demonstrations. There is no authentication or authorization layer; possession of local access is the trust boundary.

## Controls

- Parameterized queries and enforced SQLite foreign keys.
- Server-side required-field, email, phone, enumeration and length validation.
- Atomic intake writes and persistent idempotency keys.
- Spreadsheet formula escaping in the application-generated CSV reports.
- Plain-text notification previews; no HTML rendering of customer message bodies.
- Local-only delivery factory, forced local mode in demos, and rejection of live mode.
- Safe error messages; notification failures store exception types instead of arbitrary exception text.
- Databases, journals, backups, secrets, IDE settings, caches, and review artifacts excluded from Git.
- Local snapshots with integrity verification and non-overwriting recovery.
- Dependency audit and automated quality checks prepared for CI.

## Limitations

SQLite databases and backups are unencrypted. Filesystem permissions, device encryption, backup storage, retention, deletion policies, and access to the host remain the operator's responsibility. Logs should never contain message bodies, emails or credentials. No external email or SMS implementation exists.

Validation checks format and length, not whether contact details belong to a customer. Submission keys prevent retries within the supported workflow; they do not identify the same customer across independent sessions. No spam throttling, consent management, tenant isolation, or public intake abuse controls are implemented.

CSV protection applies to the explicit report downloads. Avoid opening raw database exports or other unreviewed CSV files as spreadsheets. Review any screenshots, exports, and repository history before sharing them.

## Before public deployment

Do not deploy the operational database. A future portfolio host should generate a fresh fictional dataset, use isolated per-session or read-only data, disable external delivery, and provide authentication if any user-specific records are retained. Validate TLS, secret handling, dependency status, resource limits, access control and reset behavior on the chosen host. These deployment controls have not been implemented or validated here.

Report security findings privately to the repository owner. Do not include customer data, database files, or credentials in public issues. A public security contact must be chosen by the owner before publication.
