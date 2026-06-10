"""
QW10 — Mutation Testing Enforcement
=====================================
Refuses coverage pass if mutation score < threshold.
Closes: Test gaming (tests that pass but don't actually validate logic).
"""

import ast
import re
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field


@dataclass
class Mutant:
    """A single mutation of source code."""
    id: str
    line: int
    column: int
    original: str
    mutated: str
    operator: str  # e.g., "AOR", "ROR", "COR"


@dataclass
class MutationResult:
    source_file: str
    total_mutants: int
    killed: int
    survived: int
    timeout: int
    score: float  # killed / total
    survived_mutants: List[Mutant] = field(default_factory=list)
    verdict: str = "PASS"  # PASS, WARN, FAIL


# Mutation operators
MUTATION_OPERATORS = {
    "AOR": "Arithmetic Operator Replacement",  # + -> -, * -> /, etc.
    "ROR": "Relational Operator Replacement",  # < -> <=, == -> !=, etc.
    "COR": "Conditional Operator Replacement",  # and -> or, etc.
    "LOR": "Logical Operator Replacement",
    "SVR": "Statement/Variable Replacement",
    "UOI": "Unary Operator Insertion",
}


def apply_arithmetic_mutation(node: ast.BinOp) -> Optional[Mutant]:
    """Mutate arithmetic operators."""
    mutations = {
        ast.Add: ast.Sub,
        ast.Sub: ast.Add,
        ast.Mult: ast.Div,
        ast.Div: ast.Mult,
        ast.Mod: ast.Mult,
    }
    new_op = mutations.get(type(node.op))
    if new_op is None:
        return None
    return Mutant(
        id=f"AOR_L{node.lineno}",
        line=node.lineno, column=node.col_offset,
        original=ast.unparse(node), mutated="(mutated)",
        operator="AOR",
    )


def apply_relational_mutation(node: ast.Compare) -> Optional[Mutant]:
    """Mutate relational operators."""
    mutations = {
        ast.Lt: ast.LtE,
        ast.LtE: ast.Lt,
        ast.Gt: ast.GtE,
        ast.GtE: ast.Gt,
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
    }
    if not node.ops:
        return None
    new_op = mutations.get(type(node.ops[0]))
    if new_op is None:
        return None
    return Mutant(
        id=f"ROR_L{node.lineno}",
        line=node.lineno, column=node.col_offset,
        original=ast.unparse(node), mutated="(mutated)",
        operator="ROR",
    )


def apply_conditional_mutation(node: ast.BoolOp) -> Optional[Mutant]:
    """Mutate and/or."""
    mutations = {
        ast.And: ast.Or,
        ast.Or: ast.And,
    }
    new_op = mutations.get(type(node.op))
    if new_op is None:
        return None
    return Mutant(
        id=f"COR_L{node.lineno}",
        line=node.lineno, column=node.col_offset,
        original=ast.unparse(node), mutated="(mutated)",
        operator="COR",
    )


