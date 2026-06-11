"""
Tests for lib.llm_view.LLMViewBuilder — head/middle/tail layout.

v1.1.1 (HIGH-5): Brings llm_view.py coverage to 100% on the
add_budget_status() and add_gate_state() methods.
"""

import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAddBudgetStatus:
    def test_budget_status_no_state(self):
        """add_budget_status is a no-op when state is None."""
        from lib.llm_view import LLMViewBuilder

        builder = LLMViewBuilder(state=None, phase_id="P1", budget=4000)
        builder.add_budget_status()
        # No section added
        assert len(builder._sections) == 0

    def test_budget_status_with_real_state(self, tmp_path):
        """add_budget_status reads phase_total/phase_budget from StateDB."""
        from lib.llm_view import LLMViewBuilder
        from lib.state import StateDB

        state = StateDB(path=str(tmp_path / "state.db"))
        state.start_phase("P1", "default", "Test Phase", soft_cap=1000, hard_cap=2000)
        state.record_token("P1", "messages", "input", 500)
        state.record_token("P1", "output", "output", 200)

        builder = LLMViewBuilder(state=state, phase_id="P1", budget=4000)
        builder.add_budget_status()

        assert len(builder._sections) == 1
        section = builder._sections[0]
        assert section.label == "budget_status"
        assert section.priority == 1  # HEAD
        assert "Budget Status" in section.content
        assert "700" in section.content  # 500+200 total
        assert "P1" in section.content
        assert "35.0%" in section.content  # 700/2000

    def test_budget_status_handles_missing_phase(self, tmp_path):
        """add_budget_status gracefully shows 0/0 for missing phase."""
        from lib.llm_view import LLMViewBuilder
        from lib.state import StateDB

        state = StateDB(path=str(tmp_path / "state.db"))
        # No phase started
        builder = LLMViewBuilder(state=state, phase_id="MISSING", budget=4000)
        builder.add_budget_status()
        assert len(builder._sections) == 1
        content = builder._sections[0].content
        assert "0 / 0 tokens" in content
        assert "MISSING" in content


class TestAddGateState:
    def test_gate_state_pass_fail(self):
        """add_gate_state produces PASS/FAIL lines from gate results."""
        from lib.llm_view import LLMViewBuilder

        builder = LLMViewBuilder(phase_id="P1", budget=4000)
        builder.add_gate_state({
            "audit_chain": {"ok": True, "checked": 5},
            "schema_check": {"ok": False, "reason": "missing column"},
        })
        assert len(builder._sections) == 1
        content = builder._sections[0].content
        assert "Gate State" in content
        assert "audit_chain: PASS" in content
        assert "schema_check: FAIL" in content
        assert builder._sections[0].priority == 1  # HEAD

    def test_gate_state_empty_results(self):
        """add_gate_state with empty dict produces just header."""
        from lib.llm_view import LLMViewBuilder

        builder = LLMViewBuilder(phase_id="P1", budget=4000)
        builder.add_gate_state({})
        assert len(builder._sections) == 1
        assert "## Gate State" in builder._sections[0].content


class TestLayoutAndBuild:
    def test_head_middle_tail_layout(self, tmp_path):
        """Final view preserves head and tail order: head first, tail last."""
        from lib.llm_view import LLMViewBuilder
        from lib.state import StateDB

        state = StateDB(path=str(tmp_path / "state.db"))
        state.start_phase("P1", "default", "Test", soft_cap=1000, hard_cap=2000)
        state.record_token("P1", "messages", "input", 500)

        builder = LLMViewBuilder(state=state, phase_id="P1", budget=4000)
        builder.add_budget_status()                    # HEAD
        builder.add_gate_state({"g1": {"ok": True}})   # HEAD
        builder.add_adversarial_findings(["warn"])     # TAIL
        builder.add_recent_decisions(["d1"])           # TAIL
        view = builder.build()
        # Head appears before tail in the rendered view
        head_pos = view.find("Budget Status")
        tail_pos = view.find("Adversarial Findings")
        assert head_pos < tail_pos

    def test_section_report_zone_labels(self):
        """section_report labels sections by zone (head/middle/tail)."""
        from lib.llm_view import LLMViewBuilder

        builder = LLMViewBuilder(phase_id="P1", budget=4000)
        builder.add_constraints(["max 100 tokens"])     # HEAD
        builder.add_adversarial_findings(["warn"])      # TAIL
        report = builder.section_report()
        assert report["phase"] == "P1"
        assert report["budget"] == 4000
        zones = {s["zone"] for s in report["sections"]}
        assert "head" in zones
        assert "tail" in zones

    def test_invalid_priority_rejected(self):
        """add_section raises on priority != 1, 2, 3."""
        from lib.llm_view import LLMViewBuilder

        builder = LLMViewBuilder(phase_id="P1", budget=4000)
        with pytest.raises(ValueError, match="Priority must be"):
            builder.add_section("x", 5, "content")
        with pytest.raises(ValueError, match="Priority must be"):
            builder.add_section("x", 0, "content")

    def test_empty_view_returns_placeholder(self):
        """build() with no sections returns a placeholder string."""
        from lib.llm_view import LLMViewBuilder

        builder = LLMViewBuilder(phase_id="EMPTY", budget=4000)
        out = builder.build()
        assert "EMPTY" in out
        assert "no sections" in out
