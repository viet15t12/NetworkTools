from __future__ import annotations

import sqlite3 as plaintext_sqlite
import tempfile
import unittest
from pathlib import Path

from infrastructure.database import sqlcipher
from infrastructure.security import clear_active_vault, configure_active_vault
from infrastructure.security.device_credentials import (
    ENVELOPE_PREFIX,
    decrypt_device_password,
    encrypt_device_password,
    migrate_device_passwords,
)


class DatabaseSecurityTests(unittest.TestCase):
    PASSPHRASE = "correct horse battery staple"

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        configure_active_vault(self.PASSPHRASE, self.root / "keys")
        sqlcipher.configure(self.PASSPHRASE)

    def tearDown(self) -> None:
        clear_active_vault()
        sqlcipher.clear()
        self.temporary.cleanup()

    def test_plaintext_database_is_migrated_and_standard_sqlite_cannot_read_it(self) -> None:
        database = self.root / "legacy.db"
        with plaintext_sqlite.connect(database) as connection:
            connection.execute(
                "CREATE TABLE t01_devices(host TEXT PRIMARY KEY, password TEXT)"
            )
            connection.execute(
                "INSERT INTO t01_devices VALUES (?, ?)", ("router-1", "secret")
            )

        self.assertTrue(sqlcipher.migrate_plaintext_database(database))
        self.assertNotEqual(database.read_bytes()[:16], b"SQLite format 3\x00")
        with self.assertRaises(plaintext_sqlite.DatabaseError):
            plaintext_sqlite.connect(database).execute(
                "SELECT * FROM t01_devices"
            ).fetchall()

        with sqlcipher.connect(database) as connection:
            self.assertEqual(
                connection.execute("SELECT host FROM t01_devices").fetchone()[0],
                "router-1",
            )

    def test_device_password_uses_hybrid_envelope_and_migrates_legacy_value(self) -> None:
        database = self.root / "devices.db"
        with sqlcipher.connect(database) as connection:
            connection.execute(
                "CREATE TABLE t01_devices(host TEXT PRIMARY KEY, password TEXT)"
            )
            connection.execute(
                "INSERT INTO t01_devices VALUES (?, ?)", ("router-1", "secret")
            )

        self.assertEqual(migrate_device_passwords(database), 1)
        with sqlcipher.connect(database) as connection:
            stored = connection.execute(
                "SELECT password FROM t01_devices WHERE host = ?", ("router-1",)
            ).fetchone()[0]
        self.assertTrue(stored.startswith(ENVELOPE_PREFIX))
        self.assertNotIn("secret", stored)
        self.assertEqual(decrypt_device_password(stored), "secret")
        self.assertNotEqual(encrypt_device_password("secret"), stored)

    def test_private_key_is_encrypted_and_wrong_database_key_fails(self) -> None:
        private_key = (self.root / "keys" / "device_credentials_private.pem").read_text()
        self.assertIn("ENCRYPTED PRIVATE KEY", private_key)
        self.assertNotIn("BEGIN RSA PRIVATE KEY", private_key)

        database = self.root / "encrypted.db"
        with sqlcipher.connect(database) as connection:
            connection.execute("CREATE TABLE example(value TEXT)")
        sqlcipher.configure("this is the wrong passphrase")
        with self.assertRaises(sqlcipher.DatabaseError):
            sqlcipher.connect(database)


if __name__ == "__main__":
    unittest.main()
