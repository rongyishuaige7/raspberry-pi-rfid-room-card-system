#!/usr/bin/env python3
"""
RC522 RFID 模块诊断测试脚本
用法：sudo python3 test_rfid.py [--raw] [--loop] [--timeout 秒数] [--door]

--raw    : 跳过多次采样过滤，直接输出每一次原始读取结果（最适合排查读不到卡的问题）
--loop   : 持续循环读取，不停止（Ctrl+C 退出）
--timeout: 单次读卡超时秒数（默认 5）
--door   : 测试房门读卡器（SPI1 CE2 /dev/spidev1.2，需 dtoverlay=spi1-3cs）
"""

import os
import sys
import time
import argparse
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("rfid_test")


# ──────────────────────────────────────────────
# 步骤 1：检查 SPI 是否已启用
# ──────────────────────────────────────────────
def check_spi(require_door_dev=False):
    logger.info("=== 步骤1：检查 SPI 接口 ===")
    import os
    spi_devices = [d for d in os.listdir("/dev") if d.startswith("spidev")]
    if spi_devices:
        logger.info("✓ 检测到 SPI 设备：%s", ", ".join(sorted(spi_devices)))
    else:
        logger.error(
            "✗ 未找到 /dev/spidev* 设备！\n"
            "  请执行：sudo raspi-config → Interface Options → SPI → Enable\n"
            "  然后重启树莓派再运行本脚本。"
        )
        return False

    if require_door_dev:
        door_path = "/dev/spidev1.2"
        if not os.path.exists(door_path):
            logger.error(
                "✗ 房门读卡器需要 %s。\n"
                "  请在 /boot/config.txt 末尾添加：dtoverlay=spi1-3cs\n"
                "  保存后重启树莓派，再确认本设备节点是否存在。",
                door_path,
            )
            return False
        logger.info("✓ 房门读卡器 SPI 节点存在：%s", door_path)

    # 检查内核模块
    try:
        with open("/proc/modules") as f:
            modules = f.read()
        if "spi_bcm2835" in modules or "spi_bcm2708" in modules:
            logger.info("✓ SPI 内核模块已加载")
        else:
            logger.warning("⚠ 未检测到 spi_bcm2835 模块，SPI 可能未正确启用")
    except Exception:
        pass

    return True


# ──────────────────────────────────────────────
# 步骤 2：检查依赖库
# ──────────────────────────────────────────────
def check_libraries():
    logger.info("=== 步骤2：检查依赖库 ===")
    ok = True
    for lib in ("RPi.GPIO", "mfrc522", "spidev"):
        try:
            __import__(lib)
            logger.info("✓ %-12s 已安装", lib)
        except ImportError as e:
            logger.error("✗ %-12s 未安装：%s", lib, e)
            ok = False
    return ok


# ──────────────────────────────────────────────
# 步骤 3：初始化 RC522
# ──────────────────────────────────────────────
def init_reader(door=False):
    """使用项目 RC522 封装（支持 SPI0 前台 / SPI1 房门）。"""
    label = "房门 SPI1 CE2" if door else "前台 SPI0 CE0"
    logger.info("=== 步骤3：初始化 RC522（%s） ===", label)
    try:
        hw_dir = os.path.dirname(os.path.abspath(__file__))
        if hw_dir not in sys.path:
            sys.path.insert(0, hw_dir)
        from rfid_driver import RC522, DEFAULT_DOOR_BUS, DEFAULT_DOOR_DEVICE, DEFAULT_DOOR_PIN_RST
        if door:
            reader = RC522(
                bus=DEFAULT_DOOR_BUS,
                device=DEFAULT_DOOR_DEVICE,
                pin_rst=DEFAULT_DOOR_PIN_RST,
            )
        else:
            reader = RC522()
        logger.info("✓ RC522 (%s) 初始化成功", label)
        return reader
    except Exception as e:
        logger.error("✗ 初始化失败：%s", e)
        if door:
            logger.error(
                "  常见原因：\n"
                "  1. 未添加 dtoverlay=spi1-3cs 或未重启\n"
                "  2. 房门 RC522 接线：SDA→GPIO16, SCK→21, MOSI→20, MISO→19, RST→26\n"
                "  3. 未使用 sudo 运行"
            )
        else:
            logger.error(
                "  常见原因：\n"
                "  1. SPI 未启用（见步骤1）\n"
                "  2. RC522 接线有误（SDA→GPIO8, SCK→11, MOSI→10, MISO→9, 3.3V, GND）\n"
                "  3. 未使用 sudo 运行（sudo python3 test_rfid.py）"
            )
        return None


