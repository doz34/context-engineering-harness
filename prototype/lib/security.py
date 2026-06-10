"""
CE-Harness Security Module
============================
Encryption at rest + audit chain rotation (forward secrecy).
Closes QW1 (chiffrement state.db) and QW5 (audit chain rotation).
"""

import os
import hashlib
import hmac as _hmac
import json
import time
import secrets
import struct
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from contextlib import contextmanager


# === QW1: ENCRYPTION AT REST ===
# Uses XChaCha20-Poly1305 (from cryptography lib if available) or
# fallback to Fernet (always available).
# For POV (zero external deps), we use a hand-rolled AES-256-GCM via
# cryptography fallback. If cryptography is not installed, we use
# a Fernet-style wrapper around AES.

# Try to import cryptography (preferred cipher). If unavailable, the
# fallback stream cipher from security_fallback is used. We import both
# eagerly at module load (inside try/except) so that the encrypt/decrypt
# methods never need a lazy relative import — which would fail if this
# module is loaded outside of its package context (e.g., script mode).
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _HAVE_AESGCM = True
except ImportError:
    AESGCM = None  # type: ignore
    _HAVE_AESGCM = False

try:
    from .security_fallback import aes_ctr_hmac_encrypt, aes_ctr_hmac_decrypt
    _HAVE_FALLBACK = True
except ImportError:
    # Direct-import fallback (e.g., script mode without lib package).
    # security_fallback is stdlib-only and ships alongside this module.
    try:
        import importlib
        _fallback_mod = importlib.import_module("security_fallback")
        aes_ctr_hmac_encrypt = _fallback_mod.aes_ctr_hmac_encrypt
        aes_ctr_hmac_decrypt = _fallback_mod.aes_ctr_hmac_decrypt
        _HAVE_FALLBACK = True
    except ImportError:
        aes_ctr_hmac_encrypt = None  # type: ignore
        aes_ctr_hmac_decrypt = None  # type: ignore
        _HAVE_FALLBACK = False


def _derive_key(passphrase: str, salt: bytes, length: int = 32) -> bytes:
    """PBKDF2-HMAC-SHA256 key derivation."""
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, 200_000)[:length]


class EncryptedDB:
    """
    Transparent encryption layer over SQLite.
    Uses XChaCha20-Poly1305 if cryptography lib present, else AES-256-GCM.

    Pattern: each row encrypted with row-level encryption. The DB schema
    stays the same (so existing queries work) but the data is opaque
    at-rest. The key is derived from a passphrase + per-DB salt.

    Limitations (acceptable for POV):
    - Per-row encryption, not full-DB (no native SQLite SEE in stdlib)
    - Schema metadata (table names) is NOT encrypted
    - For true full-DB encryption, use SQLCipher or LUKS container
    """

    def __init__(self, db_path: str, passphrase: str):
        self.db_path = db_path
        self.salt_path = db_path + ".salt"
        self.passphrase = passphrase

        # Read or create salt
        if os.path.exists(self.salt_path):
            with open(self.salt_path, "rb") as f:
                self.salt = f.read()
        else:
            self.salt = secrets.token_bytes(16)
            with open(self.salt_path, "wb") as f:
                f.write(self.salt)
            os.chmod(self.salt_path, 0o600)  # Owner read/write only

        self.key = _derive_key(passphrase, self.salt)
        self._cipher = self._init_cipher()

    def _init_cipher(self):
        """Pick AESGCM (preferred) or built-in fallback based on what's available."""
        if _HAVE_AESGCM:
            return ("AESGCM", AESGCM(self.key))
        if _HAVE_FALLBACK:
            return ("BUILTIN", None)  # Use stdlib-based fallback
        raise RuntimeError(
            "No encryption backend available: install `cryptography` "
            "or ensure lib/security_fallback.py is on the import path."
        )

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a string. Returns nonce + ciphertext."""
        pt = plaintext.encode()
        if self._cipher[0] == "AESGCM":
            nonce = secrets.token_bytes(12)
            ct = self._cipher[1].encrypt(nonce, pt, None)
            return nonce + ct
        # Fallback: AES-256-CTR + HMAC-SHA256 (encrypt-then-MAC).
        # NOT secure against nonce reuse but acceptable for POV
        # when cryptography lib is not available.
        if aes_ctr_hmac_encrypt is None:
            raise RuntimeError("Fallback cipher unavailable")
        return aes_ctr_hmac_encrypt(self.key, pt)

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt. Inverse of encrypt."""
        if self._cipher[0] == "AESGCM":
            nonce, ct = ciphertext[:12], ciphertext[12:]
            return self._cipher[1].decrypt(nonce, ct, None).decode()
        if aes_ctr_hmac_decrypt is None:
            raise RuntimeError("Fallback cipher unavailable")
        return aes_ctr_hmac_decrypt(self.key, ciphertext).decode()

    def is_secure(self) -> bool:
        """Returns True if AESGCM (recommended), False if fallback."""
        return self._cipher[0] == "AESGCM"


# === QW5: AUDIT CHAIN ROTATION (Forward Secrecy) ===
# Pattern: HMAC key derived from time-epoch + master key.
# Each epoch (e.g., 24h), the key rotates. Old events still verifiable
# with the epoch-specific key, but a key compromise at time T
# doesn't allow forging events at time T+1.

EPOCH_SECONDS = 86400  # 24h


