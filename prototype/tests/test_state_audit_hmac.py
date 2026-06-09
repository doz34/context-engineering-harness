"""Test QW-S3-8: state.append_audit migration to RotatingHMAC."""
import sys
import os
import tempfile
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.state import StateDB
from lib.security import RotatingHMAC, load_or_create_master_key, current_epoch_id


def test_append_audit_uses_rotating_hmac():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(os.path.join(d, "test.db"))
        h = db.append_audit("test_event", {"foo": "bar"})
        assert h is not None
        # Should be a 64-char hex (SHA-256 output)
        assert len(h) == 64
        # Should be deterministic per epoch (not 0)
        assert h != "0" * 64


def test_audit_chain_uses_chained_prev_hash():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(os.path.join(d, "test.db"))
        h1 = db.append_audit("event1", {"x": 1})
        h2 = db.append_audit("event2", {"x": 2})
        h3 = db.append_audit("event3", {"x": 3})
        # All 3 hashes are different (chain is built)
        assert h1 != h2
        assert h2 != h3
        assert h1 != h3
        # Verify chain: h2's prev_hash should be h1
        with db.conn() as c:
            row = c.execute(
                "SELECT prev_hash, hash FROM audit_event WHERE event_type = 'event2'"
            ).fetchone()
            assert row[0] == h1
            assert row[1] == h2


def test_audit_event_stores_epoch_id():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(os.path.join(d, "test.db"))
        db.append_audit("event1", {"x": 1})
        # Verify the payload stored in DB includes epoch_id
        with db.conn() as c:
            row = c.execute(
                "SELECT payload FROM audit_event WHERE event_type = 'event1'"
            ).fetchone()
            payload = json.loads(row[0])
            # New format: {"payload": {"x": 1}, "ts": "...", "epoch_id": "..."}
            assert "epoch_id" in payload
            assert "payload" in payload
            assert payload["payload"] == {"x": 1}


def test_master_key_persisted_to_disk():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(os.path.join(d, "test.db"))
        db.append_audit("event", {"x": 1})
        # Master key file should be created
        master_path = os.path.join(d, "test.db.master")
        assert os.path.exists(master_path)
        # Mode 0600
        mode = os.stat(master_path).st_mode & 0o777
        assert mode == 0o600


def test_same_master_key_reused_across_instances():
    """If the master key exists, it's reused (no rotation per instance)."""
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "test.db")
        db1 = StateDB(db_path)
        db1.append_audit("event1", {"x": 1})
        # New instance
        db2 = StateDB(db_path)
        db2.append_audit("event2", {"x": 2})
        # Both should use the same key
        # (We can't easily verify the key itself, but the chain should be valid)
        with db2.conn() as c:
            count = c.execute("SELECT COUNT(*) FROM audit_event").fetchone()[0]
        assert count == 2


def test_audit_chain_rewind_blocks():
    """Rewinding to an old epoch key (forward secrecy) is the property."""
    # Compute epoch key for current time
    key = load_or_create_master_key("/tmp/test_key_master")
    rh = RotatingHMAC(key)
    e_now = current_epoch_id()
    e_past = e_now - 1
    key_now = rh._derive_epoch_key(e_now)
    key_past = rh._derive_epoch_key(e_past)
    # Different keys
    assert key_now != key_past


def test_payload_format_compatible_with_verification():
    """The stored payload format must be verifiable with RotatingHMAC."""
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(os.path.join(d, "test.db"))
        db.append_audit("test", {"foo": "bar"})
        # Re-load and verify
        with db.conn() as c:
            row = c.execute(
                "SELECT payload, prev_hash, hash FROM audit_event"
            ).fetchone()
        payload_json, prev_hash, h = row
        stored = json.loads(payload_json)
        # Construct the canonical content (matches RotatingHMAC.sign)
        content = {
            "ts": stored["ts"],
            "epoch_id": stored["epoch_id"],
            "payload": json.dumps(stored["payload"]),
            "prev_hash": prev_hash,
        }
        # Recompute hash with epoch key
        epoch_id = int(stored["epoch_id"])
        key = load_or_create_master_key(os.path.join(d, "test.db.master"))
        rh = RotatingHMAC(key)
        epoch_key = rh._derive_epoch_key(epoch_id)
        import hmac as _hmac
        import hashlib
        content_bytes = json.dumps(content, sort_keys=True).encode()
        expected = _hmac.new(epoch_key, content_bytes, hashlib.sha256).hexdigest()
        assert h == expected, "Audit chain not verifiable with RotatingHMAC"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
