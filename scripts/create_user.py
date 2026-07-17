#!/usr/bin/env python3
"""Interactively create a room-card user without putting passwords in shell history."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hardware"))

from database import Database  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or replace one local demo user")
    parser.add_argument("username")
    parser.add_argument(
        "--role",
        required=True,
        choices=("admin", "operator", "viewer"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    if len(password) < 12:
        print("Use at least 12 characters.", file=sys.stderr)
        return 2

    client_sha256 = hashlib.sha256(password.encode("utf-8")).hexdigest()
    database = Database()
    try:
        database.upsert_user(args.username, client_sha256, args.role)
    finally:
        database.close()
    print(f"User {args.username!r} is ready with role {args.role!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