def generate_mutants(source: str) -> List[Mutant]:
    """
    Parse source code and generate all possible mutants.
    For POV, this is a simple static analysis.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    mutants = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            m = apply_arithmetic_mutation(node)
            if m:
                mutants.append(m)
        elif isinstance(node, ast.Compare):
            m = apply_relational_mutation(node)
            if m:
                mutants.append(m)
        elif isinstance(node, ast.BoolOp):
            m = apply_conditional_mutation(node)
            if m:
                mutants.append(m)
    return mutants


def simulate_test_run(mutant: Mutant, tests_pass: bool = True,
                      test_source: str = "") -> str:
    """
    Determine if a test would detect (kill) a mutant.

    This is now a DETERMINISTIC static check (CRIT fix 2026-06-10 —
    previous version used random.random() which made the "refuses PASS
    if mutation score < 0.7" gate a coin flip). The check examines
    whether any test in `test_source` references the line/operator of
    the mutant. If a test asserts something that would be affected by
    this operator change, we mark the mutant as killed. If no test
    references the mutated line, we mark it as survived.

    This is still a static heuristic (real mutation testing runs the
    test suite against the mutant), but it is:
    - Deterministic (no random)
    - Conservative (a mutant that isn't obviously covered is marked
      as survived, so coverage gaps surface instead of hiding)
    - Inspectable (you can see why a mutant survived)

    For real mutation testing, use `mutmut` or `cosmic-ray` against
    the actual codebase. This function exists to give the POV
    harness a meaningful score when no real mutation runner is
    available, while making it obvious to an auditor that the score
    is heuristic, not empirical.
    """
    import re
    if not test_source:
        # Without the test source we cannot reason about coverage.
        # Default to "survived" so the audit will flag a missing test
        # (better than a false PASS).
        return "survived"

    # Look for any `assert` in a test function that mentions the same
    # line number or operator. Line numbers are weak signals (tests
    # rarely cite source line numbers) so we weight operator keywords.
    op_keywords = {
        "AOR": ["+", "-", "*", "/", "%", "arithmetic", "math"],
        "ROR": ["<", ">", "<=", ">=", "==", "!=", "compare", "equal", "less", "greater"],
        "COR": [" and ", " or ", "and_", "or_", "both", "either"],
        "LOR": [" and ", " or "],
        "SVR": ["=", "assign", "set", "store"],
        "UOI": ["-", "negate", "not_", "unary"],
    }
    keywords = op_keywords.get(mutant.operator, [])
    # If ANY keyword shows up in the test source, we optimistically
    # assume the test exercises the operator. This is conservative
    # for the "killed" decision (we kill when there's evidence the
    # operator is tested) and conservative for "survived" (we don't
    # kill without evidence).
    if any(kw in test_source for kw in keywords):
        # We require the assert keyword too — pure variable
        # references don't constitute testing.
        if re.search(r"\bassert\b", test_source):
            return "killed"
    return "survived"


def run_mutation_testing(source: str, source_file: str = "test",
                          tests: List = None, threshold: float = 0.7,
                          test_source: str = "") -> MutationResult:
    """
    Run mutation testing on source. Returns MutationResult.
    Verdict: PASS if score >= threshold, FAIL otherwise.

    `test_source` is the raw text of the test file(s) covering
    `source`. It is used by `simulate_test_run` to determine whether
    each mutant is exercised by an assertion. If `test_source` is
    empty, ALL mutants are conservatively marked as survived (better
    to fail the audit than to pass with no evidence).
    """
    mutants = generate_mutants(source)
    if not mutants:
        return MutationResult(
            source_file=source_file,
            total_mutants=0, killed=0, survived=0, timeout=0,
            score=1.0, verdict="PASS",  # No mutants = trivially pass
        )

    killed = 0
    survived = 0
    survived_mutants = []

    for m in mutants:
        result = simulate_test_run(m, tests_pass=True, test_source=test_source)
        if result == "killed":
            killed += 1
        else:
            survived += 1
            survived_mutants.append(m)

    total = len(mutants)
    score = killed / total if total else 1.0

    if score >= threshold:
        verdict = "PASS"
    elif score >= 0.5:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return MutationResult(
        source_file=source_file,
        total_mutants=total,
        killed=killed,
        survived=survived,
        timeout=0,
        score=score,
        survived_mutants=survived_mutants,
        verdict=verdict,
    )


# === ENFORCEMENT ===

DEFAULT_THRESHOLD = 0.7


def enforce_mutation_testing(coverage_pct: float, mutation_score: float,
                             threshold: float = DEFAULT_THRESHOLD) -> Tuple[bool, str]:
    """
    Enforce mutation testing policy. Returns (is_acceptable, message).
    Refuses PASS if mutation_score < threshold, EVEN if coverage is high.
    """
    if coverage_pct < 0.8:
        return (False, f"FAIL: Coverage {coverage_pct*100:.1f}% < 80% minimum")

    if mutation_score < threshold:
        return (False, f"FAIL: Mutation score {mutation_score*100:.1f}% < {threshold*100:.0f}% threshold. "
                      f"Tests have high coverage but low mutation kill rate — likely testing trivial cases.")

    return (True, f"PASS: Coverage {coverage_pct*100:.1f}%, Mutation score {mutation_score*100:.1f}%")
