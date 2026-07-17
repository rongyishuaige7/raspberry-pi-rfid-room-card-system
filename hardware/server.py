"""
树莓派TCP服务端
接收Qt客户端指令，控制硬件设备
"""
import socket
import threading
import json
import time
import signal
import sys
import secrets
import logging
import os
import re
from datetime import datetime, date
from rfid_driver import (
    RC522,
    DEFAULT_DOOR_BUS,
    DEFAULT_DOOR_DEVICE,
    DEFAULT_DOOR_PIN_RST,
)
from servo_control import ServoControl
from database import Database
from hardware_ext import HardwareAlerts, OLEDDisplay
import RPi.GPIO as GPIO

# 防止多个模块冲突，在服务入口统一设置
try:
    GPIO.setmode(GPIO.BCM)
except:
    pass

HOST = os.getenv('ROOMCARD_BIND_HOST', '127.0.0.1')
PORT = int(os.getenv('ROOMCARD_PORT', '8888'))
MAX_LINE_BYTES = int(os.getenv('ROOMCARD_MAX_LINE_BYTES', '8192'))
MAX_SESSIONS = int(os.getenv('ROOMCARD_MAX_SESSIONS', '256'))
SESSION_TTL_SECONDS = int(os.getenv('ROOMCARD_SESSION_TTL_SECONDS', '3600'))
logger = logging.getLogger(__name__)


def normalize_uid(uid):
    """Accept the decimal UID format produced by this RC522 driver."""
    value = str(uid).strip()
    if not re.fullmatch(r"[0-9]{1,20}", value):
        raise ValueError("卡号必须是 1 到 20 位十进制数字")
    return value


