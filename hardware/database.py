"""
数据库操作模块
连接MySQL数据库，执行房卡相关操作
"""
import os
import logging
import threading
import pymysql
import hashlib
import hmac
import secrets
from datetime import datetime, date

logger = logging.getLogger(__name__)

PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000


def normalize_client_secret(client_sha256):
    """Validate the SHA-256 value sent by the historical Qt client."""
    value = str(client_sha256).strip().lower()
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("client secret must be a 64-character SHA-256 hex value")
    return value


def hash_client_secret(client_sha256, *, iterations=PASSWORD_ITERATIONS, salt=None):
    """Hash the client-side digest again before storing it in MariaDB."""
    secret = normalize_client_secret(client_sha256)
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("ascii"),
        salt_bytes,
        iterations,
    )
    return f"{PASSWORD_SCHEME}${iterations}${salt_bytes.hex()}${digest.hex()}"


def verify_client_secret(client_sha256, encoded):
    """Constant-time verification for the PBKDF2 database representation."""
    try:
        scheme, iterations_text, salt_hex, digest_hex = str(encoded).split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        expected = bytes.fromhex(digest_hex)
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            normalize_client_secret(client_sha256).encode("ascii"),
            bytes.fromhex(salt_hex),
            iterations,
        )
        return hmac.compare_digest(candidate, expected)
    except (TypeError, ValueError):
        return False