# ──────────────────────────────────────────────
# 步骤 4a：原始模式——每 100ms 读一次，不过滤
# ──────────────────────────────────────────────
def read_raw(reader, timeout=5.0):
    logger.info("=== 步骤4（原始模式）：%g 秒内持续读取，请将卡靠近读卡器 ===", timeout)
    start = time.time()
    attempts = 0
    hits = 0
    while time.time() - start < timeout:
        attempts += 1
        try:
            uid, text = reader.read_no_block()
            if uid:
                hits += 1
                logger.info("★ 原始读卡成功 [第%d次尝试]  UID = %s  数据 = %r",
                            attempts, uid, (text or "").strip())
            else:
                # 每 10 次打印一次"空读"提示，避免刷屏
                if attempts % 10 == 0:
                    logger.debug("  第%d次尝试：未读到卡", attempts)
        except Exception as e:
            logger.warning("  读取异常：%s", e)
        time.sleep(0.1)

    elapsed = time.time() - start
    logger.info("--- 原始模式结束：共尝试 %d 次，成功读卡 %d 次，耗时 %.1fs ---",
                attempts, hits, elapsed)
    return hits > 0


# ──────────────────────────────────────────────
# 步骤 4b：驱动层模式——使用项目自带的 RC522 类（含多次采样过滤）
# ──────────────────────────────────────────────
def read_via_driver(timeout=5.0, door=False):
    mode = "房门" if door else "前台"
    logger.info("=== 步骤4（驱动层模式）：%s RC522 读卡（%g 秒超时） ===", mode, timeout)
    try:
        hw_dir = os.path.dirname(os.path.abspath(__file__))
        if hw_dir not in sys.path:
            sys.path.insert(0, hw_dir)
        from rfid_driver import RC522, DEFAULT_DOOR_BUS, DEFAULT_DOOR_DEVICE, DEFAULT_DOOR_PIN_RST
        if door:
            rfid = RC522(
                bus=DEFAULT_DOOR_BUS,
                device=DEFAULT_DOOR_DEVICE,
                pin_rst=DEFAULT_DOOR_PIN_RST,
            )
        else:
            rfid = RC522()
        uid = rfid.read_card_uid(timeout=timeout)
        try:
            rfid.cleanup()
        except Exception:
            pass
        if uid:
            logger.info("★ 驱动层读卡成功，UID = %s", uid)
            return True
        else:
            logger.warning("✗ 驱动层：%g 秒内未读到卡", timeout)
            return False
    except Exception as e:
        logger.error("✗ 驱动层异常：%s", e)
        return False


# ──────────────────────────────────────────────
# 步骤 5：SPI 底层通信测试（读 RC522 版本寄存器）
# ──────────────────────────────────────────────
def _rc522_read_reg(spi, addr):
    """RC522 SPI 读寄存器：第一字节 = (addr<<1)|0x80，第二字节哑读"""
    tx = ((addr << 1) & 0x7E) | 0x80
    return spi.xfer2([tx, 0x00])[1]


def _rst_pulse(rst_pin):
    """对 RC522 RST 执行硬件复位（低→高）。"""
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(rst_pin, GPIO.OUT)
        GPIO.output(rst_pin, GPIO.LOW)
        time.sleep(0.05)
        GPIO.output(rst_pin, GPIO.HIGH)
        time.sleep(0.05)
        logger.info("  RST(GPIO%d) 复位脉冲已发送", rst_pin)
    except Exception as e:
        logger.warning("  RST 脉冲失败（非致命）：%s", e)


