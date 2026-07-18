# Project status

> Status date: 2026-07-17

| Layer | Current evidence | Not established |
|:--|:--|:--|
| Source | Source-confirmed; origin and exclusions are documented | No claim that the original dirty Git state was production-ready |
| Python server | Static compile and unit tests pass | Not run against the historical Raspberry Pi GPIO/SPI stack in this publication pass |
| Qt client | Qt 5 and Qt 6 clean qmake builds pass on Linux | No current Windows/macOS build or GUI smoke |
| MariaDB | Schema is linted and database access has unit-tested password helpers | No current MariaDB integration run in CI |
| Historical UI | Four redacted screenshots derive from real 2026-04-03 captures | Screenshots do not bind to the public commit |
| Hardware | Wiring can be traced to current source | Current dual-RC522, SG90, buzzer, LED, and OLED re-test not run |
| Security | Safer defaults and disclosed boundaries | No TLS, rate limiting, lockout, hardware-backed credential, or independent security assessment |

Canonical summary:

```text
Source-confirmed
Python tests passed
Qt 5/6 client build-verified
Historical UI demonstrated on 2026-04-03
Current Raspberry Pi and end-to-end hardware re-test not run
```

Unsupported labels include production hotel access control, secure entry, tamper-proof,
industrial-grade operation, and present-day hardware verification.

## Historical media and EDA added on 2026-07-18

sanitized historical photo(s). See [MEDIA_EVIDENCE](MEDIA_EVIDENCE.md) for dates, sanitization, omissions, and evidence limits.

This publication update adds historical evidence only. Current hardware re-test not run.
