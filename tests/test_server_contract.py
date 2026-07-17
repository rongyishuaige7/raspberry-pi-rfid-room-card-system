import json
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hardware"))

# The server is tested without importing Raspberry Pi-only packages.
gpio = types.ModuleType("RPi.GPIO")
gpio.BCM = 11
gpio.OUT = 0
gpio.HIGH = 1
gpio.LOW = 0
gpio.getmode = lambda: gpio.BCM
gpio.setmode = lambda *_: None
gpio.setup = lambda *_args, **_kwargs: None
gpio.output = lambda *_: None
gpio.cleanup = lambda *_: None
gpio.PWM = lambda *_: types.SimpleNamespace(
    start=lambda *_: None,
    stop=lambda: None,
    ChangeDutyCycle=lambda *_: None,
)
rpi = types.ModuleType("RPi")
rpi.GPIO = gpio
sys.modules.setdefault("RPi", rpi)
sys.modules.setdefault("RPi.GPIO", gpio)

mfrc522 = types.ModuleType("mfrc522")
mfrc522.MFRC522 = object
sys.modules.setdefault("mfrc522", mfrc522)

from server import CardServer, normalize_uid


class FakeDatabase:
    def __init__(self, card=None, user=None):
        self.card = card
        self.user = user
        self.logs = []

    def get_card(self, _uid):
        return self.card

    def check_login(self, _username, _digest):
        return self.user

    def add_log(self, uid, operation, operator="system", result=1, detail=""):
        self.logs.append((uid, operation, operator, result, detail))


class FakeServo:
    def __init__(self):
        self.calls = 0

    def open_door(self):
        self.calls += 1


class ServerContractTests(unittest.TestCase):
    def make_server(self, *, card=None, user=None, servo=None):
        server = CardServer.__new__(CardServer)
        server.db = FakeDatabase(card=card, user=user)
        server.rfid_front = None
        server.rfid_door = None
        server.servo = servo
        server.alerts = None
        server.display = None
        server.running = True
        server._sessions = {}
        server._sessions_lock = threading.Lock()
        return server

    def test_uid_contract(self):
        self.assertEqual(normalize_uid("123456"), "123456")
        for value in ("", "abc", "12:34", "1" * 21):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_uid(value)

    def test_unauthenticated_commands_are_rejected(self):
        server = self.make_server()
        response = json.loads(server.process_command("GET_STATS:"))
        self.assertEqual(response["code"], 401)

    def test_login_session_carries_role_and_last_seen(self):
        server = self.make_server(user={"username": "demo", "role": "operator"})
        response = json.loads(server.cmd_login("demo", "a" * 64))
        token = response["data"]["token"]
        self.assertEqual(response["data"]["role"], "FrontDesk")
        self.assertEqual(len(token) >= 40, True)
        self.assertIn("last_seen", server._sessions[token])

    def test_front_desk_cannot_emergency_open_lost_card(self):
        card = {"status": 1, "room_number": "101"}
        servo = FakeServo()
        server = self.make_server(card=card, servo=servo)
        response = json.loads(server.cmd_open_door(
            "123456", {"username": "front", "role": "FrontDesk"}
        ))
        self.assertEqual(response["code"], 403)
        self.assertEqual(servo.calls, 0)

    def test_front_desk_cannot_read_audit_logs(self):
        server = self.make_server()
        token = "front-session"
        server._sessions[token] = {
            "username": "front",
            "role": "FrontDesk",
            "last_seen": time.monotonic(),
        }
        response = json.loads(server.process_command(f"GET_LOGS:{token}:100"))
        self.assertEqual(response["code"], 403)

    def test_housekeeping_cannot_read_audit_logs(self):
        server = self.make_server()
        token = "housekeeping-session"
        server._sessions[token] = {
            "username": "cleaner",
            "role": "Housekeeping",
            "last_seen": time.monotonic(),
        }
        response = json.loads(server.process_command(f"GET_LOGS:{token}:100"))
        self.assertEqual(response["code"], 403)

    def test_admin_dispatch_does_not_claim_actuation_confirmation(self):
        card = {"status": 0, "room_number": "101"}
        servo = FakeServo()
        server = self.make_server(card=card, servo=servo)
        with mock.patch("server.threading.Thread") as thread_cls:
            response = json.loads(server.cmd_open_door(
                "123456", {"username": "admin", "role": "Admin"}
            ))
        self.assertEqual(response["code"], 202)
        self.assertFalse(response["actuation_confirmed"])
        thread_cls.assert_called_once()

    def test_missing_servo_is_not_reported_as_success(self):
        card = {"status": 0, "room_number": "101"}
        server = self.make_server(card=card, servo=None)
        response = json.loads(server.cmd_open_door(
            "123456", {"username": "admin", "role": "Admin"}
        ))
        self.assertEqual(response["code"], 503)


if __name__ == "__main__":
    unittest.main()
