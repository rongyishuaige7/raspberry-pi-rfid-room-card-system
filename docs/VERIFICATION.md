# Verification

## One-command local gate

```bash
bash scripts/verify.sh
```

The gate runs from an isolated temporary copy and checks:

1. secret and local-data patterns;
2. repository structure, forbidden outputs, file sizes, links, screenshot metadata, and documentation contracts;
3. Python bytecode compilation;
4. Python unit tests for PBKDF2 storage, UID validation, authentication, role policy, and actuator-response semantics;
5. clean Qt 5 and Qt 6 qmake client builds.

## Current verified result

On 2026-07-17 the candidate passed:

```text
Secret scan: PASS
Repository check: PASS
Python py_compile: PASS
Python unittest: 12 passed
Qt 5 qmake clean build: PASS
Qt 6 qmake clean build: PASS
```

The Qt builds are source/build tests on Linux. They do not open the GUI or connect to a Raspberry Pi.

## Hardware re-test checklist

To upgrade the state to `Hardware re-verified`, bind the record to a commit and date, then verify:

1. exact Raspberry Pi model and Raspberry Pi OS version;
2. SPI0 front RC522 VersionReg and repeated UID reads;
3. SPI1 CE2 door RC522 VersionReg and repeated UID reads;
4. MariaDB initialization with no default users, followed by interactive administrator creation;
5. Qt login and RBAC for Admin, FrontDesk, and Housekeeping;
6. issue, query, lose, cancel, and delete flows with expected room-state synchronization;
7. normal card accepted, expired/lost/cancelled card rejected at the door reader;
8. lost-card emergency path available only to Admin;
9. SG90 PWM task, actual linkage movement, power stability, and the lack or addition of position feedback;
10. optional LED, active buzzer, and OLED behavior;
11. service restart invalidates sessions;
12. the service remains on an isolated trusted LAN or authenticated encrypted tunnel.

Record observed failures and untested items. Do not convert a source build or historical screenshot into a current hardware claim.
