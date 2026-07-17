# Source provenance

## Authoritative-copy decision

| Object | Role | Evidence | Rule |
|:--|:--|:--|:--|
| `/mnt/shared/2026项目/room-card-system.zip` | Read-only historical baseline | SHA-256 `72d751555cf0a4e87a1e897f44539876ede5d8bbf9d21203a1a5f19da88d2cd8` | Never edited or repacked |
| `/home/rongyi/桌面/room-card-system` | Newer source and historical-demo evidence | Dirty local Git `master` at `46e60ff`; current files dated through 2026-04-03 | Read-only source; not cleaned in place |
| `room-card-system/client-fixed.zip` | Historical fixed-client package | Its source matches the current client for the files it contains; its executable and generated files are excluded | Comparison evidence only |
| `/home/rongyi/桌面/raspberry-pi-rfid-room-card-system` | Clean publication candidate | Built from an explicit allowlist, with fresh public Git history | All public edits occur here |

The desktop worktree is the newer candidate because it contains post-archive client fixes, expanded server/database code, and dated historical screenshots. This establishes version order only; it does **not** prove that the public commit has been run on the retained device.

## Merge and exclusion record

Included from the current desktop worktree:

- Qt/C++ client sources and `.pro`/`.ui` files;
- Python server, database, RC522, servo, optional OLED/alert, and diagnostic sources;
- MariaDB schema as a starting point;
- four derivative screenshots made from real 2026-04-03 interface captures.

Excluded before the first public commit:

- original `.git/` history and all staged/unstaged ambiguity;
- `client-fixed.zip` and the archived executable;
- qmake `Makefile`, `.qmake.stash`, object files, generated `ui_*.h`, and `card-manager` binary;
- CSV operation-log export;
- raw screenshots containing private IPs and complete RFID UIDs;
- historical default passwords and replayable unsalted password records;
- any local database, secret, token, or environment file.

## Public hardening changes

The public candidate keeps the original teaching architecture while narrowing unsafe claims and defaults:

- no default application user or password;
- interactive account creation with salted PBKDF2 database storage;
- loopback bind by default and environment-based configuration;
- role checks derive the audit operator from the authenticated session;
- only administrators can issue the explicit lost-card emergency exception;
- bounded line size, log limit, session count, and session lifetime;
- remote-open response reports task dispatch, not confirmed physical actuation;
- SG90 timing is no longer described as position feedback;
- historical fixed LAN addresses, fake company footer, and “Cloud Sync OK” text are removed.

These changes are source- and test-verified. Current Raspberry Pi, RFID, database, and actuator re-testing has not been run.
