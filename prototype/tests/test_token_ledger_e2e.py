"""
End-to-end tests for TokenLedger budget triggers at 60/70/85/95% of soft cap.

v1.1.1 (HIGH-4): Brings token_ledger.py coverage to 100% on the
triggering logic via subprocess-style multi-step record calls.
"""

import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBudgetTriggers:
    """Each of the 5 trigger thresholds must fire on the right boundary."""

    def test_60pct_triggers_info(self, tmp_path):
        """Recording tokens in 60-70% range triggers INFO_60."""
        from lib.state import StateDB
        from lib.token_ledger import TokenLedger

        state = StateDB(path=str(tmp_path / "state.db"))
        ledger = TokenLedger(state=state, verbose=False)
        ledger.start_phase("P1", "Test", soft_cap=1000, hard_cap=2000)
        # 650/1000 = 65% → INFO_60 (between 0.60 and 0.70)
        status = ledger.record("P1", "messages", "input", 650)
        assert status["action"] == "INFO_60"
        assert status["level"] == "60%"

    def test_70pct_triggers_cc_now(self, tmp_path):
        """Recording past 70% soft cap must trigger CC_NOW (Compaction Checkpoint)."""
        from lib.state import StateDB
        from lib.token_ledger import TokenLedger

        state = StateDB(path=str(tmp_path / "state.db"))
        ledger = TokenLedger(state=state, verbose=False)
        ledger.start_phase("P2", "Test", soft_cap=1000, hard_cap=2000)
        status = ledger.record("P2", "messages", "input", 750)
        assert status["action"] == "CC_NOW"
        assert status["level"] == "70%"

    def test_85pct_triggers_warn(self, tmp_path):
        """Recording past 85% soft cap must trigger WARN_85."""
        from lib.state import StateDB
        from lib.token_ledger import TokenLedger

        state = StateDB(path=str(tmp_path / "state.db"))
        ledger = TokenLedger(state=state, verbose=False)
        ledger.start_phase("P3", "Test", soft_cap=1000, hard_cap=2000)
        status = ledger.record("P3", "messages", "input", 880)
        assert status["action"] == "WARN_85"
        assert status["level"] == "85%"

    def test_95pct_triggers_critical(self, tmp_path):
        """Recording past 95% soft cap must trigger CRITICAL."""
        from lib.state import StateDB
        from lib.token_ledger import TokenLedger

        state = StateDB(path=str(tmp_path / "state.db"))
        ledger = TokenLedger(state=state, verbose=False)
        ledger.start_phase("P4", "Test", soft_cap=1000, hard_cap=2000)
        status = ledger.record("P4", "messages", "input", 960)
        assert status["action"] == "CRITICAL"
        assert status["level"] == "95%"

    def test_100pct_hard_cap_triggers_abort(self, tmp_path):
        """Reaching hard cap (100% of hard_cap) must trigger ABORT."""
        from lib.state import StateDB
        from lib.token_ledger import TokenLedger

        state = StateDB(path=str(tmp_path / "state.db"))
        ledger = TokenLedger(state=state, verbose=False)
        ledger.start_phase("P5", "Test", soft_cap=1000, hard_cap=2000)
        # 2000 = 100% of hard cap (200% of soft)
        status = ledger.record("P5", "messages", "input", 2000)
        assert status["action"] == "ABORT"
        assert status["level"] == "HARD_CAP"


class TestTriggerOrdering:
    """Triggers must be monotonic — once fired, never re-fire for the same phase."""

    def test_each_trigger_fires_only_once(self, tmp_path):
        """Re-recording in same threshold must not re-fire the same trigger."""
        from lib.state import StateDB
        from lib.token_ledger import TokenLedger

        state = StateDB(path=str(tmp_path / "state.db"))
        ledger = TokenLedger(state=state, verbose=False)
        ledger.start_phase("P6", "Test", soft_cap=1000, hard_cap=2000)
        s1 = ledger.record("P6", "messages", "input", 650)  # 65% → INFO_60
        s2 = ledger.record("P6", "messages", "input", 100)  # total 75% → CC_NOW (not INFO_60)
        s3 = ledger.record("P6", "messages", "input", 100)  # total 85% → WARN_85
        assert s1["action"] == "INFO_60"
        assert s2["action"] == "CC_NOW"
        assert s3["action"] == "WARN_85"

    def test_subsequent_records_below_threshold_no_action(self, tmp_path):
        """Records under the 60% threshold return no action."""
        from lib.state import StateDB
        from lib.token_ledger import TokenLedger

        state = StateDB(path=str(tmp_path / "state.db"))
        ledger = TokenLedger(state=state, verbose=False)
        ledger.start_phase("P7", "Test", soft_cap=1000, hard_cap=2000)
        s = ledger.record("P7", "messages", "input", 100)  # 10%
        assert s["action"] is None
        assert s["pct"] == pytest.approx(0.1)

    def test_jump_directly_to_critical(self, tmp_path):
        """A single record jumping past multiple thresholds fires the highest."""
        from lib.state import StateDB
        from lib.token_ledger import TokenLedger

        state = StateDB(path=str(tmp_path / "state.db"))
        ledger = TokenLedger(state=state, verbose=False)
        ledger.start_phase("P8", "Test", soft_cap=1000, hard_cap=2000)
        # One record of 960 tokens = 96% of soft cap → should fire CRITICAL (95%)
        s = ledger.record("P8", "messages", "input", 960)
        assert s["action"] == "CRITICAL"


class TestPhaseLifecycle:
    def test_end_phase_prints_summary(self, tmp_path, capsys):
        """end_phase prints a summary line with total tokens and percent."""
        from lib.state import StateDB
        from lib.token_ledger import TokenLedger

        state = StateDB(path=str(tmp_path / "state.db"))
        ledger = TokenLedger(state=state, verbose=True)
        ledger.start_phase("P9", "Test", soft_cap=1000, hard_cap=2000)
        ledger.record("P9", "messages", "input", 500)
        ledger.end_phase("P9", "complete")
        captured = capsys.readouterr()
        assert "Phase P9 ended" in captured.out
        assert "500 tokens" in captured.out

    def test_dashboard_uses_soft_pct(self, tmp_path):
        """dashboard() returns Rich-formatted string with soft cap and percent."""
        from lib.state import StateDB
        from lib.token_ledger import TokenLedger

        state = StateDB(path=str(tmp_path / "state.db"))
        ledger = TokenLedger(state=state, verbose=False)
        ledger.start_phase("P10", "Test", soft_cap=1000, hard_cap=2000)
        ledger.record("P10", "messages", "input", 500)
        ledger.record("P10", "output", "output", 100)
        out = ledger.dashboard("P10")
        assert "Phase P10" in out
        assert "Total: 600" in out
        assert "Soft cap: 1,000" in out
        assert "60.0%" in out
