"""Test Hooks System (Fix 1)."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.hooks import (
    HookSystem, HookContext, HookEvent, HookDecision,
    pre_tool_use_block_destructive, pre_tool_use_check_budget,
    post_tool_use_clear_result, post_tool_use_summarize_swallowed,
)


def test_block_destructive_rm_rf():
    """rm -rf at root is blocked."""
    ctx = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        payload={},
        tool_name="Bash",
        tool_args={"command": "rm -rf /etc"},
    )
    r = pre_tool_use_block_destructive(ctx)
    assert r.decision == HookDecision.DENY
    assert "destructive" in r.reason.lower()


def test_block_destructive_git_force_push():
    """git push --force is blocked."""
    ctx = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        payload={},
        tool_name="Bash",
        tool_args={"command": "git push --force origin main"},
    )
    r = pre_tool_use_block_destructive(ctx)
    assert r.decision == HookDecision.DENY


def test_block_drop_table():
    """DROP TABLE is blocked."""
    ctx = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        payload={},
        tool_name="Bash",
        tool_args={"command": "psql -c 'DROP TABLE users'"},
    )
    r = pre_tool_use_block_destructive(ctx)
    assert r.decision == HookDecision.DENY


def test_allow_safe_command():
    """Normal commands are allowed."""
    ctx = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        payload={},
        tool_name="Bash",
        tool_args={"command": "ls -la"},
    )
    r = pre_tool_use_block_destructive(ctx)
    assert r.decision == HookDecision.ALLOW
    assert r.silent is True


def test_budget_check_blocks_when_exhausted():
    """No budget = block tool call."""
    ctx = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        payload={"budget_remaining": 0},
        tool_name="Bash",
        tool_args={"command": "ls"},
    )
    r = pre_tool_use_check_budget(ctx)
    assert r.decision == HookDecision.DENY


def test_budget_check_allows_when_available():
    """Budget remaining = allow."""
    ctx = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        payload={"budget_remaining": 1000},
        tool_name="Bash",
        tool_args={"command": "ls"},
    )
    r = pre_tool_use_check_budget(ctx)
    assert r.decision == HookDecision.ALLOW


def test_clear_large_tool_result():
    """Large tool result is cleared, head/tail kept."""
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        os.makedirs(".ctxh/tool_results", exist_ok=True)

        # Build a 1000+ char result where HEADMARKER is in the first 200
        # and TAILMARKER is fully in the last 200 chars.
        # TAILMARKER = 10 chars, must be substring of r[-200:].
        # Math: TAILMARKER must start at position p where 800 <= p <= 990.
        # Choose p = 990 (TAILMARKER at the very end). middle_pad = 990 - 213 = 777.
        # Total = 10+190+13+777+10+0 = 1000. TAILMARKER at 990, r[-200:] = [800-999]. ✓
        large_result = "HEADMARKER" + "X" * 190 + "MIDDLE_HIDDEN" + "Z" * 777 + "TAILMARKER"
        assert len(large_result) >= 1000, f"got {len(large_result)}"
        ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            payload={},
            tool_name="Grep",
            tool_result=large_result,
            timestamp="20260608T220000",
        )
        r = post_tool_use_clear_result(ctx)
        assert r.decision == HookDecision.CLEAR
        assert r.modified_payload is not None
        cleared = r.modified_payload["tool_result"]
        assert "CLEARED" in cleared
        assert "MIDDLE_HIDDEN" not in cleared  # Middle is offloaded
        # Head (first 200 chars) preserved — includes HEADMARKER
        assert "HEADMARKER" in cleared
        # Tail (last 200 chars) preserved — includes TAILMARKER
        assert "TAILMARKER" in cleared


def test_keep_small_tool_result():
    """Small tool results are not cleared."""
    ctx = HookContext(
        event=HookEvent.POST_TOOL_USE,
        payload={},
        tool_name="Read",
        tool_result="short result",
    )
    r = post_tool_use_clear_result(ctx)
    assert r.decision == HookDecision.ALLOW


def test_swallow_passing_results():
    """Passing test results are swallowed (silent)."""
    for pattern_result in [
        "All 5 tests passed",
        "OK (12 tests)",
        "No issues found",
        "0 errors, 0 warnings",
        "Lint: clean",
        "Build successful",
    ]:
        ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            payload={},
            tool_name="Test",
            tool_result=pattern_result,
        )
        r = post_tool_use_summarize_swallowed(ctx)
        assert r.decision == HookDecision.CLEAR, f"Should swallow: {pattern_result}"


def test_verbose_for_failures():
    """Failures are NOT swallowed."""
    ctx = HookContext(
        event=HookEvent.POST_TOOL_USE,
        payload={},
        tool_name="Test",
        tool_result="3 tests FAILED:\ntest_x\ntest_y\ntest_z",
    )
    r = post_tool_use_summarize_swallowed(ctx)
    assert r.decision == HookDecision.ALLOW
    assert r.silent is False


def test_hook_system_orchestration():
    """HookSystem chains handlers, DENY wins (short-circuits)."""
    hs = HookSystem()
    ctx = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        payload={},
        tool_name="Bash",
        tool_args={"command": "rm -rf /"},
    )
    r = hs.fire(ctx)
    assert r.decision == HookDecision.DENY
    # First hook DENIED, so subsequent hooks short-circuit
    assert len(hs.executed) == 1
    assert hs.executed[0]["handler"] == "pre_tool_use_block_destructive"


def test_hook_system_orchestration_allows_all():
    """When no hook denies, all hooks are executed."""
    hs = HookSystem()
    ctx = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        payload={"budget_remaining": 1000},
        tool_name="Bash",
        tool_args={"command": "ls"},
    )
    r = hs.fire(ctx)
    assert r.decision == HookDecision.ALLOW
    # All 3 hooks run
    assert len(hs.executed) == 3


def test_hook_system_audit_report():
    """Audit report is generated."""
    hs = HookSystem()
    ctx = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        payload={"budget_remaining": 1000},
        tool_name="Bash",
        tool_args={"command": "ls"},
    )
    hs.fire(ctx)
    report = hs.audit_report()
    assert "Hook audit" in report
    assert "ALLOW" in report


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
