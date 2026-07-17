import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hardware"))

from database import hash_client_secret, normalize_client_secret, verify_client_secret


class PasswordStorageTests(unittest.TestCase):
    def test_round_trip_uses_unique_salts(self):
        digest = hashlib.sha256(b"correct horse battery staple").hexdigest()
        first = hash_client_secret(digest)
        second = hash_client_secret(digest)
        self.assertNotEqual(first, second)
        self.assertTrue(verify_client_secret(digest, first))
        self.assertTrue(verify_client_secret(digest, second))

    def test_wrong_secret_is_rejected(self):
        first = hashlib.sha256(b"first password").hexdigest()
        second = hashlib.sha256(b"second password").hexdigest()
        encoded = hash_client_secret(first)
        self.assertFalse(verify_client_secret(second, encoded))

    def test_replayable_plain_sha256_is_not_a_valid_database_record(self):
        digest = hashlib.sha256(b"not enough").hexdigest()
        self.assertFalse(verify_client_secret(digest, digest))

    def test_malformed_client_secret_is_rejected(self):
        for value in ("", "abc", "g" * 64, "a" * 63, "a" * 65):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_client_secret(value)


if __name__ == "__main__":
    unittest.main()
