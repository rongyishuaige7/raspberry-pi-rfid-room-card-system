#!/usr/bin/env python3
"""Repository release checks that require no Raspberry Pi hardware."""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

REQUIRED = [
    ".env.example", ".github/workflows/validate.yml", ".gitignore",
    ".markdownlint-cli2.jsonc", "HARDWARE.md",
    "LICENSE", "Makefile", "README.md", "SECURITY.md", "THIRD_PARTY_NOTICES.md",
    "assets/screenshots/historical-audit-log.png",
    "assets/screenshots/historical-dashboard.png",
    "assets/screenshots/historical-login.png",
    "assets/screenshots/historical-room-map.png",
    "client/card-manager.pro", "database/init.sql", "docs/GITHUB_METADATA.md",
    "docs/HARDWARE_LAB_CARD.md", "docs/PROJECT_STATUS.md", "docs/PROTOCOL.md",
    "docs/SOURCE_PROVENANCE.md", "docs/VERIFICATION.md", "hardware/BOM.csv",
    "hardware/requirements.txt", "hardware/server.py", "hardware/wiring-diagram.svg",
    "scripts/create_user.py", "scripts/secret_scan.py", "scripts/verify.sh",
    "tests/test_passwords.py", "tests/test_server_contract.py",
]
FORBIDDEN_NAMES = {
    ".env", "client-fixed.zip", "card-manager", "Makefile.Debug", "Makefile.Release",
    ".qmake.stash", "2026-04-03_logs.csv", "id_rsa", "id_ed25519",
}
FORBIDDEN_DIRS = {"__pycache__", ".venv", "venv", "build", "node_modules"}
FORBIDDEN_SUFFIXES = {".o", ".so", ".a", ".pyc", ".pyo", ".zip", ".7z", ".db", ".sqlite"}
MAX_FILE_BYTES = 5 * 1024 * 1024


def files_for_check(root: Path) -> list[Path]:
    try:
        raw = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"], check=True, capture_output=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        raw = b""
    if raw:
        return [root / item.decode("utf-8", "surrogateescape") for item in raw.split(b"\0") if item]
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and not any(part in {".git", "__pycache__", "build"} for part in path.parts)
    )


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="strict")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors: list[str] = []

    for rel in REQUIRED:
        if not (root / rel).is_file():
            errors.append(f"missing required file: {rel}")

    files = files_for_check(root)
    for path in files:
        rel = path.relative_to(root)
        if path.name in FORBIDDEN_NAMES:
            errors.append(f"forbidden local/generated file: {rel}")
        if any(part in FORBIDDEN_DIRS for part in rel.parts):
            errors.append(f"forbidden generated directory: {rel}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden generated artifact: {rel}")
        if path.stat().st_size > MAX_FILE_BYTES:
            errors.append(f"file exceeds 5 MiB: {rel}")

    contracts = {
        "README.md": [
            "Current Raspberry Pi and end-to-end hardware re-test not run",
            "actuation_confirmed\": false",
            "no application user and no default password",
            "assets/screenshots/historical-dashboard.png",
        ],
        "SECURITY.md": [
            "custom TCP protocol has no TLS",
            "RC522 UID is not a secure credential",
            "successful response means the PWM task was queued",
        ],
        "docs/PROJECT_STATUS.md": [
            "Historical UI demonstrated on 2026-04-03",
            "Current Raspberry Pi and end-to-end hardware re-test not run",
        ],
        "docs/SOURCE_PROVENANCE.md": [
            "72d751555cf0a4e87a1e897f44539876ede5d8bbf9d21203a1a5f19da88d2cd8",
            "client-fixed.zip",
            "Dirty local Git `master` at `46e60ff`",
        ],
        "docs/PROTOCOL.md": [
            "| `GET_LOGS` | optional limit, clamped to 1–500 | Admin only |",
        ],
        "hardware/server.py": [
            "ROOMCARD_BIND_HOST', '127.0.0.1'",
            "'actuation_confirmed': False",
            "session.get('username') or 'unknown'",
            "_CMD_READ_ONLY = frozenset({'GET_STATS', 'GET_CARDS', 'GET_ROOMS', 'CHECK_CARD'})",
        ],
        "database/init.sql": [
            "不创建默认账号或默认密码",
            "fk_card_room",
        ],
    }
    for rel, required_text in contracts.items():
        path = root / rel
        if not path.is_file():
            continue
        content = read(path)
        for value in required_text:
            if value not in content:
                errors.append(f"fact contract missing in {rel}: {value}")

    forbidden_claims = [
        "system online", "production ready", "industrial grade", "current hardware verified",
        "hardware re-verified: pass", "cloud sync ok", "系统已上线", "远程开门成功",
    ]
    for rel in ["README.md", "docs/PROJECT_STATUS.md", "docs/HARDWARE_LAB_CARD.md", "client/mainwindow.cpp"]:
        path = root / rel
        if not path.is_file():
            continue
        content = read(path).lower()
        for claim in forbidden_claims:
            # A clearly negated disclosure is required, not an unsupported positive claim.
            content_without_negated_boundaries = content.replace(
                f"do not describe this repository as {claim}", ""
            )
            if claim in content_without_negated_boundaries:
                errors.append(f"unsupported claim in {rel}: {claim}")

    try:
        ET.parse(root / "hardware/wiring-diagram.svg")
    except (ET.ParseError, OSError) as exc:
        errors.append(f"invalid wiring SVG: {exc}")

    try:
        with (root / "hardware/BOM.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) < 8:
            errors.append("BOM must contain at least 8 component rows")
    except (OSError, csv.Error) as exc:
        errors.append(f"invalid BOM.csv: {exc}")

    for path in sorted((root / "assets/screenshots").glob("*.png")):
        try:
            with Image.open(path) as image:
                if image.format != "PNG":
                    errors.append(f"screenshot is not PNG: {path.relative_to(root)}")
                if set(image.info) - {"transparency"}:
                    errors.append(f"screenshot contains metadata: {path.relative_to(root)} {sorted(image.info)}")
                if image.width < 400 or image.height < 400:
                    errors.append(f"screenshot unexpectedly small: {path.relative_to(root)}")
        except OSError as exc:
            errors.append(f"cannot open screenshot {path.relative_to(root)}: {exc}")

    if errors:
        print("Repository check: FAIL", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Repository check: PASS ({len(files)} files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
