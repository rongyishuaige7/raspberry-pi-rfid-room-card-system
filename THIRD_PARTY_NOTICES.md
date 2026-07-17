# Third-party notices

This repository contains Rongyi's project source code. It does not vendor Qt, MariaDB, Raspberry Pi OS, Python packages, fonts, or their source trees.

| Component | How it is used | License / source |
|:--|:--|:--|
| Qt 5/6 | Builds the desktop client | Qt licensing depends on the selected edition and modules. The open-source distributions are available under LGPL/GPL terms: <https://www.qt.io/licensing/open-source-lgpl-obligations> |
| MariaDB | Local relational database | GPL-2.0; <https://mariadb.com/kb/en/mariadb-license/> |
| PyMySQL | Python MariaDB/MySQL client | MIT; <https://github.com/PyMySQL/PyMySQL> |
| RPi.GPIO | Raspberry Pi GPIO access | MIT; <https://sourceforge.net/projects/raspberry-gpio-python/> |
| spidev | Python SPI bindings | MIT; <https://github.com/doceme/py-spidev> |
| mfrc522 | MFRC522/RC522 Python driver | GPL-3.0; <https://github.com/pimylifeup/MFRC522-python> |
| luma.oled | Optional SSD1306 output | MIT; <https://github.com/rm-hull/luma.oled> |
| Pillow | Optional luma.oled dependency | HPND; <https://python-pillow.github.io/> |

The dependency lists download these components from their respective distributors. Review their current license texts before redistributing binaries or a complete device image. MIT covers only the original material in this repository and does not replace third-party terms.
