"""Tests for Context Failure Mode Detector."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from failure_detector import ContextFailureDetector, Finding, Severity


# -- distraction -------------------------------------------------------------

def test_distraction_detects_repeated_actions():
    det = ContextFailureDetector()
    for _ in range(5):
        det.record_action("tool_call", "search_files(pattern='TODO')")
    result = det.detect_distraction()
    assert result is not None
    assert result.mode == "distraction"
    assert result.severity in (Severity.MED, Severity.HIGH, Severity.CRIT)
    assert "5x" in result.detail or "Repeated" in result.detail


def test_distraction_clean_when_varied():
    det = ContextFailureDetector()
    det.record_action("tool_call", "search_files(pattern='TODO')")
    det.record_action("edit", "Fixed the bug in parser")
    det.record_action("read", "src/main.py")
    result = det.detect_distraction()
    assert result is None


# -- poisoning ---------------------------------------------------------------

def test_poisoning_detects_unreferenced_elements():
    det = ContextFailureDetector()
    det.record_action("tool_call", "search_files(pattern='config')")
    det.record_action("output", "Found legacy_database reference")
    det.record_action("output", "Found legacy_database again")
    result = det.detect_poisoning(context_elements=["config", "parser", "main"])
    assert result is not None
    assert result.mode == "poisoning"
    assert "legacy_database" in result.evidence.get("ghost_elements", [])


def test_poisoning_clean_when_all_referenced():
    det = ContextFailureDetector()
    det.record_action("tool_call", "search_files(pattern='config')")
    det.record_action("output", "Working with config and parser")
    result = det.detect_poisoning(context_elements=["config", "parser"])
    assert result is None


# -- clash -------------------------------------------------------------------

def test_clash_detects_contradictions():
    det = ContextFailureDetector()
    instructions = [
        "Always use tabs for indentation",
        "Never use tabs for indentation",
        "Do validate all inputs",
        "Don't validate all inputs",
    ]
    result = det.detect_clash(instructions)
    assert result is not None
    assert result.mode == "clash"
    assert len(result.evidence["clashes"]) >= 2


# -- instruction fade --------------------------------------------------------

def test_instruction_fade_measures_drift():
    det = ContextFailureDetector()
    baseline = "You must follow strict security policies and validate all user inputs"
    current = "Follow some policies and check inputs when possible"
    result = det.detect_instruction_fade(baseline, current)
    assert result is not None
    assert result.mode == "instruction_fade"
    assert result.evidence["retention"] < 1.0


# -- context rot -------------------------------------------------------------

def test_context_rot_estimates_risk():
    det = ContextFailureDetector()
    # Within normal range — no finding
    result = det.detect_context_rot(turn_count=15, context_size=10000)
    assert result is None

    # Beyond thresholds — elevated risk
    result = det.detect_context_rot(turn_count=40, context_size=25000)
    assert result is not None
    assert result.mode == "context_rot"
    assert result.evidence["risk_score"] >= 0.3

    # Severe rot
    result = det.detect_context_rot(turn_count=60, context_size=50000, accuracy_hint=0.6)
    assert result is not None
    assert result.severity == Severity.CRIT


# -- run_all -----------------------------------------------------------------

def test_run_all_returns_structured_findings():
    det = ContextFailureDetector()
    for _ in range(4):
        det.record_action("tool_call", "search_files(pattern='TODO')")

    result = det.run_all_checks(
        baseline_instructions="Be secure and validate inputs strictly always",
        context_elements=["config", "parser"],
        instructions=["Do validate all inputs", "Don't validate all inputs"],
        turn_count=45,
        context_size=25000,
    )

    assert isinstance(result, dict)
    assert "findings" in result
    assert "total" in result
    assert "has_critical" in result
    assert result["total"] >= 1

    for f in result["findings"]:
        assert "mode" in f
        assert "severity" in f
        assert f["severity"] in ("LOW", "MED", "HIGH", "CRIT")


if __name__ == "__main__":
    test_distraction_detects_repeated_actions()
    test_distraction_clean_when_varied()
    test_poisoning_detects_unreferenced_elements()
    test_poisoning_clean_when_all_referenced()
    test_clash_detects_contradictions()
    test_instruction_fade_measures_drift()
    test_context_rot_estimates_risk()
    test_run_all_returns_structured_findings()
    print("All 8 tests passed.")
