import logging
import RPi.GPIO as GPIO
import time

logger = logging.getLogger(__name__)
try:
    from luma.core.interface.serial import i2c
    from luma.core.render import canvas
    from luma.oled.device import ssd1306
    HAS_OLED = True
except ImportError:
    HAS_OLED = False

class HardwareAlerts:
    """蜂鸣器为低电平触发：LOW=响，HIGH=静音。LED 为高电平亮。"""
    def __init__(self, led_pin=17, buzzer_pin=27):
        self.led_pin = led_pin
        self.buzzer_pin = buzzer_pin
        GPIO.setmode(GPIO.BCM)
        # 蜂鸣器低电平触发，初始 HIGH 保持静音
        GPIO.setup(self.buzzer_pin, GPIO.OUT, initial=GPIO.HIGH)
        GPIO.setup(self.led_pin, GPIO.OUT, initial=GPIO.LOW)

    def success(self):
        """成功反馈：响一声，灯(LED)亮"""
        GPIO.output(self.led_pin, GPIO.HIGH)
        GPIO.output(self.buzzer_pin, GPIO.LOW)  # LOW 响
        time.sleep(0.2)
        GPIO.output(self.led_pin, GPIO.LOW)
        GPIO.output(self.buzzer_pin, GPIO.HIGH)  # HIGH 静音

    def failure(self):
        """失败反馈：响三声，灯闪烁"""
        for _ in range(3):
            GPIO.output(self.led_pin, GPIO.HIGH)
            GPIO.output(self.buzzer_pin, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(self.led_pin, GPIO.LOW)
            GPIO.output(self.buzzer_pin, GPIO.HIGH)
            time.sleep(0.1)

    def cleanup(self):
        GPIO.output(self.led_pin, GPIO.LOW)
        GPIO.output(self.buzzer_pin, GPIO.HIGH)  # 静音


class OLEDDisplay:
    def __init__(self):
        self.device = None
        if not HAS_OLED:
            logger.info("OLED 库未安装 (luma.oled)，跳过显示初始化")
            return
        try:
            serial = i2c(port=1, address=0x3C)
            self.device = ssd1306(serial)
            self.show_status("System Ready", "Waiting for card...")
        except Exception as e:
            logger.warning("OLED初始化失败: %s", e)

    def show_status(self, line1, line2=""):
        if not self.device:
            return
        with canvas(self.device) as draw:
            # 简单的边框
            draw.rectangle(self.device.bounding_box, outline="white", fill="black")
            draw.text((10, 10), line1, fill="white")
            draw.text((10, 30), line2, fill="white")

    def show_card(self, uid, room="Unknown"):
        self.show_status(f"UID: {uid}", f"Room: {room}")

    def show_error(self, msg):
        self.show_status("ACCESS DENIED", msg)