def check_spi_comm(bus=0, device=0, rst_pin=25, door=False):
    """
    直接用 spidev 读取 RC522 的 VersionReg（地址 0x37）。
    正常芯片返回 0x91/0x92（原版）或 0x82/0x90（常见克隆），均视为通信正常。
    如果返回 0x00 或 0xFF，说明 SPI 通信失败（接线问题或 RST 悬空）。

    诊断策略：
    1. 先不操作 RST，直接读一次
    2. 若失败，发一次 RST 复位脉冲后再读
    3. 若仍失败，用三种 SPI 速率（1M / 500k / 100k）逐一尝试
    4. 扫描若干常用寄存器，帮助判断是全 0x00 还是有部分响应

    Args:
        bus, device: 与 open(bus, device) 一致，如前台 (0,0)、房门 (1,2)
        rst_pin: RC522 RST 所接 BCM 引脚
        door: 房门模式（仅影响日志中的接线提示）
    """
    dev_path = f"/dev/spidev{bus}.{device}"
    mode = "房门 SPI1" if door else "前台 SPI0"
    logger.info("=== 步骤5：SPI 底层通信检测 [%s %s]（读 VersionReg 0x37） ===", mode, dev_path)

    import spidev

    VERSION_REG = 0x37

    def try_read(speed_hz, do_rst=False):
        """返回 (version_byte, ok)"""
        try:
            if do_rst:
                _rst_pulse(rst_pin)

            spi = spidev.SpiDev()
            spi.open(bus, device)
            spi.max_speed_hz = speed_hz
            spi.mode = 0
            version = _rc522_read_reg(spi, VERSION_REG)
            spi.close()
            return version, True
        except FileNotFoundError:
            logger.error("✗ %s 不存在（请先启用对应 SPI 并重启）", dev_path)
            return None, False
        except PermissionError:
            logger.error("✗ 权限不足，请使用 sudo 运行")
            return None, False
        except Exception as e:
            logger.error("✗ SPI 异常：%s", e)
            return None, False

    # 0x91/0x92 为原版 RC522；0x82/0x90 等为常见克隆/变体，均视为芯片正常
    VALID_VERSION = (0x82, 0x90, 0x91, 0x92)

    def describe_version(v, label=""):
        if v in VALID_VERSION:
            logger.info("  ✓ %s VersionReg = 0x%02X ← 芯片正常响应（SPI 通信 OK）", label, v)
            return True
        elif v == 0x00:
            logger.warning("  ✗ %s VersionReg = 0x00 ← MISO 全低/无响应（检查 RST 是否接 3.3V）", label)
        elif v == 0xFF:
            logger.warning("  ✗ %s VersionReg = 0xFF ← MISO 全高/上电异常", label)
        else:
            logger.warning("  ⚠ %s VersionReg = 0x%02X ← 非标准值（若能刷卡可忽略）", label, v)
        return False

    # ── 第一轮：不动 RST，1MHz ──
    logger.info("  [1/3] 尝试 1MHz，不操作 RST ...")
    v, ok = try_read(1_000_000, do_rst=False)
    if not ok:
        return False
    if describe_version(v, "1MHz无RST"):
        return True

    # ── 第二轮：先拉低再拉高 RST，1MHz ──
    logger.info("  [2/3] 检测到 0x%02X，尝试先对 RST(GPIO%d) 执行复位脉冲 ...", v, rst_pin)
    v, ok = try_read(1_000_000, do_rst=True)
    if not ok:
        return False
    if describe_version(v, "1MHz+RST"):
        return True

    # ── 第三轮：降低 SPI 速率逐一尝试 ──
    logger.info("  [3/3] 尝试降低 SPI 速率 ...")
    for speed in (500_000, 200_000, 100_000):
        v, ok = try_read(speed, do_rst=True)
        if not ok:
            return False
        label = f"{speed//1000}kHz+RST"
        if describe_version(v, label):
            return True

    # ── 附加诊断：扫描多个寄存器，判断是"全0"还是偶有响应 ──
    logger.info("  --- 附加诊断：扫描 RC522 寄存器 0x00~0x3F ---")
    try:
        _rst_pulse(rst_pin)
        spi = spidev.SpiDev()
        spi.open(bus, device)
        spi.max_speed_hz = 100_000
        spi.mode = 0
        results = {}
        for reg in range(0x00, 0x40):
            results[reg] = _rc522_read_reg(spi, reg)
        spi.close()

        vals = list(results.values())
        unique = set(vals)
        logger.info("  寄存器扫描结果：unique values = %s", sorted(unique))
        if unique == {0x00}:
            if door:
                logger.error(
                    "  ✗ 所有寄存器均返回 0x00。\n"
                    "  房门读卡器请检查：MISO→GPIO19、MOSI→20、SCK→21、SDA/CS→GPIO16、RST→GPIO%d",
                    rst_pin,
                )
            else:
                logger.error(
                    "  ✗ 所有寄存器均返回 0x00。\n"
                    "  最可能原因（按概率排序）：\n"
                    "  ① MISO 线（GPIO9 → RC522 MISO）未接或接触不良\n"
                    "  ② MOSI 与 MISO 接反（GPIO10↔GPIO9 互换试试）\n"
                    "  ③ RC522 模块 3.3V 供电不足或 GND 未共地\n"
                    "  ④ RST 引脚悬空或一直被拉低（接 3.3V 直接试试）"
                )
        elif unique == {0xFF}:
            if door:
                logger.error(
                    "  ✗ 所有寄存器均返回 0xFF。\n"
                    "  请检查 SDA→GPIO16(CE2) 与 GND/3.3V。"
                )
            else:
                logger.error(
                    "  ✗ 所有寄存器均返回 0xFF。\n"
                    "  最可能原因：\n"
                    "  ① SDA/CS(GPIO8) 未接或悬空，片选无效\n"
                    "  ② MISO 被上拉到高电平（检查 RC522 板上电阻）"
                )
        else:
            logger.warning(
                "  ⚠ 寄存器值不全相同，有部分响应（unique=%s），\n"
                "  可能是克隆芯片版本号不同，或 SPI 时序偏差。\n"
                "  请尝试 --raw 模式实际刷卡，或检查是否需要更低速率。",
                sorted(unique)
            )
            # 打印部分有价值的寄存器
            key_regs = {0x37: "VersionReg", 0x01: "CommandReg", 0x04: "ComIrqReg",
                        0x06: "ErrorReg",   0x0A: "FIFODataReg", 0x0B: "FIFOLevelReg"}
            for addr, name in key_regs.items():
                logger.info("    0x%02X %-14s = 0x%02X", addr, name, results[addr])
    except Exception as e:
        logger.error("  寄存器扫描失败：%s", e)

    if door:
        logger.error(
            "\n  ════ 总结：房门 RC522 SPI 通信异常 ════\n"
            "  Step A: 确认已配置 dtoverlay=spi1-3cs 且存在 /dev/spidev1.2\n"
            "  Step B: RC522 SDA→GPIO16(CE2)，RST→GPIO%d，供电 3.3V 共地\n"
            "  Step C: 检查 SPI1 四线 MISO/SCK/MOSI 与模块对应引脚",
            rst_pin,
        )
    else:
        logger.error(
            "\n  ════ 总结：SPI 通信异常，无法读取 VersionReg ════\n"
            "  请按以下顺序逐步排查：\n"
            "  Step A: 确认 RC522 有 3.3V（用万用表量 VCC 与 GND 之间）\n"
            "  Step B: 确认 RST 引脚已接 GPIO25 或直接接 3.3V（不可悬空）\n"
            "  Step C: 对调 MISO(GPIO9) 与 MOSI(GPIO10) 再试（常见接反问题）\n"
            "  Step D: 换一根杜邦线替换 MISO 线（最常见虚接位置）\n"
            "  Step E: 用万用表测 GPIO8(SDA) 到 RC522 SDA 是否通路"
        )
    return False


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="RC522 RFID 诊断测试")
    parser.add_argument("--raw", action="store_true",
                        help="使用原始模式（不过滤，每次读取都输出）")
    parser.add_argument("--loop", action="store_true",
                        help="持续循环读取（Ctrl+C 停止）")
    parser.add_argument("--timeout", type=float, default=5.0,
                        help="单次读卡超时秒数（默认5）")
    parser.add_argument("--door", action="store_true",
                        help="测试房门读卡器 SPI1（/dev/spidev1.2，需 dtoverlay=spi1-3cs）")
    args = parser.parse_args()

    hw_dir = os.path.dirname(os.path.abspath(__file__))
    if hw_dir not in sys.path:
        sys.path.insert(0, hw_dir)
    from rfid_driver import (
        DEFAULT_DOOR_BUS,
        DEFAULT_DOOR_DEVICE,
        DEFAULT_DOOR_PIN_RST,
        DEFAULT_FRONT_BUS,
        DEFAULT_FRONT_DEVICE,
        DEFAULT_FRONT_PIN_RST,
    )

    print("=" * 60)
    print("  RC522 RFID 模块诊断测试")
    if args.door:
        print("  模式：房门读卡器 SPI1")
        print("  接线：SDA→GPIO16(CE2), SCK→21, MOSI→20, MISO→19")
        print("        RST→GPIO26, 3.3V, GND  （需 /boot/config.txt: dtoverlay=spi1-3cs）")
    else:
        print("  模式：前台读卡器 SPI0")
        print("  接线：SDA→GPIO8, SCK→11, MOSI→10, MISO→9")
        print("        RST→GPIO25, 3.3V, GND")
    print("=" * 60)

    # 前置检查
    if not check_spi(require_door_dev=args.door):
        sys.exit(1)
    if not check_libraries():
        sys.exit(1)

    # SPI 底层通信检测（不依赖 mfrc522 库）
    if args.door:
        comm_ok = check_spi_comm(
            bus=DEFAULT_DOOR_BUS,
            device=DEFAULT_DOOR_DEVICE,
            rst_pin=DEFAULT_DOOR_PIN_RST,
            door=True,
        )
    else:
        comm_ok = check_spi_comm(
            bus=DEFAULT_FRONT_BUS,
            device=DEFAULT_FRONT_DEVICE,
            rst_pin=DEFAULT_FRONT_PIN_RST,
            door=False,
        )
    if not comm_ok:
        logger.error("SPI 底层通信异常，请先排查接线再继续。")
        # 不强制退出，允许继续测试

    import RPi.GPIO as GPIO

    # 根据模式选择测试方式
    if args.raw:
        reader = init_reader(door=args.door)
        if not reader:
            sys.exit(1)

        try:
            if args.loop:
                logger.info("进入循环原始读卡模式，Ctrl+C 停止...")
                while True:
                    read_raw(reader, timeout=args.timeout)
            else:
                print()
                logger.info("请将 RFID 卡/标签靠近读卡器...")
                read_raw(reader, timeout=args.timeout)
        except KeyboardInterrupt:
            logger.info("用户中断。")
        finally:
            try:
                reader.cleanup()
            except Exception:
                pass
            GPIO.cleanup()
    else:
        try:
            if args.loop:
                logger.info("进入循环驱动层读卡模式，Ctrl+C 停止...")
                while True:
                    logger.info("请将 RFID 卡/标签靠近读卡器（%g 秒超时）...", args.timeout)
                    read_via_driver(timeout=args.timeout, door=args.door)
                    time.sleep(0.3)
            else:
                logger.info("请将 RFID 卡/标签靠近读卡器（%g 秒超时）...", args.timeout)
                read_via_driver(timeout=args.timeout, door=args.door)
        except KeyboardInterrupt:
            logger.info("用户中断。")
        finally:
            try:
                GPIO.cleanup()
            except Exception:
                pass

    print()
    print("=" * 60)
    print("  诊断完成。常见问题速查：")
    print("  1. SPI 未启用  → sudo raspi-config → Interface Options → SPI")
    print("  2. 房门读卡器  → /boot/config.txt 添加 dtoverlay=spi1-3cs 后重启")
    print("  3. 接线错误    → 对照 docs/硬件引脚与部署说明.md 逐根检查")
    print("  4. 供电不足    → RC522 必须接 3.3V，勿接 5V；GND 共地")
    print("  5. 未用 sudo   → sudo python3 test_rfid.py [--door]")
    print("  6. 卡距离太远  → RC522 感应距离约 3~5cm，需正面靠近")
    print("  7. 驱动过滤太严→ 加 --raw 参数查看是否能读到原始数据")
    print("=" * 60)


if __name__ == "__main__":
    main()
