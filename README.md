# Raspberry Pi RFID Room-card System

A teaching prototype that connects two RC522 readers, a Raspberry Pi Python service, MariaDB, an SG90 actuator, and a Qt/C++ management client.

[![Validate](https://github.com/rongyishuaige7/raspberry-pi-rfid-room-card-system/actions/workflows/validate.yml/badge.svg)](https://github.com/rongyishuaige7/raspberry-pi-rfid-room-card-system/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-0b7285.svg)](LICENSE)

> **Evidence scope, 2026-07-17:** Source-confirmed · Python tests passed · Qt 5/6 client build-verified · Historical UI demonstrated on 2026-04-03 · Current Raspberry Pi and end-to-end hardware re-test not run.

![Redacted historical dashboard from 2026-04-03](assets/screenshots/historical-dashboard.png)

The image above is a redacted derivative of a real historical interface capture. The private LAN address and RFID UIDs were removed or blurred, and image metadata was stripped. It demonstrates the historical UI only; it is not evidence that the current public commit was re-run on hardware.

## Historical material evidence (2026-07-18 publication)

sanitized historical photo(s). See [MEDIA_EVIDENCE](docs/MEDIA_EVIDENCE.md) for dates, sanitization, omissions, and evidence limits.

![Historical Raspberry Pi/RC522 prototype, 2026-04-08](assets/photos/historical-prototype.jpg)

Historical media/EDA do not prove that the current public commit was flashed or re-tested on hardware. **Current hardware re-test not run.**


## What the prototype covers

- separate SPI0 front-desk and SPI1 CE2 door-side RC522 readers;
- issue, query, lose, cancel, and remove room cards;
- background door-side card polling and SG90 PWM tasks;
- Admin, FrontDesk, and Housekeeping server-side role policies;
- room state, operation logs, statistics, CSV export, and a Qt dashboard;
- environment-based MariaDB configuration and interactive account creation;
- optional GPIO LED, active buzzer, and SSD1306 OLED feedback;
- an RC522 diagnostic script with SPI device and VersionReg checks.

This repository is useful for learning how a small multi-layer hardware system fits together. It is **not** a production hotel lock or a secure access-control product.

## Architecture

```text
Qt 5/6 desktop client
        │ custom newline-delimited TCP, default 8888
        ▼
Raspberry Pi Python service ───── MariaDB
        │
        ├── RC522 #1 / SPI0 CE0: front-desk issue/read
        ├── RC522 #2 / SPI1 CE2: door-side polling
        ├── SG90 / GPIO18: PWM sequence, no position feedback
        ├── LED + active buzzer: optional status feedback
        └── SSD1306 / I2C1: optional local display
```

## Historical interface evidence

| Login | Room map |
|:--:|:--:|
| ![Historical login](assets/screenshots/historical-login.png) | ![Historical room map](assets/screenshots/historical-room-map.png) |

<details>
<summary>Redacted historical audit-log view</summary>

![Historical audit-log view with identifiers blurred](assets/screenshots/historical-audit-log.png)

</details>

These captures are dated 2026-04-03. They are kept separate from the current build claim.

## Repository layout

```text
client/                 Qt/C++ management client
hardware/               Raspberry Pi server and hardware drivers
database/init.sql       MariaDB schema and demo room seed data
hardware/BOM.csv        Source-derived bill of materials
hardware/wiring-diagram.svg
assets/screenshots/     Redacted historical interface captures
tests/                  Hardware-free Python contract tests
docs/                   Protocol, verification, state, and provenance
scripts/                User creation and repository gates
```

## Safe-by-default setup

### 1. Install Raspberry Pi dependencies

```bash
sudo apt update
sudo apt install -y mariadb-server python3-venv python3-dev build-essential
python3 -m venv .venv
. .venv/bin/activate
pip install -r hardware/requirements.txt
# Optional OLED:
pip install -r hardware/requirements-optional.txt
```

`mfrc522` is GPL-3.0; the repository does not vendor it. Review [third-party notices](THIRD_PARTY_NOTICES.md) before redistributing a device image.

### 2. Initialize MariaDB without default credentials

```bash
sudo systemctl enable --now mariadb
sudo mysql < database/init.sql
```

Create a least-privilege database account with your own long random password. Do not paste the real password into Git or a public shell transcript:

```sql
CREATE USER 'roomcard'@'localhost' IDENTIFIED BY '<YOUR_RANDOM_DATABASE_PASSWORD>';
GRANT SELECT, INSERT, UPDATE, DELETE ON room_card_system.* TO 'roomcard'@'localhost';
FLUSH PRIVILEGES;
```

Set the database variables in a protected service environment. `.env.example` documents the names; `.env` is ignored by Git.

```bash
export ROOMCARD_DB_USER=roomcard
export ROOMCARD_DB_PASSWORD='<YOUR_RANDOM_DATABASE_PASSWORD>'
```

Create the first application administrator interactively. The password is read with `getpass`, not as a command-line argument:

```bash
python3 scripts/create_user.py local-admin --role admin
```

The public schema contains demo room numbers but **no application user and no default password**.

### 3. Enable interfaces and verify hardware

Enable SPI0 through `raspi-config`. For the second reader, add this once to `/boot/firmware/config.txt` on current Raspberry Pi OS, then reboot:

```text
dtoverlay=spi1-3cs
```

Confirm `/dev/spidev0.0` and `/dev/spidev1.2`, then run the diagnostic for each reader:

```bash
sudo .venv/bin/python hardware/test_rfid.py --raw
sudo .venv/bin/python hardware/test_rfid.py --door --raw
```

See [HARDWARE.md](HARDWARE.md) and the [wiring boundary diagram](hardware/wiring-diagram.svg). RC522 uses 3.3 V. The servo needs a stable 5 V supply and shared ground.

### 4. Start the server

Loopback is the default. That is appropriate for local testing or a tunnel:

```bash
sudo -E .venv/bin/python hardware/server.py
```

To accept a Qt client from the same **isolated trusted LAN**, explicitly opt in:

```bash
export ROOMCARD_BIND_HOST=0.0.0.0
sudo -E .venv/bin/python hardware/server.py
```

The protocol has no TLS. Do not expose port `8888` to the public Internet.

### 5. Build the Qt client

Qt 6:

```bash
mkdir -p build/client
cd build/client
qmake6 ../../client/card-manager.pro
make -j"$(nproc)"
./card-manager
```

Qt 5 can use `qmake` with the corresponding development packages. Enter the actual Raspberry Pi address when prompted; no historical private IP is hard-coded.

## Protocol and security semantics

The client hashes the password once for historical protocol compatibility, then sends that digest over the custom TCP link. The server stores a salted PBKDF2 derivative, but a network observer could still replay the transmitted digest. See [PROTOCOL.md](docs/PROTOCOL.md) and [SECURITY.md](SECURITY.md).

A remote-open response only confirms dispatch:

```json
{
  "code": 202,
  "msg": "开门任务已下发；未确认舵机完成动作",
  "actuation_confirmed": false
}
```

The SG90 path has no position sensor or lock-state feedback. RC522 UID is cloneable and must not be treated as a high-assurance credential.

## Verification

```bash
bash scripts/verify.sh
```

The gate performs secret/local-data scans, repository checks, Python compilation, 12 unit tests, and clean Qt 5/6 qmake builds. CI repeats the same checks without pretending to own Raspberry Pi hardware.

See:

- [Verification and current result](docs/VERIFICATION.md)
- [Current project state](docs/PROJECT_STATUS.md)
- [Source provenance and exclusions](docs/SOURCE_PROVENANCE.md)
- [BOM](hardware/BOM.csv)

## Known limits

- Current commit has not been re-run on the retained Raspberry Pi/dual-RC522 prototype.
- Historical interface screenshots are not current-commit evidence.
- CI does not access GPIO, SPI, MariaDB, RC522, SG90, OLED, LED, or buzzer hardware.
- No TLS, replay protection, login rate limiting, lockout policy, tamper detection, or hardware-backed credential exists.
- SG90 PWM timing is open-loop and does not prove a door reached a requested state.
- Exact Raspberry Pi revision, power supply, buzzer driver, LED resistor, enclosure, and wiring harness still require physical confirmation.
- No current real-hardware photo or demonstration video is published.

## License

Original repository material is available under the [MIT License](LICENSE). Dependencies retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
