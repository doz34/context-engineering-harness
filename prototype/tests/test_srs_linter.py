"""Test QW3: SRS Linter."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.srs_linter import lint_srs, find_acceptance_criteria, check_measurability, SAMPLE_SRS_GOOD, SAMPLE_SRS_BAD


def test_lint_good_srs():
    r = lint_srs(SAMPLE_SRS_GOOD)
    assert r["verdict"] == "PASS"
    assert r["measurable_count"] == r["total_acs"]


def test_lint_bad_srs():
    r = lint_srs(SAMPLE_SRS_BAD)
    assert r["verdict"] == "FAIL"
    assert r["measurable_count"] < r["total_acs"]


def test_no_acs_detected_fails():
    r = lint_srs("This document has no acceptance criteria at all.")
    assert r["verdict"] == "FAIL"
    assert any("No acceptance criteria" in i.issues[0] for i in r["issues"])


def test_vague_words_detected():
    issues, suggestions = check_measurability("The system should be fast and user-friendly.")
    assert len(issues) > 0
    assert any("vague" in i.lower() for i in issues)


def test_specific_metric_passes():
    issues, _ = check_measurability("The system shall respond in < 200ms at p99.")
    assert issues == []


def test_http_status_code_recognized():
    issues, _ = check_measurability("The API shall return HTTP 200 on success.")
    assert issues == []


def test_https_status_code_with_text():
    issues, _ = check_measurability("On invalid input, the system shall return HTTP 400.")
    assert issues == []


def test_shall_language_required():
    """Missing 'shall/must/will' is flagged."""
    issues, _ = check_measurability("The response time is < 100ms with 99% success.")
    assert any("shall" in i.lower() or "must" in i.lower() for i in issues)


def test_find_acs_ac_dash_format():
    text = "AC-1: First requirement\nAC-2: Second requirement\nAC-3: Third requirement"
    acs = find_acceptance_criteria(text)
    ids = [a[0] for a in acs]
    assert "AC-1" in ids or "AC1" in ids  # Format variation
    assert "AC-2" in ids
    assert "AC-3" in ids


def test_find_acs_gherkin():
    text = """
    Given a user is logged in
    When they click logout
    Then the session should be cleared within 50ms
    """
    acs = find_acceptance_criteria(text)
    assert any("Given" in a[1] for a in acs)


def test_find_acs_empty():
    acs = find_acceptance_criteria("No criteria here at all.")
    assert acs == []


def test_percentage_metric_recognized():
    issues, _ = check_measurability("Error rate shall be < 0.1% over 24h.")
    assert issues == []


def test_throughput_metric_recognized():
    issues, _ = check_measurability("The system shall handle 10000 req/s.")
    assert issues == []


def test_standards_reference_recognized():
    issues, _ = check_measurability("The API shall be JSON Schema v1.0 compliant.")
    assert issues == []


def test_open_ended_etc_flagged():
    issues, _ = check_measurability("The system shall handle errors etc.")
    assert any("etc" in i.lower() for i in issues)


def test_vague_quantifier_flagged():
    issues, _ = check_measurability("Most users should be happy.")
    assert any("vague" in i.lower() or "some" in i.lower() for i in issues)


def test_ac_with_version_recognized():
    issues, _ = check_measurability("The system shall conform to RFC 7231 (HTTP 1.1).")
    assert issues == []


def test_lint_mixed_srs():
    """Mix of good and bad ACs gives WARN verdict."""
    srs = """
    AC-1: System shall respond in < 200ms.
    AC-2: It should be fast.
    AC-3: The system shall support 1000 users.
    AC-4: The app should be good and simple.
    """
    r = lint_srs(srs)
    # 2/4 measurable = 50% → FAIL
    assert r["verdict"] == "FAIL"
    assert r["measurable_count"] == 2
    assert r["total_acs"] == 4


def test_lint_all_measurable_passes():
    srs = """
    AC-1: System shall respond in < 200ms.
    AC-2: System shall support 1000 concurrent users.
    AC-3: System shall return HTTP 200 on success.
    AC-4: System shall hash passwords with SHA-256.
    AC-5: System shall return errors as JSON Schema v1.0.
    """
    r = lint_srs(srs)
    assert r["verdict"] == "PASS"
    assert r["pct_measurable"] == 100


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
