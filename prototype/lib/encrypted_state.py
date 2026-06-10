"""
CE-Harness Encrypted StateDB
==============================
Wraps StateDB with file-level AES-256-GCM encryption at rest.

Strategy: the SQLite file is encrypted on close and decrypted on open.
During active use, a temp plaintext DB exists. On close, the temp is
encrypted and securely deleted. This avoids SQLCipher dependency and
works with stdlib sqlite3 + the existing EncryptedDB cipher.

v1.1 — Closes CRIT-1 (state.db plaintext, CWE-311).
"""

import os
import base64
import tempfile
import shutil
import struct
import hashlib
import secrets
from typing import Optional, Iterator
from contextlib import contextmanager

from .state import StateDB
from .security import EncryptedDB, _HAVE_AESGCM

# Marker bytes to identify encrypted files (magic + version)
_ENC_MAGIC = b"CTXHENC1"


def _is_encrypted(path: str) -> bool:
    """Check if a file starts with our encryption marker."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as f:
            return f.read(len(_ENC_MAGIC)) == _ENC_MAGIC
    except Exception:
        return False


def _secure_delete(path: str, passes: int = 3) -> None:
    """Overwrite file with random data before unlinking."""
    if not os.path.exists(path):
        return
    size = os.path.getsize(path)
    try:
        with open(path, "r+b") as f:
            for _ in range(passes):
                f.seek(0)
                f.write(secrets.token_bytes(size))
                f.flush()
                os.fsync(f.fileno())
    except Exception:
        pass
    os.unlink(path)


class EncryptedStateDB(StateDB):
    """StateDB subclass that encrypts the SQLite file at rest.

    On open (first conn() call), the encrypted .enc file is decrypted
    to a temporary plaintext file. On close(), the temp is encrypted
    back and securely deleted.

    The passphrase can come from:
    - CTXH_PASSPHRASE env var
    - .ctxh/state.key file (auto-generated if missing)
    - Explicit constructor argument

    Usage:
        state = EncryptedStateDB(path=".ctxh/state.db", passphrase="secret")
        # ... use normally (all StateDB methods work) ...
        state.close()  # encrypts and cleans up

    Or via env var:
        CTXH_ENCRYPTED=1 CTXH_PASSPHRASE=mysecret ctxh init
    """

    def __init__(self, path: str = ".ctxh/state.db",
                 passphrase: Optional[str] = None,
                 key_file: Optional[str] = None):
        self._enc_path = path + ".enc"
        self._key_file = key_file or (path + ".key")
        self._tmp_path: Optional[str] = None
        self._is_open = False
        self._edb: Optional[EncryptedDB] = None

        # Resolve passphrase
        if passphrase is None:
            passphrase = os.environ.get("CTXH_PASSPHRASE")
        if passphrase is None:
            passphrase = self._load_or_create_key()
        self._passphrase = passphrase

        # Decrypt to temp if encrypted file exists
        if _is_encrypted(self._enc_path):
            self._decrypt_to_temp()
        else:
            # First use or migration: create plaintext DB normally
            # It will be encrypted on first close()
            self._tmp_path = path

        # Initialize the parent StateDB with the (decrypted) path
        super().__init__(path=self._tmp_path)

    def _load_or_create_key(self) -> str:
        """Load key from file, or generate and persist one."""
        if os.path.exists(self._key_file):
            with open(self._key_file, "r") as f:
                return f.read().strip()
        key = secrets.token_hex(32)
        os.makedirs(os.path.dirname(self._key_file) or ".", exist_ok=True)
        with open(self._key_file, "w") as f:
            f.write(key)
        os.chmod(self._key_file, 0o600)
        return key

    def _decrypt_to_temp(self) -> None:
        """Decrypt .enc file to a temporary plaintext DB."""
        self._edb = EncryptedDB(
            db_path=self._enc_path, passphrase=self._passphrase
        )
        # Read encrypted file
        with open(self._enc_path, "rb") as f:
            raw = f.read()
        # Skip magic marker
        payload = raw[len(_ENC_MAGIC):]
        if not payload:
            # Empty encrypted DB: start fresh
            fd, self._tmp_path = tempfile.mkstemp(
                suffix=".db", prefix="ctxh_",
                dir=os.path.dirname(self._enc_path) or "."
            )
            os.close(fd)
            return
        # Payload is base64-encoded ciphertext (see _encrypt_from_temp)
        ciphertext = base64.b64decode(payload)
        decrypted_str = self._edb.decrypt(ciphertext)
        decrypted_bytes = base64.b64decode(decrypted_str)
        fd, self._tmp_path = tempfile.mkstemp(
            suffix=".db", prefix="ctxh_",
            dir=os.path.dirname(self._enc_path) or "."
        )
        with os.fdopen(fd, "wb") as f:
            f.write(decrypted_bytes)
        os.chmod(self._tmp_path, 0o600)

    def _encrypt_from_temp(self) -> None:
        """Encrypt temp DB back to .enc file, secure-delete temp."""
        if self._tmp_path is None or not os.path.exists(self._tmp_path):
            return

        if self._edb is None:
            self._edb = EncryptedDB(
                db_path=self._enc_path, passphrase=self._passphrase
            )

        # Read plaintext temp DB and base64-encode for string transport
        with open(self._tmp_path, "rb") as f:
            plaintext_bytes = f.read()
        plaintext_b64 = base64.b64encode(plaintext_bytes).decode("ascii")

        # Encrypt
        ciphertext = self._edb.encrypt(plaintext_b64)

        # Write encrypted file: magic + base64(ciphertext)
        with open(self._enc_path, "wb") as f:
            f.write(_ENC_MAGIC)
            f.write(base64.b64encode(ciphertext))
        os.chmod(self._enc_path, 0o600)

        # Secure-delete temp
        _secure_delete(self._tmp_path)
        self._tmp_path = None

    def close(self) -> None:
        """Encrypt and close the database."""
        if self._tmp_path and os.path.exists(self._tmp_path):
            # Checkpoint WAL before encrypting
            try:
                import sqlite3
                c = sqlite3.connect(self._tmp_path)
                c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                c.close()
            except Exception:
                pass
            self._encrypt_from_temp()
        self._is_open = False

    def __del__(self):
        """Ensure encryption on garbage collection."""
        try:
            self.close()
        except Exception:
            pass

    def is_encrypted_at_rest(self) -> bool:
        """Check if the encrypted file exists on disk."""
        return _is_encrypted(self._enc_path)

    @property
    def encryption_status(self) -> dict:
        """Return encryption metadata for health checks."""
        return {
            "encrypted_at_rest": self.is_encrypted_at_rest(),
            "cipher": "AES-256-GCM" if _HAVE_AESGCM else "SHA256-CTR-HMAC",
            "enc_path": self._enc_path,
            "key_file": self._key_file,
            "temp_active": self._tmp_path is not None
                           and os.path.exists(self._tmp_path or ""),
        }
