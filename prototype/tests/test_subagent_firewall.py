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
    """verify_isolation inspects the ledger rather than returning a stub."""
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)
        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        fw = SubagentFirewall(ledger, "p1")

        # (1) No spawn happened → audit fails cleanly (not a stub)
        no_spawn = fw.verify_isolation("sub_never_spawned")
        assert no_spawn["is_valid"] is False
        assert "no spawn ledger entry" in no_spawn["reason"]

        # (2) Spawn a subagent, then verify → audit passes
        from lib.subagent_firewall import SubagentBrief
        brief = SubagentBrief(OBJECT="audit me", FORMAT="text",
                              TOOLS="grep", BOUND="in-scope")
        fw.spawn(brief)
        spawn_id = f"p1_sub_1"
        audit = fw.verify_isolation(spawn_id)
        assert audit["is_valid"] is True
        assert audit["parent_context_visible"] is False
        assert audit["return_summary_only"] is True
        assert "spawn_recorded_at" in audit


def test_last_sub_id_exposed():
    """CRIT fix 2026-06-10: last_sub_id is exposed after spawn so the
    CLI demo no longer hard-codes 'sub_1' and prints is_valid: False."""
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)
        ledger.start_phase("p1", "Test", soft_cap=1000, hard_cap=2000)
        fw = SubagentFirewall(ledger, "p1")

        # Before any spawn, last_sub_id is None
        assert fw.last_sub_id is None

        brief = SubagentBrief(OBJECT="x", FORMAT="text",
                              TOOLS="grep", BOUND="in-scope")
        result = fw.spawn(brief)

        # After spawn, last_sub_id is the real spawn id
        assert fw.last_sub_id is not None
        assert fw.last_sub_id.startswith("p1_sub_")
        # And the audit against this id is valid
        audit = fw.verify_isolation(fw.last_sub_id)
        assert audit["is_valid"] is True
        assert audit["subagent_id"] == fw.last_sub_id

        # Increment: a second spawn yields a new sub_id
        first = fw.last_sub_id
        fw.spawn(brief)
        assert fw.last_sub_id != first
        assert fw.last_sub_id.endswith("_sub_2")


def test_demo_sub_id_matches():
    """End-to-end test for the demo sub_id bug (CRIT fix 2026-06-10).

    Simulates what `bin/ctxh spawn` does: spawn, then verify_isolation
    using firewall.last_sub_id (NOT a hard-coded 'sub_1'). The audit
    must show is_valid: True. Before the fix, the audit printed
    `is_valid: False` because the hard-coded 'sub_1' didn't match the
    real spawn id format `{phase_id}_sub_{N}`.
    """
    with tempfile.TemporaryDirectory() as d:
        db = StateDB(path=os.path.join(d, "test.db"))
        ledger = TokenLedger(state=db, verbose=False)
        ledger.start_phase("P_DEMO", "Demo", soft_cap=1000, hard_cap=2000)
        fw = SubagentFirewall(ledger, "P_DEMO")

        brief = SubagentBrief(OBJECT="demo", FORMAT="text",
                              TOOLS="grep", BOUND="in-scope")
        fw.spawn(brief)

        # What the CLI does (after fix):
        audit = fw.verify_isolation(fw.last_sub_id)
        assert audit["is_valid"] is True, (
            f"Demo audit failed: is_valid={audit.get('is_valid')} "
            f"reason={audit.get('reason')}"
        )

        # What the CLI did BEFORE the fix (regression guard):
        bad_audit = fw.verify_isolation("sub_1")
        assert bad_audit["is_valid"] is False
        assert "no spawn ledger entry" in bad_audit["reason"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
