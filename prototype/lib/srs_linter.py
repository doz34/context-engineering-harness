"""
QW3 — SRS Linter
=================
Validates that Acceptance Criteria (AC) in a Software Requirements
Specification (SRS) are measurable. Refuses vague ACs.
Closes: Spec gaming (AC flous = n'importe quoi passe T2).
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass, field


# === UNMEASURABLE PATTERNS (red flags) ===
# An AC is UNMEASURABLE if it uses these words without quantification
UNMEASURABLE_HEDGES = [
    r'\b(should|may|might|maybe|perhaps|probably)\b',  # Hedge
    r'\b(fast|slow|good|bad|nice|simple|easy|intuitive|user-friendly)\b',  # Subjective
    r'\b(some|few|many|several|most)\b',  # Vague quantifier
    r'\b(etc|and so on|and more)\b',  # Open-ended
    r'\b(works|handles|supports|processes)\b(?!\s+(at least|at most|exactly))',  # Vague verb without metric
]

# Quantification patterns: should match measurable ACs
MEASURABLE_PATTERNS = [
    r'\b(<=?|>=?|==|!=|<>)\s*\d+',  # Comparison to number
    r'\d+\s*(ms|s|seconds?|minutes?|hours?|days?)\b',  # Time unit
    r'\d+\s*(MB|KB|GB|bytes?|KB/s|MB/s)\b',  # Storage/bandwidth
    r'\d+\s*(req/s|rps|qps|ops/s|throughput)\b',  # Throughput
    r'\b\d+%\b',  # Percentage
    r'\b\d+(\.\d+)?\s*(seconds?|ms|s)\b',  # Decimal time
    r'\b(returns|displays|logs|sends|emits)\b\s+\w+\s+(when|if|on|upon)',  # Action-on-condition
    r'\b(HTTP|REST|TCP|UDP|GET|POST|PUT|DELETE)\s+\d{3}',  # HTTP status code
    r'\b\d{3}\s+(OK|Bad|Error|Forbidden|Unauthorized|Not Found)',  # HTTP status
    r'\b(when|if)\s+.{1,80}\s+then\s+',  # When-then pattern
    r'\bexactly\s+\d+',  # Exact count
    r'\bwithin\s+\d+\s*(ms|s)',  # Within X time
    r'\b(at least|at most|no more than)\s+\d+',  # Bounded quantifier
    r'\b\d+(\.\d+)?%',  # Decimal percentage
    r'\bSHA-?256|MD5|AES-\d+|RSA-\d+|ECDSA',  # Crypto standards
    r'\b(JSON|XML|YAML|CSV|PDF)\s+(format|schema|spec)',  # Format spec
    r'\b(v[0-9]+\.[0-9]+\.[0-9]+|RFC\s*\d+)\b',  # Version/RFC reference
    r'\b\d{1,3}(,\d{3})+\s+(users?|requests?|concurrent|connections?|items?)\b',  # Large count
    r'\b\d+\s+(users?|requests?|concurrent|connections?|items?|calls?)\b',  # Plain count
]


@dataclass
class ACIssue:
    ac_id: str
    ac_text: str
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


def find_acceptance_criteria(text: str) -> List[Tuple[str, str]]:
    """
    Extract ACs from a SRS text. Returns list of (id, text).
    Supports multiple formats:
    - AC-1: text
    - AC1.1: text
    - ## Acceptance Criteria (markdown header)
    - Given/When/Then (Gherkin-like)
    """
    criteria = []

    # Pattern 1: "AC-N:" or "AC N:" or "AC.N:" (allow leading whitespace)
    for m in re.finditer(r'^\s*(AC[\-\s\.]?\d+(?:\.\d+)?)\s*[:\.\)]\s*(.+?)$',
                          text, re.MULTILINE):
        ac_id, ac_text = m.group(1).strip(), m.group(2).strip()
        if ac_text and len(ac_text) > 5:
            criteria.append((ac_id, ac_text))

    # Pattern 2: numbered list "1. ..."
    for m in re.finditer(r'^\s*(\d+)\.\s+(.{15,})$', text, re.MULTILINE):
        # Heuristic: if line contains typical AC words
        ac_id = f"AC-{m.group(1)}"
        ac_text = m.group(2).strip()
        if any(kw in ac_text.lower() for kw in ["shall", "must", "will", "should", "given", "when"]):
            if (ac_id, ac_text) not in criteria:
                criteria.append((ac_id, ac_text))

    # Pattern 3: Gherkin "Given/When/Then"
    gherkin_blocks = re.findall(
        r'(Given\s+.+?\s+When\s+.+?\s+Then\s+.+?)(?=\n\s*\n|\Z)',
        text, re.DOTALL | re.IGNORECASE
    )
    for i, block in enumerate(gherkin_blocks, 1):
        ac_id = f"AC-G{i}"
        if (ac_id, block.strip()) not in criteria:
            criteria.append((ac_id, block.strip()))

    return criteria


def check_measurability(ac_text: str) -> Tuple[List[str], List[str]]:
    """
    Check if an AC is measurable. Returns (issues, suggestions).
    """
    issues = []
    suggestions = []

    # Check length
    if len(ac_text) < 15:
        issues.append(f"AC too short ({len(ac_text)} chars) — vague")

    # Check unmeasurable hedges
    for pattern in UNMEASURABLE_HEDGES:
        if re.search(pattern, ac_text, re.IGNORECASE):
            issues.append(f"Contains vague language: {pattern}")
            suggestions.append(
                "Replace vague words with specific metrics (e.g., 'fast' → '< 100ms')"
            )

    # Check measurable patterns
    has_measurable = False
    for pattern in MEASURABLE_PATTERNS:
        if re.search(pattern, ac_text, re.IGNORECASE):
            has_measurable = True
            break

    if not has_measurable:
        issues.append("No measurable criteria found (no numbers, units, conditions)")
        suggestions.append(
            "Add a measurable metric: number + unit (e.g., 'response time < 200ms', "
            "'p99 latency', 'error rate < 0.1%', 'JSON Schema valid', 'HTTP 200')"
        )

    # Check for "shall" (IEEE 830 recommended)
    if not re.search(r'\b(shall|must|will)\b', ac_text, re.IGNORECASE):
        issues.append("Missing 'shall' / 'must' / 'will' (weak requirement language)")
        suggestions.append("Use 'shall' (IEEE 830 standard)")

    return issues, suggestions


def lint_srs(srs_text: str) -> dict:
    """
    Lint an SRS document. Returns:
    {
        "total_acs": int,
        "measurable_count": int,
        "issues": [ACIssue, ...],
        "verdict": "PASS" | "WARN" | "FAIL"
    }
    """
    acs = find_acceptance_criteria(srs_text)

    if not acs:
        return {
            "total_acs": 0,
            "measurable_count": 0,
            "issues": [ACIssue(ac_id="N/A", ac_text="(no ACs found)",
                               issues=["No acceptance criteria detected"])],
            "verdict": "FAIL",
        }

    issues = []
    measurable_count = 0

    for ac_id, ac_text in acs:
        ac_issues, suggestions = check_measurability(ac_text)
        if not ac_issues:
            measurable_count += 1
        else:
            issues.append(ACIssue(
                ac_id=ac_id, ac_text=ac_text,
                issues=ac_issues, suggestions=suggestions,
            ))

    total = len(acs)
    pct_measurable = (measurable_count / total * 100) if total else 0

    # Verdict
    if pct_measurable >= 90:
        verdict = "PASS"
    elif pct_measurable >= 70:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return {
        "total_acs": total,
        "measurable_count": measurable_count,
        "pct_measurable": pct_measurable,
        "issues": issues,
        "verdict": verdict,
    }


# Example usage
SAMPLE_SRS_GOOD = """
# SRS - User Management

## Acceptance Criteria

AC-1: The system shall respond to login requests in < 200ms at p99 latency.
AC-2: The system shall support 10,000 concurrent users with < 0.1% error rate.
AC-3: When a user submits invalid credentials, the system shall return HTTP 401.
AC-4: All passwords shall be hashed using SHA-256 before storage.
AC-5: The API shall return responses in JSON Schema v1.0 compliant format.
"""

SAMPLE_SRS_BAD = """
# SRS - Vague

## Acceptance Criteria

AC-1: The system should be fast and user-friendly.
AC-2: Login should probably work well for most users.
AC-3: The app should handle errors etc.
AC-4: The system is generally good.
"""
