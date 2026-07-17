# Hardware and wiring boundary

This document is a **source-derived wiring guide**, not a PCB schematic and not proof of the current physical assembly. The public commit has not been re-tested on Rongyi's historical hardware.

## Raspberry Pi BCM wiring

| Function | Module pin | Raspberry Pi BCM / device | Electrical note |
|:--|:--|:--|:--|
| Front reader select | RC522 SDA/SS | GPIO8, SPI0 CE0, `/dev/spidev0.0` | RC522 uses 3.3 V logic |
| Front reader clock | RC522 SCK | GPIO11 | SPI0 SCLK |
| Front reader MOSI | RC522 MOSI | GPIO10 | SPI0 MOSI |
| Front reader MISO | RC522 MISO | GPIO9 | SPI0 MISO |
| Front reader reset | RC522 RST | GPIO25 | Do not leave floating |
| Door reader select | RC522 SDA/SS | GPIO16, SPI1 CE2, `/dev/spidev1.2` | Requires `dtoverlay=spi1-3cs` |
| Door reader clock | RC522 SCK | GPIO21 | SPI1 SCLK |
| Door reader MOSI | RC522 MOSI | GPIO20 | SPI1 MOSI |
| Door reader MISO | RC522 MISO | GPIO19 | SPI1 MISO |
| Door reader reset | RC522 RST | GPIO26 | Do not leave floating |
| Servo PWM | SG90 signal | GPIO18 | Servo power should not come from a weak 3.3 V rail |
| Status LED | LED/driver input | GPIO17 | Series resistor or module input required |
| Active buzzer | module input | GPIO27, active low | Confirm current; use a driver transistor when required |
| Optional OLED SDA | SSD1306 SDA | GPIO2 / I2C1 SDA | Source assumes address `0x3C` |
| Optional OLED SCL | SSD1306 SCL | GPIO3 / I2C1 SCL | Confirm module voltage tolerance |

Both RC522 boards are powered from **3.3 V** and share ground with the Raspberry Pi. Power the servo from a regulated 5 V source with sufficient transient current and connect the grounds. Do not feed 5 V logic into Raspberry Pi GPIO.

## Source-confirmed configuration

- Front RC522: SPI bus 0, device 0, RST GPIO25.
- Door RC522: SPI bus 1, device 2, RST GPIO26.
- Servo: GPIO18 at 50 Hz.
- LED: GPIO17 active high.
- Buzzer: GPIO27 active low.
- OLED: I2C1 at `0x3C`, optional.

## Unconfirmed physical details

The source material does not prove the exact Raspberry Pi revision, RC522 board revision, servo power supply, buzzer driver, LED resistor, wire harness, enclosure, or current draw. Confirm those items from the retained prototype before replacing “current hardware re-test not run” with a hardware-verified status.
