"""
QW2 — Subagent Result Schema Validator
========================================
Strict validation of <subagent-result> return contract.
Closes: Subagent smuggling (return payload attacks).

Pattern: SUMMARY + REFS + ARTIFACTS only. No free payload.
Refuses: anything not in the strict schema. SMUGGLING BLOCKED.
"""

import re
from typing import Tuple, List, Optional
from dataclasses import dataclass


# Strict schema for <subagent-result>
ALLOWED_KEYS = {"SUMMARY", "REFS", "ARTIFACTS", "TOKENS", "RAW_SIZE"}

# Patterns: each value has a strict regex
PATTERNS = {
    "SUMMARY": re.compile(r'^[A-Za-z0-9 .,;:!?()\-/\'"]{0,500}$'),
    # REFS: comma-separated, each ref is "filepath:line" or URL
    "REFS": re.compile(r'^[A-Za-z0-9._/:\-,]{0,2000}$'),
    # ARTIFACTS: comma-separated paths (allow comma between entries)
    "ARTIFACTS": re.compile(r'^[A-Za-z0-9._/\-,]{0,2000}$'),
    # TOKENS: integer
    "TOKENS": re.compile(r'^\d{0,10}$'),
    "RAW_SIZE": re.compile(r'^\d{0,15}$'),
}

# Dangerous patterns that should NEVER appear in subagent return
# (anti-smuggling)
DANGEROUS_PATTERNS = [
    re.compile(r'https?://(?!localhost|127\.0\.0\.1)[^\s]+'),  # External URLs
    re.compile(r'<script', re.IGNORECASE),  # HTML
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'\$\([^)]*\)'),  # Shell command substitution
    re.compile(r'`[^`]+`'),  # Backticks
    re.compile(r'\b(eval|exec|import|os\.system|subprocess)\b'),  # Code injection
    re.compile(r'\b(password|api_key|secret|token)\s*[:=]\s*\S+', re.IGNORECASE),  # Secrets
]


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    cleaned_dsl: str
    fields: dict


def parse_dsl(line: str) -> dict:
    """Parse KEY:VALUE;;KEY:VALUE format."""
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


def emit_dsl(d: dict) -> str:
    """Emit dict as DSL line."""
    return ";;".join(f"{k}:{v}" for k, v in d.items())


def validate(dsl_line: str, strict: bool = True) -> ValidationResult:
    """
    Validate a <subagent-result> DSL line.
    Strict mode: refuse unknown keys, refuse oversized values,
    refuse dangerous patterns.
    """
    errors = []
    parsed = parse_dsl(dsl_line)

    if not parsed:
        return ValidationResult(
            is_valid=False,
            errors=["Empty or unparseable DSL"],
            cleaned_dsl="",
            fields={},
        )

    # Check unknown keys
    unknown = set(parsed.keys()) - ALLOWED_KEYS
    if unknown:
        errors.append(f"Unknown keys (potential smuggling): {sorted(unknown)}")
        if strict:
            return ValidationResult(
                is_valid=False,
                errors=errors,
                cleaned_dsl="",
                fields=parsed,
            )

    # Validate each field
    for key, value in parsed.items():
        if key in PATTERNS:
            if not PATTERNS[key].match(value):
                errors.append(f"Field {key} does not match expected pattern")

    # Anti-smuggling checks
    for key, value in parsed.items():
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(value):
                errors.append(f"Field {key} contains dangerous pattern: {pattern.pattern[:50]}")

    # REFS / ARTIFACTS: each entry must be a valid path
    for field_name in ("REFS", "ARTIFACTS"):
        if field_name in parsed and parsed[field_name]:
            entries = [e.strip() for e in parsed[field_name].split(",") if e.strip()]
            for entry in entries:
                if ".." in entry:
                    errors.append(f"Path traversal in {field_name}: {entry}")
                if entry.startswith("/etc/") or entry.startswith("/proc/") or entry.startswith("/sys/"):
                    errors.append(f"Sensitive path in {field_name}: {entry}")

    # SUMMARY: no newlines (DSL is single-line)
    if "SUMMARY" in parsed and ("\n" in parsed["SUMMARY"] or "\r" in parsed["SUMMARY"]):
        errors.append("SUMMARY contains newlines (must be single-line)")

    # Length checks
    for key, value in parsed.items():
        if len(value) > 5000:
            errors.append(f"Field {key} too long: {len(value)} chars (max 5000)")

    is_valid = len(errors) == 0
    cleaned = emit_dsl(parsed) if is_valid else ""

    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        cleaned_dsl=cleaned,
        fields=parsed,
    )


def safe_subagent_result(summary: str, refs: List[str] = None,
                         artifacts: List[str] = None,
                         tokens: int = 0, raw_size: int = 0) -> str:
    """
    Build a safe <subagent-result> DSL line, validated.
    Returns the DSL string, or raises ValueError on validation failure.
    """
    fields = {
        "SUMMARY": summary[:500],
        "REFS": ",".join(refs or [])[:2000],
        "ARTIFACTS": ",".join(artifacts or [])[:2000],
        "TOKENS": str(tokens)[:10],
        "RAW_SIZE": str(raw_size)[:15],
    }
    dsl = emit_dsl(fields)
    result = validate(dsl, strict=True)
    if not result.is_valid:
        raise ValueError(f"Subagent result validation failed: {result.errors}")
    return result.cleaned_dsl
