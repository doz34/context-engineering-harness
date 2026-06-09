"""Test Token Ledger triggers."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.state import StateDB
from lib.token_ledger import TokenLedger


def test_start_and_record():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)

        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        status = ledger.record("p1", "messages", "input", 500)
        assert status["action"] is None  # 50% < 60%


def test_trigger_at_60_percent():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)

        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        # 600 tokens = 60%
        status = ledger.record("p1", "messages", "input", 600)
        assert status["action"] == "INFO_60"


def test_trigger_at_70_percent_cc():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)

        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        # 700 tokens = 70% → CC_NOW
        status = ledger.record("p1", "messages", "input", 700)
        assert status["action"] == "CC_NOW"
        assert "Compaction" in status["message"]


def test_trigger_at_95_percent_critical():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)

        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        # 950 tokens = 95%
        status = ledger.record("p1", "messages", "input", 950)
        assert status["action"] == "CRITICAL"


def test_trigger_at_hard_cap_abort():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)

        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        # 2000 tokens = 100% of hard cap → ABORT
        status = ledger.record("p1", "messages", "input", 2000)
        assert status["action"] == "ABORT"


def test_trigger_fires_only_once():
    """A trigger at 70% should not re-fire on subsequent calls."""
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)

        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        s1 = ledger.record("p1", "messages", "input", 700)  # First 70%
        assert s1["action"] == "CC_NOW"

        s2 = ledger.record("p1", "messages", "input", 100)  # Now 80%
        # Should NOT re-fire CC_NOW, should fire WARN_85 maybe
        # (depends on threshold ordering)
        assert s2["action"] != "CC_NOW"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
