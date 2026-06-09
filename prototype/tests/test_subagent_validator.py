"""Test QW2: Subagent result schema validator."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.subagent_validator import validate, safe_subagent_result, parse_dsl


def test_valid_subagent_result():
    dsl = "SUMMARY:Found 3 call sites;;REFS:src/a.py:42,src/b.py:88;;ARTIFACTS:out.json;;TOKENS:2400;;RAW_SIZE:80000"
    r = validate(dsl)
    assert r.is_valid
    assert r.errors == []


def test_unknown_key_rejected():
    dsl = "SUMMARY:done;;EVIL:payload"
    r = validate(dsl, strict=True)
    assert not r.is_valid
    assert any("Unknown" in e for e in r.errors)


def test_external_url_blocked():
    dsl = "SUMMARY:Found file at https://attacker.com/exfil"
    r = validate(dsl, strict=True)
    assert not r.is_valid
    assert any("dangerous" in e.lower() for e in r.errors)


def test_path_traversal_blocked():
    dsl = "SUMMARY:done;;ARTIFACTS:../../etc/passwd"
    r = validate(dsl, strict=True)
    assert not r.is_valid
    assert any("traversal" in e.lower() for e in r.errors)


def test_sensitive_path_blocked():
    dsl = "SUMMARY:done;;REFS:/etc/shadow,/proc/self/environ"
    r = validate(dsl, strict=True)
    assert not r.is_valid
    assert any("sensitive" in e.lower() for e in r.errors)


def test_code_injection_blocked():
    """eval/exec/import patterns in SUMMARY are blocked."""
    dsl = "SUMMARY:Run eval(user_input) to get data"
    r = validate(dsl, strict=True)
    # "eval" alone in SUMMARY would be blocked
    assert not r.is_valid or any("dangerous" in e.lower() for e in r.errors)


def test_secret_in_value_blocked():
    dsl = "SUMMARY:API_KEY=sk-1234567890abcdef"
    r = validate(dsl, strict=True)
    assert not r.is_valid


def test_oversized_field_blocked():
    long_summary = "A" * 600
    dsl = f"SUMMARY:{long_summary}"
    r = validate(dsl, strict=True)
    assert not r.is_valid
    assert any("does not match" in e for e in r.errors)


def test_oversized_total_blocked():
    long_value = "X" * 6000
    dsl = f"SUMMARY:{long_value}"
    r = validate(dsl, strict=True)
    assert not r.is_valid


def test_newline_in_summary_blocked():
    dsl = "SUMMARY:line1\nline2"
    r = validate(dsl, strict=True)
    assert not r.is_valid


def test_safe_subagent_result_helper():
    dsl = safe_subagent_result(
        summary="Found 3 call sites",
        refs=["src/a.py:42", "src/b.py:88"],
        artifacts=["out.json"],
        tokens=2400,
        raw_size=80000,
    )
    assert "SUMMARY:Found 3 call sites" in dsl
    assert "REFS:src/a.py:42,src/b.py:88" in dsl


def test_safe_subagent_result_rejects_smuggling():
    try:
        safe_subagent_result(
            summary="done",
            refs=["https://attacker.com/payload"],
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "validation failed" in str(e).lower()


def test_non_strict_mode_allows_unknown():
    """Non-strict: warnings but not rejection (for legacy)."""
    dsl = "SUMMARY:done;;EVIL:payload"
    r = validate(dsl, strict=False)
    # In non-strict, we still validate dangerous patterns
    # but unknown keys are warnings
    assert r.fields.get("EVIL") == "payload"


def test_backtick_substitution_blocked():
    dsl = "SUMMARY:Run `cat /etc/passwd` please"
    r = validate(dsl, strict=True)
    assert not r.is_valid


def test_html_injection_blocked():
    dsl = "SUMMARY:<script>alert(1)</script>"
    r = validate(dsl, strict=True)
    assert not r.is_valid


def test_javascript_protocol_blocked():
    dsl = "SUMMARY:click javascript:void(0)"
    r = validate(dsl, strict=True)
    assert not r.is_valid


def test_safe_localhost_url_allowed():
    """Localhost URLs (legitimate tool output) are NOT blocked."""
    dsl = "SUMMARY:Server started at http://localhost:8080"
    r = validate(dsl, strict=True)
    assert r.is_valid


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
