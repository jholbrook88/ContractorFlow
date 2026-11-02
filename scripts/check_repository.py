"""Reject sensitive file types and credential patterns in tracked files and history."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_PARTS = {".venv", ".agents", ".idea", ".junie", "backups", "demo_data", "artifacts"}
BLOCKED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pem", ".key", ".log"}
PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+"),
]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main():
    failures = []
    files = git("ls-files").decode().splitlines()
    for name in files:
        path = Path(name)
        if (
            set(path.parts) & BLOCKED_PARTS
            or path.suffix in BLOCKED_SUFFIXES
            or path.name in (".env", "secrets.toml")
            or ".db-" in path.name
        ):
            failures.append(f"Excluded file tracked: {name}")
        content = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(content) for pattern in PATTERNS):
            failures.append(f"Sensitive pattern in tracked file: {name}")
    objects = git("rev-list", "--objects", "HEAD", "--branches", "--tags").decode().splitlines()
    count = 0
    for entry in objects:
        oid, _, name = entry.partition(" ")
        if not name or git("cat-file", "-t", oid).strip() != b"blob":
            continue
        count += 1
        path = Path(name)
        if set(path.parts) & BLOCKED_PARTS or path.suffix in BLOCKED_SUFFIXES:
            failures.append(f"Excluded file in history: {name}")
        content = git("cat-file", "blob", oid).decode("utf-8", errors="replace")
        if any(pattern.search(content) for pattern in PATTERNS):
            failures.append(f"Sensitive pattern in history: {name}")
    if failures:
        raise SystemExit("\n".join(sorted(set(failures))))
    print(
        f"Publication file scan passed: {len(files)} tracked files; {count} historical blobs. Manual privacy review remains required."
    )


if __name__ == "__main__":
    main()
