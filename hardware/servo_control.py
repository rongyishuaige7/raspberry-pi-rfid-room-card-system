"""
SG90舵机控制模块
接线: 棕线-GND, 红线-5V, 橙线-GPIO18
"""
import logging
import RPi.GPIO as GPIO
import time

logger = logging.getLogger(__name__)


class ServoControl:
    def __init__(self, pin=18, freq=50):
        """初始化舵机控制

        Args:
            pin: GPIO引脚编号，默认18
            freq: PWM频率，默认50Hz
        """
        self.pin = pin
        self.freq = freq
        try:
            if GPIO.getmode() is None:
                GPIO.setmode(GPIO.BCM)
        except:
            pass
        GPIO.setup(self.pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.pin, freq)
        self.pwm.start(0)
        self.current_angle = 0

    def _angle_to_duty(self, angle):
        """角度转换为占空比

        0度对应0.5ms脉冲(2.5%占空比)
        180度对应2.5ms脉冲(12.5%占空比)
        """
        return 2.5 + (angle / 180) * 10

    def rotate_to(self, angle, duration=1.0):
        """旋转到指定角度

        Args:
            angle: 目标角度(0-180)
            duration: 保持时间(秒)
        """
        if angle < 0:
            angle = 0
        elif angle > 180:
            angle = 180

        duty = self._angle_to_duty(angle)
        self.pwm.ChangeDutyCycle(duty)

        # SG90 没有位置反馈。这里只等待 PWM 保持时间，不能据此宣称到位。
        time.sleep(duration)
        self.current_angle = angle
        self.pwm.ChangeDutyCycle(0)

    def open_door(self, open_angle=90, hold_time=3):
        """开门动作

        Args:
            open_angle: 开门角度，默认90度
            hold_time: 保持开门时间(秒)
        """
        self.rotate_to(open_angle, 0.5)
        time.sleep(hold_time)
        self.rotate_to(0, 0.5)

    def cleanup(self):
        """清理GPIO资源"""
        self.pwm.stop()
        GPIO.cleanup(self.pin)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    servo = ServoControl()
    logger.info("测试舵机...")
    try:
        logger.info("开门...")
        servo.open_door()
        logger.info("完成")
    except KeyboardInterrupt:
        logger.info("退出")
    finally:
        servo.cleanup()