class CardServer:
    """房卡管理服务器"""

    # 角色与指令权限：Admin 全部（含审计日志）；其余角色不读取审计日志。
    _CMD_READ_ONLY = frozenset({'GET_STATS', 'GET_CARDS', 'GET_ROOMS', 'CHECK_CARD'})
    _CMD_FRONTDESK_OK = frozenset({'READ_CARD', 'ADD_CARD', 'LOST_CARD', 'CANCEL_CARD', 'OPEN_DOOR'})
    _CMD_HOUSEKEEPING_OK = _CMD_READ_ONLY | frozenset({'OPEN_DOOR'})

    def __init__(self):
        self.db = None
        self.rfid_front = None  # 前台读卡器 SPI0，用于 READ_CARD / 发卡
        self.rfid_door = None   # 房门读卡器 SPI1，用于无人值守刷卡开门
        self.servo = None
        self.running = True
        self.alerts = None
        self.display = None
        self._sessions = {}  # token -> {'username': str, 'role': 'Admin'|'FrontDesk'|'Housekeeping'}
        self._sessions_lock = threading.Lock()
        self.init_database()
        self.init_hardware()

        # 启动硬件监控后台线程 (无人值守刷卡逻辑)
        self.monitor_thread = threading.Thread(target=self._rfid_monitor_thread)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def _rfid_monitor_thread(self):
        """后台监控线程：处理物理刷卡开门"""
        logger.info("无人值守刷卡监控已启动")
        while self.running:
            if not self.rfid_door or not self.db:
                time.sleep(1)
                continue

            try:
                # 房门读卡器独立 SPI 总线，与前台读卡互不阻塞
                uid = self.rfid_door.read_card_uid(timeout=1.0)
                if uid:
                    logger.info("刷卡事件: 检测到卡片 %s", uid)
                    self.process_physical_swipe(uid)
            except Exception as e:
                logger.warning("监控线程异常: %s", e)

            time.sleep(0.1)

    def process_physical_swipe(self, uid):
        """处理物理刷卡逻辑"""
        card = self.db.get_card(uid)
        if not card:
            logger.warning("未授权卡片 %s", uid)
            if self.display:
                self.display.show_error("Unauthorized")
            if self.alerts:
                self.alerts.failure()
            self.db.add_log(uid, '刷卡', result=0, detail='非法卡片')
            return

        if card['status'] == 0:
            # 检查有效期
            expire = card['expire_date']
            if expire:
                if isinstance(expire, str):
                    expire = datetime.strptime(expire, '%Y-%m-%d').date()
                if expire < date.today():
                    logger.info("拒绝: 卡片 %s 已过期", uid)
                    if self.display:
                        self.display.show_error("Expired")
                    if self.alerts:
                        self.alerts.failure()
                    self.db.add_log(uid, '刷卡', result=0, detail='卡已过期')
                    return

            room_num = card.get('room_number') or '—'
            logger.info("验证通过: 房号 %s，准备下发舵机 PWM 序列", room_num)
            if self.display:
                self.display.show_card(uid[-6:], room_num)
            if self.alerts:
                self.alerts.success()
            if self.servo:
                try:
                    self.servo.open_door()
                    self.db.add_log(
                        uid,
                        '刷卡开门任务',
                        result=1,
                        detail='PWM序列已下发；没有门锁位置反馈',
                    )
                except Exception as exc:
                    logger.warning("舵机任务异常: %s", exc)
                    self.db.add_log(uid, '刷卡开门任务', result=0, detail='舵机任务异常')
            else:
                self.db.add_log(uid, '刷卡开门任务', result=0, detail='舵机未初始化')

        elif card['status'] == 1:
            logger.info("拒绝: 卡片 %s 已挂失", uid)
            if self.display:
                self.display.show_error("Lost Card")
            if self.alerts:
                self.alerts.failure()
            self.db.add_log(uid, '刷卡', result=0, detail='尝试使用挂失卡')

        elif card['status'] == 2:
            logger.info("拒绝: 卡片 %s 已注销", uid)
            if self.display:
                self.display.show_error("Cancelled")
            if self.alerts:
                self.alerts.failure()
            self.db.add_log(uid, '刷卡', result=0, detail='尝试使用注销卡')

    def init_database(self):
        """初始化数据库"""
        try:
            self.db = Database()
            logger.info("数据库连接成功")
        except Exception as e:
            self.db = None
            logger.error("数据库连接失败: %s", e)
            logger.info("请确认数据库服务已启动，并执行初始化脚本: sudo mysql < database/init.sql 或设置环境变量 ROOMCARD_DB_*")

    def require_db(self):
        """确保数据库可用"""
        if not self.db:
            return False, json.dumps({'code': 501, 'msg': '数据库未连接'})
        return True, None

    def _require_auth(self, token, cmd):
        """验证会话并检查该角色是否允许执行 cmd。返回 (session_dict, None) 或 (None, error_json)。"""
        if not token or not token.strip():
            return None, json.dumps({'code': 401, 'msg': '未登录或会话已失效'})
        with self._sessions_lock:
            session = self._sessions.get(token.strip())
            if session and time.monotonic() - session["last_seen"] > SESSION_TTL_SECONDS:
                self._sessions.pop(token.strip(), None)
                session = None
            elif session:
                session["last_seen"] = time.monotonic()
        if not session:
            return None, json.dumps({'code': 401, 'msg': '未登录或会话已失效'})
        role = session.get('role', 'Housekeeping')
        if role == 'Admin':
            return session, None
        if cmd in self._CMD_READ_ONLY:
            return session, None
        if role == 'Housekeeping':
            if cmd in self._CMD_HOUSEKEEPING_OK:
                return session, None
            return None, json.dumps({'code': 403, 'msg': '当前角色无此操作权限'})
        if role == 'FrontDesk' and cmd in self._CMD_FRONTDESK_OK:
            return session, None
        if role == 'FrontDesk' and cmd == 'DELETE_CARD':
            return None, json.dumps({'code': 403, 'msg': '前台角色不允许删除房卡记录'})
        return None, json.dumps({'code': 403, 'msg': '当前角色无此操作权限'})

    def init_hardware(self):
        """初始化硬件"""
        # 蜂鸣器低电平触发，尽早设为 HIGH 保持静音
        try:
            GPIO.setup(27, GPIO.OUT, initial=GPIO.HIGH)
            GPIO.setup(17, GPIO.OUT, initial=GPIO.LOW)
        except Exception:
            pass

        try:
            self.rfid_front = RC522()
            logger.info("前台 RFID (SPI0) 初始化成功")
        except Exception as e:
            self.rfid_front = None
            logger.warning(
                "前台 RFID 初始化失败: %s；请确保已启用 SPI0 (sudo raspi-config -> Interface Options -> SPI)",
                e,
            )

        try:
            self.rfid_door = RC522(
                bus=DEFAULT_DOOR_BUS,
                device=DEFAULT_DOOR_DEVICE,
                pin_rst=DEFAULT_DOOR_PIN_RST,
            )
            logger.info(
                "房门 RFID (SPI1 bus=%s dev=%s RST=GPIO%s) 初始化成功",
                DEFAULT_DOOR_BUS,
                DEFAULT_DOOR_DEVICE,
                DEFAULT_DOOR_PIN_RST,
            )
        except Exception as e:
            self.rfid_door = None
            logger.warning(
                "房门 RFID 初始化失败: %s；请在 /boot/config.txt 添加 dtoverlay=spi1-3cs 并接线 SPI1 CE2(GPIO16)，然后重启",
                e,
            )

        try:
            self.servo = ServoControl(pin=18)
            logger.info("舵机初始化成功")
        except Exception as e:
            logger.warning("舵机初始化失败: %s", e)

        try:
            self.alerts = HardwareAlerts()
            logger.info("报警模块初始化成功")
        except Exception as e:
            self.alerts = None
            logger.warning("报警模块初始化失败: %s", e)
            try:
                GPIO.output(27, GPIO.HIGH)  # 蜂鸣器低电平触发，HIGH 静音
            except Exception:
                pass

        try:
            self.display = OLEDDisplay()
            logger.info("OLED显示模块初始化成功")
        except Exception as e:
            logger.warning("OLED显示模块初始化失败: %s", e)

    def handle_client(self, conn, addr):
        """处理客户端连接"""
        logger.info("客户端连接: %s", addr)
        buffer = ""
        try:
            # 使用超时，便于服务停止时线程退出
            conn.settimeout(1.0)
            while self.running:
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue

                if not chunk:
                    break

                buffer += chunk.decode("utf-8", errors="strict")
                if len(buffer.encode("utf-8")) > MAX_LINE_BYTES and "\n" not in buffer:
                    conn.sendall((json.dumps({"code": 413, "msg": "请求过长"}) + "\n").encode("utf-8"))
                    return

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if len(line.encode('utf-8')) > MAX_LINE_BYTES:
                        conn.sendall((json.dumps({'code': 413, 'msg': '请求过长'}) + '\n').encode('utf-8'))
                        continue
                    line = line.strip()
                    if not line:
                        continue

                    logger.debug("收到指令: %s", line)
                    response = self.process_command(line)
                    if not response.endswith("\n"):
                        response += "\n"
                    conn.sendall(response.encode("utf-8"))
        except Exception as e:
            logger.warning("客户端异常: %s", e)
        finally:
            # 处理最后一条可能未带换行的指令
            line = buffer.strip()
            if line:
                try:
                    logger.debug("收到指令: %s", line)
                    response = self.process_command(line)
                    if not response.endswith("\n"):
                        response += "\n"
                    conn.sendall(response.encode("utf-8"))
                except Exception:
                    pass
            conn.close()
            logger.info("客户端断开: %s", addr)

    def process_command(self, data):
        """处理指令。除 LOGIN 外，首参为会话 token，用于鉴权。"""
        try:
            data = data.strip()
            parts = data.split(':')
            cmd = parts[0].strip() if parts else ''

            if cmd == 'LOGIN':
                user = parts[1].strip() if len(parts) > 1 else ''
                pwd = parts[2].strip() if len(parts) > 2 else ''
                return self.cmd_login(user, pwd)
            # 以下指令需要 token（parts[1]），其余参数顺延
            token = parts[1].strip() if len(parts) > 1 else ''
            session, err = self._require_auth(token, cmd)
            if err:
                return err

            if cmd == 'READ_CARD':
                return self.cmd_read_card()
            elif cmd == 'OPEN_DOOR':
                uid = parts[2].strip() if len(parts) > 2 else ''
                return self.cmd_open_door(uid, session)
            elif cmd == 'CHECK_CARD':
                uid = parts[2].strip() if len(parts) > 2 else ''
                return self.cmd_check_card(uid)
            elif cmd == 'GET_STATS':
                return self.cmd_get_stats()
            elif cmd == 'ADD_CARD':
                uid = parts[2].strip() if len(parts) > 2 else ''
                room_id = parts[3].strip() if len(parts) > 3 else None
                expire_date = parts[4].strip() if len(parts) > 4 else None
                operator = session.get('username') or 'unknown'
                return self.cmd_add_card(uid, room_id, expire_date, operator)
            elif cmd == 'LOST_CARD':
                uid = parts[2].strip() if len(parts) > 2 else ''
                operator = session.get('username') or 'unknown'
                return self.cmd_lost_card(uid, operator)
            elif cmd == 'CANCEL_CARD':
                uid = parts[2].strip() if len(parts) > 2 else ''
                operator = session.get('username') or 'unknown'
                return self.cmd_cancel_card(uid, operator)
            elif cmd == 'GET_LOGS':
                limit = 100
                if len(parts) > 2 and parts[2].strip():
                    try:
                        limit = int(parts[2].strip())
                    except ValueError:
                        limit = 100
                limit = max(1, min(limit, 500))
                return self.cmd_get_logs(limit)
            elif cmd == 'GET_CARDS':
                return self.cmd_get_cards()
            elif cmd == 'GET_ROOMS':
                return self.cmd_get_rooms()
            elif cmd == 'DELETE_CARD':
                uid = parts[2].strip() if len(parts) > 2 else ''
                return self.cmd_delete_card(uid, session.get('username') or 'unknown')
            else:
                return json.dumps({'code': 400, 'msg': '未知指令'})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_login(self, username, password):
        """处理登录验证"""
        try:
            ok, resp = self.require_db()
            if not ok: return resp

            # password 为客户端传来的 SHA256 十六进制串
            user = self.db.check_login(username, password)
            if user:
                role_map = {
                    'admin': 'Admin',
                    'operator': 'FrontDesk',
                    'viewer': 'Housekeeping'
                }
                c_role = role_map.get(user['role'], 'Housekeeping')
                token = secrets.token_urlsafe(32)
                with self._sessions_lock:
                    while len(self._sessions) >= MAX_SESSIONS:
                        self._sessions.pop(next(iter(self._sessions)))
                    self._sessions[token] = {
                        'username': user['username'],
                        'role': c_role,
                        'last_seen': time.monotonic(),
                    }
                return json.dumps({'code': 200, 'data': {'token': token, 'username': user['username'], 'role': c_role}})
            return json.dumps({'code': 401, 'msg': '用户名或密码错误'})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_read_card(self):
        """读卡 - 带超时"""
        try:
            if not self.rfid_front:
                return json.dumps({'code': 501, 'msg': '前台RFID模块未初始化'})

            logger.debug("读卡指令: 正在读取（前台读卡器）")

            # 客户端请求驱动，超时4秒；使用前台 SPI0 读卡器
            try:
                uid = self.rfid_front.read_card_uid(timeout=4.0)
                if uid:
                    logger.info("读卡成功: %s", uid)
                    return json.dumps({'code': 200, 'data': {'uid': uid}})
                return json.dumps({'code': 201, 'msg': '未检测到卡片'})
            except Exception as e:
                logger.warning("读卡错误: %s", e)
                return json.dumps({'code': 500, 'msg': str(e)})

        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_open_door(self, uid, session):
        """Queue a remote-open task after applying the role and card policy."""
        try:
            if not uid:
                return json.dumps({'code': 400, 'msg': '卡号不能为空'})
            try:
                uid = normalize_uid(uid)
            except ValueError as exc:
                return json.dumps({'code': 400, 'msg': str(exc)})

            ok, resp = self.require_db()
            if not ok:
                return resp

            # 检查卡状态
            card = self.db.get_card(uid)
            if not card:
                return json.dumps({'code': 202, 'msg': '卡不存在'})

            if card['status'] == 2:
                self.db.add_log(
                    uid,
                    '远程开门',
                    operator=session.get('username', 'unknown'),
                    result=0,
                    detail='非法尝试:卡已注销',
                )
                return json.dumps({'code': 204, 'msg': '卡已注销，禁止准入'})

            if not self.servo:
                self.db.add_log(
                    uid,
                    '远程开门任务',
                    operator=session.get('username', 'unknown'),
                    result=0,
                    detail='舵机未初始化',
                )
                return json.dumps({'code': 503, 'msg': '舵机未初始化，未下发开门任务'})

            detail = '正常卡远程开门'
            if card['status'] == 1:
                if session.get('role') != 'Admin':
                    self.db.add_log(
                        uid,
                        '远程开门',
                        operator=session.get('username', 'unknown'),
                        result=0,
                        detail='非管理员尝试为挂失卡开门',
                    )
                    return json.dumps({'code': 403, 'msg': '只有管理员可以为挂失卡下发紧急开门任务'})
                detail = '挂失卡紧急准入(管理员授权)'

            def do_open():
                try:
                    if self.display:
                        self.display.show_status("Remote Open", f"UID: {uid[-6:]}")
                    if self.alerts:
                        self.alerts.success()
                    self.servo.open_door()
                    self.db.add_log(
                        uid,
                        '远程开门任务',
                        operator=session.get('username', 'unknown'),
                        result=1,
                        detail=f'{detail}；PWM序列已下发，没有门锁位置反馈',
                    )
                except Exception as e:
                    logger.warning("开门线程异常: %s", e)
                    self.db.add_log(
                        uid,
                        '远程开门任务',
                        operator=session.get('username', 'unknown'),
                        result=0,
                        detail='舵机任务异常',
                    )

            t = threading.Thread(target=do_open)
            t.daemon = True
            t.start()
            return json.dumps({'code': 202, 'msg': '开门任务已下发；未确认舵机完成动作', 'actuation_confirmed': False})

        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_check_card(self, uid):
        """检查卡状态"""
        try:
            ok, resp = self.require_db()
            if not ok:
                return resp

            card = self.db.get_card(uid)
            if card:
                return json.dumps({'code': 200, 'data': {
                    'uid': card['uid'],
                    'status': card['status'],
                    'room_id': card['room_id'],
                    'expire_date': str(card['expire_date']) if card['expire_date'] else None
                }})
            return json.dumps({'code': 201, 'msg': '卡不存在'})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_add_card(self, uid, room_id=None, expire_date=None, operator='admin'):
        """添加房卡"""
        try:
            if not uid:
                return json.dumps({'code': 400, 'msg': '卡号不能为空'})
            try:
                uid = normalize_uid(uid)
            except ValueError as exc:
                return json.dumps({'code': 400, 'msg': str(exc)})

            ok, resp = self.require_db()
            if not ok:
                return resp

            # 无论旧卡是什么状态，允许覆盖发新卡
            existing = self.db.get_card(uid)
            if existing:
                # 如果更换了房间，理论上可以清理旧房间状态，但目前逻辑保证发卡即覆盖
                pass

            room_id = int(room_id) if room_id else None
            if room_id is not None and room_id <= 0:
                return json.dumps({'code': 400, 'msg': '房间 ID 必须是正整数'})
            if expire_date:
                try:
                    datetime.strptime(expire_date, '%Y-%m-%d')
                except ValueError:
                    return json.dumps({'code': 400, 'msg': '有效期必须使用 YYYY-MM-DD'})
            self.db.add_card(uid, room_id, expire_date)
            self.db.add_log(uid, '发行', operator=operator, result=1)
            return json.dumps({'code': 200, 'msg': '发卡成功'})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_lost_card(self, uid, operator='admin'):
        """挂失房卡"""
        try:
            ok, resp = self.require_db()
            if not ok:
                return resp

            card = self.db.get_card(uid)
            if not card:
                return json.dumps({'code': 201, 'msg': '卡不存在'})

            self.db.update_card_status(uid, 1)
            self.db.add_log(uid, '挂失', operator=operator, result=1)
            return json.dumps({'code': 200, 'msg': '挂失成功'})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_cancel_card(self, uid, operator='admin'):
        """注销房卡"""
        try:
            ok, resp = self.require_db()
            if not ok:
                return resp

            card = self.db.get_card(uid)
            if not card:
                return json.dumps({'code': 201, 'msg': '卡不存在'})

            self.db.update_card_status(uid, 2)
            self.db.add_log(uid, '注销', operator=operator, result=1)
            return json.dumps({'code': 200, 'msg': '注销成功'})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_get_logs(self, limit=100):
        """获取日志"""
        try:
            ok, resp = self.require_db()
            if not ok:
                return resp

            logs = self.db.get_logs(limit)
            log_list = []
            for log in logs:
                log_list.append({
                    'id': log['id'],
                    'card_uid': log['card_uid'],
                    'operation': log['operation'],
                    'operator': log['operator'],
                    'result': log['result'],
                    'detail': log.get('detail', ''),
                    'create_time': str(log['create_time'])
                })
            return json.dumps({'code': 200, 'data': log_list})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_get_cards(self):
        """获取房卡列表"""
        try:
            ok, resp = self.require_db()
            if not ok:
                return resp

            cards = self.db.get_all_cards()
            card_list = []
            for card in cards:
                card_list.append({
                    'id': card['id'],
                    'uid': card['uid'],
                    'room_id': card['room_id'],
                    'room_number': card.get('room_number', ''),
                    'status': card['status'],
                    'status_text': '正常' if card['status'] == 0 else ('挂失' if card['status'] == 1 else '注销'),
                    'expire_date': str(card['expire_date']) if card['expire_date'] else '',
                    'create_time': str(card['create_time']),
                    'update_time': str(card['update_time'])
                })
            return json.dumps({'code': 200, 'data': card_list})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_get_rooms(self):
        """获取房间列表"""
        try:
            ok, resp = self.require_db()
            if not ok:
                return resp

            self.db.refresh_expired_rooms()
            rooms = self.db.get_all_rooms()
            room_list = []
            for room in rooms:
                room_list.append({
                    'id': room['id'],
                    'room_number': room['room_number'],
                    'floor': room.get('floor', 0),
                    'status': room.get('status', 0),
                    'card_status': room.get('card_status'), # 新增关联卡状态字段
                    'create_time': str(room.get('create_time', '')) if room.get('create_time') else ''
                })
            return json.dumps({'code': 200, 'data': room_list})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_delete_card(self, uid, operator='admin'):
        """删除房卡(从数据库移除)"""
        try:
            if not uid:
                return json.dumps({'code': 400, 'msg': '卡号不能为空'})

            ok, resp = self.require_db()
            if not ok:
                return resp

            card = self.db.get_card(uid)
            if not card:
                return json.dumps({'code': 201, 'msg': '卡不存在'})

            self.db.remove_card(uid)
            self.db.add_log(uid, '删除', operator=operator, result=1)
            return json.dumps({'code': 200, 'msg': '删除成功'})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def cmd_get_stats(self):
        """获取统计"""
        try:
            ok, resp = self.require_db()
            if not ok:
                return resp

            stats = self.db.get_statistics()
            return json.dumps({'code': 200, 'data': stats})
        except Exception as e:
            return json.dumps({'code': 500, 'msg': str(e)})

    def start(self):
        """启动服务"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(5)
        logger.info("服务启动，监听 %s:%s", HOST, PORT)
        logger.info("等待客户端连接...")

        try:
            while self.running:
                conn, addr = server.accept()
                thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                thread.daemon = True
                thread.start()
        except KeyboardInterrupt:
            logger.info("收到退出信号")
        finally:
            self.running = False
            server.close()
            # 停止监控线程需要一点时间
            time.sleep(1.0)
            if self.rfid_front:
                self.rfid_front.cleanup()
            if self.rfid_door:
                self.rfid_door.cleanup()
            if self.servo:
                self.servo.cleanup()
            if self.alerts:
                self.alerts.cleanup()
            if self.db:
                self.db.close()
            try:
                GPIO.cleanup()
            except Exception:
                pass
            logger.info("服务已停止")


def signal_handler(sig, frame):
    logger.info("收到 Ctrl+C 信号，正在退出")
    sys.exit(0)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    signal.signal(signal.SIGINT, signal_handler)
    server = CardServer()
    server.start()
