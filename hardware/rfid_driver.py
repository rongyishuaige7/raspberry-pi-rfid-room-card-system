"""
RFID RC522 驱动模块 (基于 mfrc522 库的 MFRC522)
支持多路 SPI：前台读卡器 (SPI0) 与房门读卡器 (SPI1)。

树莓派接线 — 前台 RC522 #1 (SPI0, 默认):
- SDA  -> GPIO8 (CE0)  /dev/spidev0.0
- SCK  -> GPIO11 (SCK)
- MOSI -> GPIO10 (MOSI)
- MISO -> GPIO9 (MISO)
- GND  -> GND
- RST  -> GPIO25 (或接 3.3V，勿悬空)
- 3.3V -> 3.3V

房门 RC522 #2 (SPI1，需 dtoverlay=spi1-3cs，使用 CE2 避免与 GPIO18 舵机冲突):
- SDA  -> GPIO16 (SPI1 CE2)  /dev/spidev1.2
- SCK  -> GPIO21
- MOSI -> GPIO20
- MISO -> GPIO19
- RST  -> GPIO26 (或 3.3V)
- 3.3V / GND 同前
"""
import logging
import RPi.GPIO as GPIO
from mfrc522 import MFRC522
import time

logger = logging.getLogger(__name__)

# 默认实例参数（与历史接线一致）
DEFAULT_FRONT_BUS = 0
DEFAULT_FRONT_DEVICE = 0
DEFAULT_FRONT_PIN_RST = 25

# 房门读卡器：SPI1 CE2（spi1-3cs 启用后通常为 /dev/spidev1.2）
DEFAULT_DOOR_BUS = 1
DEFAULT_DOOR_DEVICE = 2
DEFAULT_DOOR_PIN_RST = 26


class RC522:
    """封装 MFRC522，提供与原先 SimpleMFRC522 类似的 UID 读取（非阻塞轮询 + 多重采样）。"""

    def __init__(self, bus=DEFAULT_FRONT_BUS, device=DEFAULT_FRONT_DEVICE,
                 pin_rst=DEFAULT_FRONT_PIN_RST, speed_hz=1_000_000):
        """
        Args:
            bus: SPI 总线号 (0=SPI0, 1=SPI1)
            device: 片选序号，如 SPI0 CE0 -> 0；SPI1 CE2 -> 2（见 /dev/spidev*）
            pin_rst: RC522 RST 所接 BCM 引脚
            speed_hz: SPI 时钟
        """
        self.bus = bus
        self.device = device
        self.pin_rst = pin_rst
        try:
            if GPIO.getmode() is None:
                GPIO.setmode(GPIO.BCM)
        except Exception:
            pass
        self.reader = MFRC522(
            bus=bus,
            device=device,
            spd=speed_hz,
            pin_mode=GPIO.BCM,
            pin_rst=pin_rst,
        )

    @staticmethod
    def uid_to_num(uid):
        """与 SimpleMFRC522.uid_to_num 一致"""
        n = 0
        for i in range(0, 5):
            n = n * 256 + uid[i]
        return n

    def read_id_no_block(self):
        """读取卡 UID（十进制整数），无卡返回 None。逻辑同 SimpleMFRC522.read_id_no_block。"""
        r = self.reader
        (status, TagType) = r.MFRC522_Request(r.PICC_REQIDL)
        if status != r.MI_OK:
            return None
        (status, uid) = r.MFRC522_Anticoll()
        if status != r.MI_OK:
            return None
        return self.uid_to_num(uid)

    def read_no_block(self):
        """兼容 SimpleMFRC522.read_no_block()：仅读 UID，不读扇区数据。返回 (uid_int|None, text_or_None)。"""
        card_id = self.read_id_no_block()
        if card_id is None:
            return None, None
        return card_id, None

    def read_card_uid(self, timeout=4.0):
        """读取卡 UID (带超时)
        参数:
            timeout: 超时时间(秒)
        返回: 卡号字符串，超时或读取失败返回None
        """
        try:
            start_time = time.time()
            samples = []
            while time.time() - start_time < timeout:
                card_id = self.read_id_no_block()
                if card_id is not None:
                    samples.append(str(card_id))
                    if len(samples) >= 3:
                        from collections import Counter
                        counts = Counter(samples)
                        most_common = counts.most_common(1)[0]
                        if most_common[1] >= 2:
                            return most_common[0]
                time.sleep(0.1)
            return None
        except Exception as e:
            logger.warning("读卡错误: %s", e)
            return None

    def cleanup(self):
        """仅关闭本读卡器的 SPI，避免 MFRC522.Close_MFRC522 中的 GPIO.cleanup 影响舵机/LED 等。"""
        try:
            if self.reader and getattr(self.reader, "spi", None):
                self.reader.spi.close()
        except Exception as e:
            logger.debug("RFID SPI 关闭: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rfid = RC522()
    logger.info("请刷卡...")
    try:
        while True:
            uid = rfid.read_card_uid()
            if uid:
                logger.info("检测到卡: %s", uid)
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("退出")
    finally:
        rfid.cleanup()
