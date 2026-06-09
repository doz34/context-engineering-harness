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


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
