"""
CE-Harness DSL Parser
=====================
Format: KEY:VALUE;;KEY:VALUE;;KEY:VALUE
Inspired by swebok-v4-harness DSL.
"""

from typing import Dict, Optional
import re


def parse(line: str) -> Dict[str, str]:
    """
    Parse a single line of KEY:VALUE;;KEY:VALUE format.

    >>> parse("VERDICT:PASS;;RATIONALE:all good")
    {'VERDICT': 'PASS', 'RATIONALE': 'all good'}
    """
    if not line or "::" not in line and ":" not in line:
        return {}

    pairs = line.split(";;")
    result = {}
    for p in pairs:
        if ":" not in p:
            continue
        k, v = p.split(":", 1)
        result[k.strip()] = v.strip()
    return result


def parse_multi(text: str) -> Dict[str, str]:
    """Parse multi-line DSL text into merged dict (last wins)."""
    result = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        result.update(parse(line))
    return result


def emit(d: Dict[str, str]) -> str:
    """Emit a dict as DSL line."""
    return ";;".join(f"{k}:{v}" for k, v in d.items())


def validate_brief(brief: Dict[str, str]) -> tuple[bool, list[str]]:
    """
    Validate a subagent brief against the 4-champs rule.
    Required: OBJECT, FORMAT, TOOLS, BOUND.
    """
    required = ["OBJECT", "FORMAT", "TOOLS", "BOUND"]
    errors = []
    for r in required:
        if r not in brief or not brief[r]:
            errors.append(f"Missing required field: {r}")
    return (len(errors) == 0, errors)


if __name__ == "__main__":
    import doctest
    doctest.testmod(verbose=True)
