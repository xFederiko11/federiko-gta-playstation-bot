import sqlite3
import tempfile
import unittest
from pathlib import Path

import cloud_state


class CloudStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "source.sqlite3"
        self.encrypted = self.root / ".state" / "bot.enc"
        self.restored = self.root / "restored.sqlite3"
        self.password = "test-password-long-enough"
        connection = sqlite3.connect(self.database)
        connection.execute("CREATE TABLE posts (body TEXT)")
        connection.execute("INSERT INTO posts VALUES ('public example; private local state')")
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_round_trip_and_ciphertext_does_not_expose_text(self):
        cloud_state.save_state(self.database, self.encrypted, self.password)
        raw = self.encrypted.read_bytes()
        self.assertNotIn(b"private local state", raw)
        self.assertTrue(cloud_state.restore_state(self.encrypted, self.restored, self.password))
        connection = sqlite3.connect(self.restored)
        self.assertEqual(connection.execute("SELECT body FROM posts").fetchone()[0], "public example; private local state")
        connection.close()

    def test_each_save_uses_fresh_salt_and_nonce(self):
        cloud_state.save_state(self.database, self.encrypted, self.password)
        first = self.encrypted.read_bytes()
        connection = sqlite3.connect(self.database)
        connection.execute("INSERT INTO posts VALUES ('new row')")
        connection.commit()
        connection.close()
        cloud_state.save_state(self.database, self.encrypted, self.password)
        self.assertNotEqual(self.encrypted.read_bytes(), first)

    def test_identical_state_does_not_create_a_new_ciphertext(self):
        cloud_state.save_state(self.database, self.encrypted, self.password)
        first = self.encrypted.read_bytes()
        cloud_state.save_state(self.database, self.encrypted, self.password)
        self.assertEqual(self.encrypted.read_bytes(), first)

    def test_save_with_changed_password_preserves_original_ciphertext(self):
        cloud_state.save_state(self.database, self.encrypted, self.password)
        first = self.encrypted.read_bytes()
        with self.assertRaises(cloud_state.StateError):
            cloud_state.save_state(self.database, self.encrypted, "different-password-long-enough")
        self.assertEqual(self.encrypted.read_bytes(), first)

    def test_wrong_password_does_not_overwrite_existing_database(self):
        cloud_state.save_state(self.database, self.encrypted, self.password)
        self.restored.write_bytes(b"keep this original")
        before = self.encrypted.read_bytes()
        with self.assertRaises(cloud_state.StateError):
            cloud_state.restore_state(self.encrypted, self.restored, "different-password-long-enough")
        self.assertEqual(self.restored.read_bytes(), b"keep this original")
        self.assertEqual(self.encrypted.read_bytes(), before)

    def test_corruption_and_short_password_are_rejected(self):
        cloud_state.save_state(self.database, self.encrypted, self.password)
        raw = bytearray(self.encrypted.read_bytes())
        raw[-1] ^= 1
        self.encrypted.write_bytes(raw)
        with self.assertRaises(cloud_state.StateError):
            cloud_state.restore_state(self.encrypted, self.restored, self.password)
        with self.assertRaises(cloud_state.StateError):
            cloud_state.restore_state(self.encrypted, self.restored, "short")
        self.assertFalse(self.restored.exists())

    def test_first_run_preserves_existing_local_database(self):
        self.restored.write_bytes(b"existing")
        self.assertFalse(cloud_state.restore_state(self.encrypted, self.restored, self.password))
        self.assertEqual(self.restored.read_bytes(), b"existing")

    def test_committed_wal_pages_are_included(self):
        connection = sqlite3.connect(self.database)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("INSERT INTO posts VALUES ('committed WAL row')")
        connection.commit()
        cloud_state.save_state(self.database, self.encrypted, self.password)
        cloud_state.restore_state(self.encrypted, self.restored, self.password)
        restored = sqlite3.connect(self.restored)
        self.assertEqual(restored.execute("SELECT count(*) FROM posts").fetchone()[0], 2)
        restored.close()
        connection.close()


if __name__ == "__main__":
    unittest.main()