class Database:
    def __init__(self, host=None, port=None, user=None,
                 password=None, database=None, unix_socket=None):
        """初始化数据库连接

        Args:
            host: 数据库主机地址
            port: 端口
            user: 用户名
            password: 密码
            database: 数据库名
            unix_socket: MySQL/MariaDB socket 路径(可选)

        环境变量(可选):
            ROOMCARD_DB_HOST / ROOMCARD_DB_PORT / ROOMCARD_DB_USER / ROOMCARD_DB_PASSWORD / ROOMCARD_DB_NAME
            ROOMCARD_DB_SOCKET

        说明:
            Raspberry Pi OS 默认常用 MariaDB，root 账号可能使用 unix_socket 认证。
            若 TCP(root@localhost) 无法连接，会自动尝试常见的 socket 路径。
        """

        self.host = host or os.getenv('ROOMCARD_DB_HOST', 'localhost')
        self.port = int(port or os.getenv('ROOMCARD_DB_PORT', '3306'))
        self.user = user or os.getenv('ROOMCARD_DB_USER', 'roomcard')
        self.password = password if password is not None else os.getenv('ROOMCARD_DB_PASSWORD', '')
        self.database = database or os.getenv('ROOMCARD_DB_NAME', 'room_card_system')
        self.unix_socket = unix_socket or os.getenv('ROOMCARD_DB_SOCKET') or None
        self.connection = None
        self._lock = threading.Lock()  # pymysql 连接非线程安全，串行化访问
        self.connect()

    def connect(self):
        """连接数据库"""
        last_error = None

        def _connect_with(unix_socket_path=None):
            kwargs = dict(
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
            )

            if unix_socket_path:
                kwargs["unix_socket"] = unix_socket_path
            else:
                kwargs["host"] = self.host
                kwargs["port"] = self.port

            return pymysql.connect(**kwargs)

        # 1) 先按配置连接（host/port 或显式 socket）
        try:
            self.connection = _connect_with(self.unix_socket)
            return
        except Exception as e:
            last_error = e

        # 2) Raspberry Pi OS / Debian 上常见：root 使用 unix_socket 认证
        if not self.unix_socket and self.host in ("localhost", "127.0.0.1"):
            socket_candidates = (
                "/run/mysqld/mysqld.sock",
                "/var/run/mysqld/mysqld.sock",
                "/tmp/mysql.sock",
            )
            for sock in socket_candidates:
                if not os.path.exists(sock):
                    continue
                try:
                    self.connection = _connect_with(sock)
                    self.unix_socket = sock
                    return
                except Exception as e:
                    last_error = e

        raise last_error

    def close(self):
        """关闭连接"""
        if self.connection:
            self.connection.close()

    def execute(self, sql, params=None):
        """执行SQL"""
        with self._lock:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
                self.connection.commit()
                return cursor.lastrowid

    def query(self, sql, params=None):
        """查询"""
        with self._lock:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()

    # === 账户操作 ===
    def check_login(self, username, password_hash):
        """Verify a login without storing the replayable client digest."""
        test_sql = "SELECT username, password, role FROM user WHERE username = %s"
        test_res = self.query(test_sql, (username,))
        if not test_res:
            return None
        if verify_client_secret(password_hash, test_res[0].get("password", "")):
            return test_res[0]
        return None

    def upsert_user(self, username, client_sha256, role):
        """Create or replace a local demo user with a salted password hash."""
        if role not in {"admin", "operator", "viewer"}:
            raise ValueError("role must be admin, operator, or viewer")
        username = str(username).strip()
        if not username or len(username) > 50:
            raise ValueError("username must contain 1 to 50 characters")
        encoded = hash_client_secret(client_sha256)
        sql = """
            INSERT INTO user (username, password, role)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE password = VALUES(password), role = VALUES(role)
        """
        self.execute(sql, (username, encoded, role))

    # === 房卡操作 ===
    def add_card(self, uid, room_id=None, expire_date=None):
        """Create or reissue a card without REPLACE's delete-and-insert side effect."""
        # 1. 记录该卡之前的房间 ID
        old_card = self.get_card(uid)
        old_room_id = old_card['room_id'] if old_card else None

        # 2. 原地更新已有记录，保留主键和 create_time。
        sql = """
            INSERT INTO card (uid, room_id, status, expire_date)
            VALUES (%s, %s, 0, %s)
            ON DUPLICATE KEY UPDATE
                room_id = VALUES(room_id),
                status = 0,
                expire_date = VALUES(expire_date),
                update_time = NOW()
        """
        last_id = self.execute(sql, (uid, room_id, expire_date))

        # 3. 同步新房间状态为已入住
        if room_id:
            self.update_room_status(room_id, 1)

        # 4. 如果换了房间，检查并清理旧房间的占用状态
        if old_room_id and old_room_id != room_id:
            self.sync_room_occupancy(old_room_id)

        return last_id

    def sync_room_occupancy(self, room_id):
        """根据该房间下是否有‘有效活跃且非注销且未过期’的卡片来校准房间状态"""
        sql = "SELECT COUNT(*) as count FROM card WHERE room_id = %s AND status != 2 AND (expire_date IS NULL OR expire_date >= CURDATE())"
        res = self.query(sql, (room_id,))
        count = res[0]['count'] if res else 0

        # 如果没有活跃卡片了，房间变为空闲(0)，否则为占用(1)
        new_status = 1 if count > 0 else 0
        self.update_room_status(room_id, new_status)

    def get_card(self, uid):
        """获取房卡信息（含房间号，便于刷卡时显示屏显示）"""
        sql = "SELECT c.*, r.room_number FROM card c LEFT JOIN room r ON c.room_id = r.id WHERE c.uid = %s"
        result = self.query(sql, (uid,))
        return result[0] if result else None

    def update_card_status(self, uid, status):
        """更新房卡状态"""
        # 如果是注销(2)，则释放房间
        if status == 2:
            card = self.get_card(uid)
            if card and card['room_id']:
                self.update_room_status(card['room_id'], 0)

        sql = "UPDATE card SET status = %s, update_time = NOW() WHERE uid = %s"
        return self.execute(sql, (status, uid))

    def bind_room(self, uid, room_id):
        """绑定房间"""
        sql = "UPDATE card SET room_id = %s, update_time = NOW() WHERE uid = %s"
        return self.execute(sql, (room_id, uid))

    def get_all_cards(self):
        """获取所有房卡"""
        sql = "SELECT c.*, r.room_number FROM card c LEFT JOIN room r ON c.room_id = r.id ORDER BY c.create_time DESC"
        return self.query(sql)

    def delete_card(self, uid):
        """注销房卡"""
        sql = "UPDATE card SET status = 2 WHERE uid = %s"
        return self.execute(sql, (uid,))

    def remove_card(self, uid):
        """删除房卡"""
        sql = "DELETE FROM card WHERE uid = %s"
        return self.execute(sql, (uid,))

    # === 房间操作 ===
    def add_room(self, room_number, floor=1):
        """新增房间"""
        sql = "INSERT INTO room (room_number, floor) VALUES (%s, %s)"
        return self.execute(sql, (room_number, floor))

    def get_all_rooms(self):
        """获取所有房间及关联卡状态（LEFT JOIN 派生表，一次查询；排除已过期卡）"""
        sql = """
            SELECT r.*, sub.card_status
            FROM room r
            LEFT JOIN (
                SELECT room_id, MIN(status) AS card_status
                FROM card
                WHERE status != 2
                  AND (expire_date IS NULL OR expire_date >= CURDATE())
                GROUP BY room_id
            ) sub ON sub.room_id = r.id
            ORDER BY r.floor, r.room_number
        """
        return self.query(sql)

    def update_room_status(self, room_id, status):
        """更新房间状态"""
        sql = "UPDATE room SET status = %s WHERE id = %s"
        return self.execute(sql, (status, room_id))

    def refresh_expired_rooms(self):
        """将仅剩已过期/已注销卡片的房间状态校正为空闲"""
        sql = """
            UPDATE room SET status = 0
            WHERE status = 1
              AND id NOT IN (
                  SELECT room_id FROM card
                  WHERE status != 2
                    AND (expire_date IS NULL OR expire_date >= CURDATE())
                    AND room_id IS NOT NULL
              )
        """
        self.execute(sql)

    # === 日志操作 ===
    def add_log(self, card_uid, operation, operator='system', result=1, detail=''):
        """添加操作日志"""
        sql = "INSERT INTO operation_log (card_uid, operation, operator, result, detail) VALUES (%s, %s, %s, %s, %s)"
        return self.execute(sql, (card_uid, operation, operator, result, detail))

    def get_logs(self, limit=100):
        """获取日志"""
        sql = "SELECT * FROM operation_log ORDER BY create_time DESC LIMIT %s"
        return self.query(sql, (limit,))

    def get_logs_by_card(self, uid):
        """获取某卡的操作日志"""
        sql = "SELECT * FROM operation_log WHERE card_uid = %s ORDER BY create_time DESC"
        return self.query(sql, (uid,))

    # === 统计 ===
    def get_statistics(self):
        """获取统计数据（单次查询合并）"""
        sql = """
            SELECT
                (SELECT COUNT(*) FROM card WHERE status != 2) AS total_cards,
                (SELECT COUNT(*) FROM card WHERE status = 0) AS normal_cards,
                (SELECT COUNT(*) FROM card WHERE status = 1) AS lost_cards,
                (SELECT COUNT(*) FROM operation_log
                 WHERE operation IN ('远程开门任务', '刷卡开门任务')
                   AND result = 1
                   AND DATE(create_time) = CURDATE()) AS today_opens,
                (SELECT COUNT(*) FROM room) AS total_rooms,
                (SELECT COALESCE(SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END), 0) FROM room) AS idle_rooms,
                (SELECT COALESCE(SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END), 0) FROM room) AS busy_rooms
        """
        result = self.query(sql)
        if not result:
            return {
                'total_cards': 0, 'normal_cards': 0, 'lost_cards': 0,
                'today_opens': 0, 'total_rooms': 0, 'idle_rooms': 0, 'busy_rooms': 0
            }
        row = result[0]
        return {
            'total_cards': row['total_cards'] or 0,
            'normal_cards': row['normal_cards'] or 0,
            'lost_cards': row['lost_cards'] or 0,
            'today_opens': row['today_opens'] or 0,
            'total_rooms': row['total_rooms'] or 0,
            'idle_rooms': int(row['idle_rooms'] or 0),
            'busy_rooms': int(row['busy_rooms'] or 0),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db = Database()
    logger.info("统计: %s", db.get_statistics())
    logger.info("房间: %s", db.get_all_rooms())
    logger.info("房卡: %s", db.get_all_cards())
    db.close()
