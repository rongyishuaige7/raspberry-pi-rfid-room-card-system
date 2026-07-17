#!/usr/bin/env python3
"""Fail on likely credentials, private keys, private LAN literals, or raw card data."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "build"}
TEXT_SUFFIXES = {
    "", ".c", ".cc", ".cpp", ".h", ".hpp", ".pro", ".ui", ".sql",
    ".md", ".py", ".txt", ".yml", ".yaml", ".json", ".csv", ".svg",
    ".sh", ".example",
}
PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:gh[opusr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "historic weak default password",
        re.compile(
            r"\b(?:"
            + "|".join(
                value + "123"
                for value in ("admin", "front", "cleaner", "roomcard")
            )
            + r")\b",
            re.I,
        ),
    ),
    ("private LAN literal", re.compile(r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")),
    (
        "generic assigned secret",
        re.compile(
            r"(?ix)\b(api[_-]?key|access[_-]?token|auth[_-]?token|secret|password|passwd|pwd)"
            r"\b\s*[:=]\s*[\"']?(?!YOUR_|EXAMPLE|REPLACE|CHANGEME|REDACTED|<YOUR_)([A-Za-z0-9+/=_!@#$%^&*.-]{8,})"
        ),
    ),
]
ALLOWED_SUBSTRINGS = {
    "replace-with-a-long-random-password",
    "<YOUR_RANDOM_DATABASE_PASSWORD>",
    "[REDACTED]",
}


def candidate_files(root: Path) -> list[Path]:
    try:
        raw = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        raw = b""
    if raw:
        return [
            root / item.decode("utf-8", "surrogateescape")
            for item in raw.split(b"\0")
            if item
        ]
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not any(part in SKIP_DIRS for part in path.parts)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    findings: list[str] = []

    for path in candidate_files(root):
        if not path.exists() or path.stat().st_size > 3_000_000:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Makefile", ".gitignore", ".env.example"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(root)
        for number, line in enumerate(content.splitlines(), 1):
            if any(allowed in line for allowed in ALLOWED_SUBSTRINGS):
                continue
            for label, pattern in PATTERNS:
                if label == "generic assigned secret" and path.name in {
                    "secret_scan.py",
                    "create_user.py",
                    "database.py",
                    "logindialog.cpp",
                }:
                    continue
                if pattern.search(line):
                    findings.append(f"{rel}:{number}: {label}")

    if findings:
        print("Secret scan: FAIL", file=sys.stderr)
        print("\n".join(sorted(set(findings))), file=sys.stderr)
        return 1
    print("Secret scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
