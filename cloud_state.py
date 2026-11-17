"""Persist SQLite state encrypted in a public repository, with no cloud database.

The password lives in a GitHub Actions secret. Only the authenticated ciphertext
is committed. The SQLite backup API includes committed WAL pages consistently.
"""

import os
import secrets
import sqlite3
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"GTASTATE\x01"
SALT_BYTES = 16
NONCE_BYTES = 12
SQLITE_HEADER = b"SQLite format 3\x00"


class StateError(RuntimeError):
    """A state operation failed without exposing its password or plaintext."""


def _key(password, salt):
    if not isinstance(password, str) or len(password) < 16:
        raise StateError("STATE_PASSWORD deve contenere almeno 16 caratteri")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def _atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + path.name + ".", delete=False) as stream:
            temp_name = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        os.chmod(path, 0o600)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def _validate_sqlite(content):
    if not content.startswith(SQLITE_HEADER):
        raise StateError("Lo stato decifrato non è un database SQLite valido")
    connection = sqlite3.connect(":memory:")
    try:
        connection.deserialize(content)
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise StateError("Il database di stato non supera il controllo di integrità")
    except sqlite3.DatabaseError as error:
        raise StateError("Il database di stato non è leggibile") from error
    finally:
        connection.close()


def _decrypt(raw, password):
    start = len(MAGIC)
    if not raw.startswith(MAGIC) or len(raw) < start + SALT_BYTES + NONCE_BYTES + 16:
        raise StateError("Formato dello stato cifrato non valido o non supportato")
    salt = raw[start:start + SALT_BYTES]
    nonce = raw[start + SALT_BYTES:start + SALT_BYTES + NONCE_BYTES]
    ciphertext = raw[start + SALT_BYTES + NONCE_BYTES:]
    try:
        return AESGCM(_key(password, salt)).decrypt(nonce, ciphertext, MAGIC + salt)
    except InvalidTag as error:
        raise StateError("STATE_PASSWORD errata oppure stato cifrato danneggiato; il file originale è conservato") from error


def restore_state(encrypted_path, db_path, password):
    """Restore a verified state atomically; return False for the first run.

    A missing ciphertext never removes an existing local database. Wrong keys,
    corrupt data and unsupported formats never overwrite the destination.
    """
    path = Path(encrypted_path)
    # Validate even on the first run so it cannot start without durable state.
    if not isinstance(password, str) or len(password) < 16:
        raise StateError("STATE_PASSWORD deve contenere almeno 16 caratteri")
    if not path.exists():
        return False
    plain = _decrypt(path.read_bytes(), password)
    _validate_sqlite(plain)
    _atomic_write(Path(db_path), plain)
    return True


def save_state(db_path, encrypted_path, password):
    """Save one consistent SQLite snapshot as authenticated ciphertext."""
    source = Path(db_path).resolve()
    if not source.is_file():
        raise StateError("Il database da salvare non esiste")
    salt, nonce = secrets.token_bytes(SALT_BYTES), secrets.token_bytes(NONCE_BYTES)
    key = _key(password, salt)
    database = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    # A WAL backup retains the WAL header even in an in-memory destination.
    # Convert a private temporary copy to DELETE mode; this keeps the encrypted
    # snapshot self-contained without altering the live database's journal mode.
    with tempfile.TemporaryDirectory(prefix="gta-state-") as directory:
        snapshot_path = Path(directory) / "snapshot.sqlite3"
        snapshot = sqlite3.connect(snapshot_path)
        try:
            database.backup(snapshot)
            snapshot.execute("PRAGMA journal_mode=DELETE")
            snapshot.commit()
        except sqlite3.DatabaseError as error:
            raise StateError("Impossibile creare una copia coerente del database") from error
        finally:
            database.close()
            snapshot.close()
        plain = snapshot_path.read_bytes()
    _validate_sqlite(plain)
    target = Path(encrypted_path)
    if target.exists():
        # Do not replace valid durable state with a different password by
        # accident, and avoid needless Git commits when nothing changed.
        if _decrypt(target.read_bytes(), password) == plain:
            return target
    ciphertext = AESGCM(key).encrypt(nonce, plain, MAGIC + salt)
    _atomic_write(target, MAGIC + salt + nonce + ciphertext)
    return target
