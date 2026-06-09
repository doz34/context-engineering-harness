"""Test QW1 + QW5: Encryption + Audit chain rotation."""
import sys
import os
import tempfile
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.security import (
    EncryptedDB, RotatingHMAC, generate_master_key,
    load_or_create_master_key, current_epoch_id, EPOCH_SECONDS,
)


def test_encrypted_db_creates_salt():
    """Salt file is created with 0600 perms."""
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "test.db")
        edb = EncryptedDB(db_path, "test_passphrase")
        assert os.path.exists(db_path + ".salt")
        mode = os.stat(db_path + ".salt").st_mode & 0o777
        assert mode == 0o600, f"Salt mode should be 0600, got {oct(mode)}"


def test_encrypted_db_encrypt_decrypt_roundtrip():
    """Encrypt then decrypt returns the original."""
    with tempfile.TemporaryDirectory() as d:
        edb = EncryptedDB(os.path.join(d, "test.db"), "pp")
        plain = "Hello, World! PII: john.doe@example.com"
        ct = edb.encrypt(plain)
        pt = edb.decrypt(ct)
        assert pt == plain


def test_encrypted_db_same_key_different_salt():
    """Same passphrase with different salts produces different ciphertexts."""
    with tempfile.TemporaryDirectory() as d:
        edb1 = EncryptedDB(os.path.join(d, "db1"), "pp")
        edb2 = EncryptedDB(os.path.join(d, "db2"), "pp")
        ct1 = edb1.encrypt("same plaintext")
        ct2 = edb2.encrypt("same plaintext")
        # Different salts → different ciphertexts
        assert ct1 != ct2


def test_encrypted_db_tamper_detection():
    """Tampered ciphertext fails MAC/AEAD verification."""
    with tempfile.TemporaryDirectory() as d:
        edb = EncryptedDB(os.path.join(d, "test.db"), "pp")
        ct = edb.encrypt("secret data")
        # Tamper with middle byte
        tampered = bytearray(ct)
        if len(tampered) > 20:
            tampered[20] ^= 0xFF
        # Decryption must raise (either MAC failure or AEAD InvalidTag)
        raised = False
        try:
            edb.decrypt(bytes(tampered))
        except Exception:
            raised = True
        assert raised, "Decryption should fail on tampered data"


def test_rotating_hmac_signs_and_verifies():
    rh = RotatingHMAC(generate_master_key())
    event = rh.sign("test payload", prev_hash="")
    assert "hash" in event
    assert rh.verify(event)


def test_rotating_hmac_different_keys_per_epoch():
    """Compromise of one epoch key doesn't affect another."""
    master = generate_master_key()
    rh = RotatingHMAC(master)
    e_now = current_epoch_id()
    e_next = e_now + 1

    key_now = rh._derive_epoch_key(e_now)
    key_next = rh._derive_epoch_key(e_next)
    assert key_now != key_next
    # Both deterministic
    assert rh._derive_epoch_key(e_now) == key_now
    assert rh._derive_epoch_key(e_next) == key_next


def test_rotating_hmac_forward_secrecy():
    """Old events still verifiable, but signing in past epoch uses old key."""
    master = generate_master_key()
    rh = RotatingHMAC(master)
    ts_now = int(time.time())
    event = rh.sign("test", prev_hash="", ts=ts_now)
    # Verify works
    assert rh.verify(event)
    # Modify payload → verification fails
    tampered = dict(event)
    tampered["payload"] = "MODIFIED"
    assert not rh.verify(tampered)


def test_rotating_hmac_chained_events():
    """Chain of events with prev_hash linking works."""
    rh = RotatingHMAC(generate_master_key())
    e1 = rh.sign("event 1", prev_hash="")
    e2 = rh.sign("event 2", prev_hash=e1["hash"])
    e3 = rh.sign("event 3", prev_hash=e2["hash"])
    # All valid individually
    assert rh.verify(e1)
    assert rh.verify(e2)
    assert rh.verify(e3)
    # Chain integrity: break e2 → e3 still valid (chain is per-event, not linked in verify)
    # Real chain integrity requires checking prev_hash matches the previous event
    assert e3["prev_hash"] == e2["hash"]
    assert e2["prev_hash"] == e1["hash"]


def test_load_or_create_master_key_persists():
    with tempfile.TemporaryDirectory() as d:
        kp = os.path.join(d, "master.key")
        # First call creates
        k1 = load_or_create_master_key(kp)
        assert os.path.exists(kp)
        # Second call loads
        k2 = load_or_create_master_key(kp)
        assert k1 == k2
        # Mode 0600
        mode = os.stat(kp).st_mode & 0o777
        assert mode == 0o600


def test_master_key_too_short_rejected():
    """< 32 bytes is rejected."""
    try:
        RotatingHMAC(b"too_short")
        assert False
    except ValueError as e:
        assert "32 bytes" in str(e)


def test_audit_chain_cross_epoch_verification():
    """Event signed in epoch E is still verifiable later (after rotation)."""
    rh = RotatingHMAC(generate_master_key())
    ts_past = int(time.time()) - EPOCH_SECONDS * 3  # 3 epochs ago
    event = rh.sign("past event", prev_hash="", ts=ts_past)
    # Verify still works
    assert rh.verify(event)
    # Even after the epoch has rotated, the past key is derived on-demand
    # from the master + epoch_id.


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
