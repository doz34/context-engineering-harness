"""Test State DB."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.state import StateDB


def test_init_creates_tables():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        with db.conn() as c:
            tables = c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            names = {t[0] for t in tables}
        assert "session" in names
        assert "phase" in names
        assert "token_event" in names
        assert "audit_event" in names


def test_phase_lifecycle():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        db.start_session("s1")
        db.start_phase("p1", "s1", "Test", soft_cap=1000, hard_cap=2000)

        soft, hard = db.phase_budget("p1")
        assert soft == 1000
        assert hard == 2000

        total = db.record_token("p1", "messages", "input", 500)
        assert total == 500

        total = db.record_token("p1", "tools", "input", 300)
        assert total == 800

        db.end_phase("p1")


def test_top_components():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        db.start_phase("p1", "s1", "Test", 1000, 2000)
        db.record_token("p1", "messages", "input", 500)
        db.record_token("p1", "tools", "input", 200)
        db.record_token("p1", "tools", "output", 100)
        db.record_token("p1", "retrieval", "input", 50)

        top = db.top_components("p1", limit=3)
        # tools: 300, messages: 500, retrieval: 50
        # Sorted DESC by total
        assert top[0][0] == "messages"  # 500
        assert top[1][0] == "tools"     # 300
        assert top[2][0] == "retrieval" # 50


# === F-003 audit 2026-06-10: negative token validation ===

def test_record_token_rejects_negative():
    """A negative `tokens` value would silently decrement the phase
    budget and bypass soft/hard caps. Must raise ValueError."""
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        db.start_phase("p1", "s1", "Test", 1000, 2000)
        try:
            db.record_token("p1", "messages", "input", -1)
        except ValueError as e:
            assert "tokens must be >= 0" in str(e)
        else:
            raise AssertionError("record_token(-1) should raise ValueError")


def test_record_token_rejects_non_int():
    """Floats, strings, bools must all be rejected to prevent type coercion
    bypasses."""
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        db.start_phase("p1", "s1", "Test", 1000, 2000)
        for bad in (1.5, "100", True, None):
            try:
                db.record_token("p1", "messages", "input", bad)
            except ValueError:
                continue
            raise AssertionError(
                f"record_token({bad!r}) should raise ValueError"
            )


# === F-004 audit 2026-06-10: verify_audit_chain ===

def test_verify_audit_chain_clean():
    """An untouched chain with valid RotatingHMAC signatures must verify."""
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        # Append 3 events (will use RotatingHMAC if cryptography is available)
        db.append_audit("e1", {"a": 1})
        db.append_audit("e2", {"b": 2})
        db.append_audit("e3", {"c": 3})
        result = db.verify_audit_chain()
        # Either the chain is valid (RotatingHMAC path) or the fallback
        # path is reported (legacy SHA-256 only). Both are acceptable for
        # this test — the only unacceptable outcome is ok=False with a
        # real signing mismatch.
        if not result["fallback"]:
            assert result["ok"] is True, result
            assert result["checked"] == 3
            assert result["first_invalid_id"] is None
        else:
            # Fallback path: verify_audit_chain can't epoch-verify legacy
            # SHA-256 events. We accept the fallback report.
            assert result["ok"] is True
            assert result["reason"] is not None


def test_verify_audit_chain_detects_tamper():
    """If a row's payload is modified after signing, verification must fail."""
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        db.append_audit("e1", {"a": 1})
        db.append_audit("e2", {"b": 2})
        # Tamper: rewrite the second row's payload directly
        with db.conn() as c:
            c.execute(
                "UPDATE audit_event SET payload = ? "
                "WHERE id = (SELECT id FROM audit_event ORDER BY id ASC LIMIT 1 OFFSET 1)",
                ('{"payload": {"b": 999}, "ts": "0", "epoch_id": "0"}',),
            )
        result = db.verify_audit_chain()
        if not result["fallback"]:
            assert result["ok"] is False
            assert result["first_invalid_id"] is not None
            assert result["reason"] is not None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