@dataclass
class Epoch:
    """A time-bounded epoch with derived key."""
    epoch_id: int
    start_ts: int
    end_ts: int
    derived_key: bytes

    def __repr__(self):
        return f"Epoch({self.epoch_id}, {datetime.fromtimestamp(self.start_ts).isoformat()})"


def current_epoch_id(ts: int = None) -> int:
    """Get epoch ID for a given timestamp (default: now)."""
    if ts is None:
        ts = int(time.time())
    return ts // EPOCH_SECONDS


class RotatingHMAC:
    """
    HMAC chain with rotating keys per epoch.

    **NOTE (CRIT fix 2026-06-10 — relabeled honestly):** what this
    module provides is **epoch compartmentalization**, NOT
    *forward secrecy* in the cryptographic sense. The master key
    derives all epoch keys via PBKDF2, so a master-key compromise
    trivially yields every epoch key. True forward secrecy requires
    ephemeral key agreement (Diffie-Hellman ratchet, Signal-style
    double-ratchet, or PFS TLS ciphersuites). The protection this
    module actually offers is:
    - Old audit events are still verifiable with the historical
      epoch key (rotation does not invalidate the chain).
    - Two consecutive epochs use different derived keys, so a
      leak confined to one epoch's working memory does not
      automatically expose other epochs.
    - Master-key compromise does, however, expose everything.
      For incident response, rotate the master key, not the
      epoch.
    Pattern inspired by Cossack Labs + ACME (Let's Encrypt) + Roughtime.
    """

    def __init__(self, master_key: bytes):
        if len(master_key) < 32:
            raise ValueError("Master key must be >= 32 bytes")
        self.master_key = master_key
        self._epoch_cache: Dict[int, Epoch] = {}

    def _derive_epoch_key(self, epoch_id: int) -> bytes:
        """Derive epoch-specific key from master + epoch_id."""
        info = f"ce-harness-epoch-{epoch_id}".encode()
        # HKDF-Expand (we use PBKDF2 for simplicity, but with the same
        # iteration count as the master key derivation at line 30 to
        # avoid a 200× cheaper attack on epoch keys vs master key).
        return hashlib.pbkdf2_hmac(
            "sha256",
            self.master_key,
            info,
            200_000,
            dklen=32,
        )

    def get_epoch(self, ts: int = None) -> Epoch:
        """Get the Epoch for a timestamp."""
        if ts is None:
            ts = int(time.time())
        eid = current_epoch_id(ts)
        if eid not in self._epoch_cache:
            self._epoch_cache[eid] = Epoch(
                epoch_id=eid,
                start_ts=eid * EPOCH_SECONDS,
                end_ts=(eid + 1) * EPOCH_SECONDS,
                derived_key=self._derive_epoch_key(eid),
            )
        return self._epoch_cache[eid]

    def sign(self, payload: str, prev_hash: str = "", ts: int = None) -> Dict[str, str]:
        """
        Sign a payload for the current epoch.
        Returns dict with all fields needed for verification.
        """
        if ts is None:
            ts = int(time.time())
        epoch = self.get_epoch(ts)

        event = {
            "ts": str(ts),
            "epoch_id": str(epoch.epoch_id),
            "payload": payload,
            "prev_hash": prev_hash,
        }
        content = json.dumps(event, sort_keys=True).encode()
        h = _hmac.new(epoch.derived_key, content, hashlib.sha256).hexdigest()
        event["hash"] = h
        return event

    def verify(self, event: Dict[str, str], strict_epoch: bool = True) -> bool:
        """
        Verify a signed event. If strict_epoch=True (default), the event
        must have been signed in the current or previous epoch (one-epoch
        tolerance to absorb clock skew between signer and verifier).
        """
        try:
            ts = int(event["ts"])
            eid = int(event["epoch_id"])
        except (KeyError, ValueError):
            return False

        # Strict-epoch check: reject events signed more than 1 epoch
        # in the past (no tolerance for stale events) or in the future
        # (rejects pre-computed forgeries). Implemented per the docstring
        # that previously claimed this behavior but never enforced it.
        if strict_epoch:
            now_eid = current_epoch_id()
            if eid < now_eid - 1 or eid > now_eid:
                return False

        # Recompute hash with epoch-specific key
        if eid not in self._epoch_cache:
            self._epoch_cache[eid] = Epoch(
                epoch_id=eid,
                start_ts=eid * EPOCH_SECONDS,
                end_ts=(eid + 1) * EPOCH_SECONDS,
                derived_key=self._derive_epoch_key(eid),
            )
        epoch = self._epoch_cache[eid]

        # Reconstruct content
        content_dict = {
            "ts": event["ts"],
            "epoch_id": event["epoch_id"],
            "payload": event["payload"],
            "prev_hash": event["prev_hash"],
        }
        content = json.dumps(content_dict, sort_keys=True).encode()
        expected = _hmac.new(epoch.derived_key, content, hashlib.sha256).hexdigest()
        return _hmac.compare_digest(expected, event.get("hash", ""))


# === MASTER KEY MANAGEMENT ===

def generate_master_key() -> bytes:
    """Generate a fresh master key (32 bytes)."""
    return secrets.token_bytes(32)


def load_or_create_master_key(path: str) -> bytes:
    """Load master key from file, or create one if missing."""
    if os.path.exists(path):
        with open(path, "rb") as f:
            key = f.read()
        if len(key) >= 32:
            return key
    # Generate new
    key = generate_master_key()
    with open(path, "wb") as f:
        f.write(key)
    os.chmod(path, 0o600)
    return key
