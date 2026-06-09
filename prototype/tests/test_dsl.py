"""Test DSL parser."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.dsl import parse, parse_multi, emit, validate_brief


def test_parse_simple():
    result = parse("KEY:value")
    assert result == {"KEY": "value"}


def test_parse_multiple():
    result = parse("KEY1:v1;;KEY2:v2;;KEY3:v3")
    assert result == {"KEY1": "v1", "KEY2": "v2", "KEY3": "v3"}


def test_parse_strips_whitespace():
    result = parse("  KEY : value  ;;  KEY2 : v2  ")
    assert result == {"KEY": "value", "KEY2": "v2"}


def test_parse_multi_lines():
    text = """
    KEY1: v1
    # comment line (ignored)
    KEY2: v2
    """
    result = parse_multi(text)
    assert result == {"KEY1": "v1", "KEY2": "v2"}


def test_emit_roundtrip():
    d = {"A": "1", "B": "2"}
    line = emit(d)
    assert parse(line) == d


def test_validate_brief_valid():
    valid, errors = validate_brief({
        "OBJECT": "Find X",
        "FORMAT": "JSON",
        "TOOLS": "grep,read",
        "BOUND": "max 10 results",
    })
    assert valid is True
    assert errors == []


def test_validate_brief_missing():
    valid, errors = validate_brief({"OBJECT": "Find X"})
    assert valid is False
    assert "FORMAT" in str(errors)
    assert "TOOLS" in str(errors)
    assert "BOUND" in str(errors)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
