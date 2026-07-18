# Raspberry Pi RFID Room-card System

A teaching prototype that connects two RC522 readers, a Raspberry Pi Python service, MariaDB, an SG90 actuator, and a Qt/C++ management client.

[![Validate](https://github.com/rongyishuaige7/raspberry-pi-rfid-room-card-system/actions/workflows/validate.yml/badge.svg)](https://github.com/rongyishuaige7/raspberry-pi-rfid-room-card-system/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-0b7285.svg)](LICENSE)

> **项目状态（2026-07-17）：** 源码已确认 · Python 测试通过 · Qt 5/6 客户端构建已验证 · 2026-04-03 有UI 截图 · 当前未进行 Raspberry Pi 和端到端真机复测。

![已脱敏的仪表盘，2026-04-03](assets/screenshots/historical-dashboard.png)

上图为项目仪表盘截图；其中的私有局域网地址和 RFID UID 已移除或模糊，图片元数据已清除。

## 项目照片与资料

这里整理了项目照片、界面截图和相关资料；文件处理说明见 [MEDIA_EVIDENCE](docs/MEDIA_EVIDENCE.md)。

![树莓派/RC522 原型，2026-04-08](assets/photos/historical-prototype.jpg)



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

## 历史界面证据

| Login | Room map |
|:--:|:--:|
| ![登录界面](assets/screenshots/historical-login.png) | ![房间地图](assets/screenshots/historical-room-map.png) |

<details>
<summary>已脱敏的历史审计日志视图</summary>

![已模糊标识符的审计日志视图](assets/screenshots/historical-audit-log.png)

</details>

这些截图日期为 2026-04-03，并与当前构建结论严格分开。

## Repository layout

```text
client/                 Qt/C++ management client
hardware/               Raspberry Pi server and hardware drivers
database/init.sql       MariaDB schema and demo room seed data
hardware/BOM.csv        Source-derived bill of materials
hardware/wiring-diagram.svg
assets/screenshots/     已脱敏的历史界面截图
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

Qt 5 可配合相应开发包使用 `qmake`。提示时请输入实际 Raspberry Pi 地址；未硬编码任何历史私网 IP。

## Protocol and security semantics

客户端为兼容历史协议，会将密码哈希一次后通过自定义 TCP 链路发送。服务端存储加盐 PBKDF2 衍生值，但网络观察者仍可能重放传输的摘要。见 [PROTOCOL.md](docs/PROTOCOL.md) 和 [SECURITY.md](SECURITY.md)。

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
- interface screenshots are not current-commit evidence.
- CI does not access GPIO, SPI, MariaDB, RC522, SG90, OLED, LED, or buzzer hardware.
- No TLS, replay protection, login rate limiting, lockout policy, tamper detection, or hardware-backed credential exists.
- SG90 PWM timing is open-loop and does not prove a door reached a requested state.
- Exact Raspberry Pi revision, power supply, buzzer driver, LED resistor, enclosure, and wiring harness still require physical confirmation.
- No current real-hardware photo or demonstration video is published.

## License

Original repository material is available under the [MIT License](LICENSE). Dependencies retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
