"""Test Subagent Firewall."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.state import StateDB
from lib.token_ledger import TokenLedger
from lib.subagent_firewall import SubagentFirewall, SubagentBrief, SubagentResult


def test_brief_from_dsl():
    dsl = "OBJECT:Find X;;FORMAT:JSON;;TOOLS:grep,read;;BOUND:max 10"
    brief = SubagentBrief.from_dsl(dsl)
    assert brief.OBJECT == "Find X"
    assert brief.FORMAT == "JSON"
    assert brief.TOOLS == ["grep", "read"]
    assert brief.BOUND == "max 10"


def test_brief_to_dsl_roundtrip():
    brief = SubagentBrief(
        OBJECT="Find X",
        FORMAT="JSON",
        TOOLS=["grep", "read"],
        BOUND="max 10",
    )
    dsl = brief.to_dsl()
    parsed = SubagentBrief.from_dsl(dsl)
    assert parsed.OBJECT == brief.OBJECT
    assert parsed.FORMAT == brief.FORMAT
    assert parsed.TOOLS == brief.TOOLS


def test_brief_validation():
    brief = SubagentBrief(OBJECT="", FORMAT="JSON", TOOLS=["grep"], BOUND="max 10")
    valid, errors = brief.validate()
    assert valid is False
    assert any("OBJECT" in e for e in errors)


def test_spawn_isolated():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)
        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        fw = SubagentFirewall(ledger, "p1")

        brief = SubagentBrief(
            OBJECT="Find parse_query call sites",
            FORMAT="JSON: {file:str, line:int}[]",
            TOOLS=["grep", "read"],
            BOUND="max 20 results",
        )

        # Stub executor that returns a known result
        def stub_execute(brief, sub_id, model, budget):
            return SubagentResult(
                summary="Found 3 call sites",
                refs=["src/a.py:42", "src/b.py:88", "src/c.py:120"],
                artifacts=[".ctxh/subagents/sub_1/out.json"],
                tokens_used=2400,
                raw_size=80000,
            )

        result = fw.spawn(brief, context_budget=4000, model="claude-sonnet-4-5",
                         execute_fn=stub_execute)

        # Return contract: summary + refs + artifacts
        assert result.summary == "Found 3 call sites"
        assert len(result.refs) == 3
        assert result.tokens_used == 2400
        assert result.raw_size == 80000

        # Compression ratio
        assert result.compression_ratio() > 20  # 80000/2400 ≈ 33x


def test_spawn_rejects_invalid_brief():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)
        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        fw = SubagentFirewall(ledger, "p1")

        bad_brief = SubagentBrief(OBJECT="", FORMAT="", TOOLS=[], BOUND="")

        try:
            fw.spawn(bad_brief)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid brief" in str(e)


def test_isolation_audit():
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)
        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        fw = SubagentFirewall(ledger, "p1")

        audit = fw.verify_isolation("sub_1")
        assert audit["parent_context_visible"] is False
        assert audit["return_summary_only"] is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
