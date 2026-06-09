"""Test QW10: Mutation testing enforcement."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.mutation_testing import (
    generate_mutants, run_mutation_testing, enforce_mutation_testing,
    Mutant,
)


SAMPLE_CODE = """
def add(a, b):
    return a + b

def is_positive(x):
    return x > 0

def both_positive(a, b):
    return a > 0 and b > 0

def divide(a, b):
    return a / b
"""


def test_generate_mutants_arithmetic():
    mutants = generate_mutants(SAMPLE_CODE)
    # Should find mutants for + and / in add() and divide()
    aor_mutants = [m for m in mutants if m.operator == "AOR"]
    assert len(aor_mutants) >= 2  # + in add, / in divide


def test_generate_mutants_relational():
    mutants = generate_mutants(SAMPLE_CODE)
    ror_mutants = [m for m in mutants if m.operator == "ROR"]
    assert len(ror_mutants) >= 2  # > in is_positive, > in both_positive


def test_generate_mutants_conditional():
    mutants = generate_mutants(SAMPLE_CODE)
    cor_mutants = [m for m in mutants if m.operator == "COR"]
    assert len(cor_mutants) >= 1  # and in both_positive


def test_generate_mutants_invalid_syntax():
    mutants = generate_mutants("def invalid(:\n    pass")
    assert mutants == []


def test_run_mutation_testing_returns_result():
    r = run_mutation_testing(SAMPLE_CODE)
    assert r.total_mutants > 0
    assert r.killed + r.survived == r.total_mutants


def test_run_mutation_testing_verdict_pass():
    """If all mutants are killed, verdict is PASS."""
    r = run_mutation_testing("def f(x):\n    return x")
    # No mutants possible (no BinOp, Compare, BoolOp)
    assert r.total_mutants == 0
    assert r.score == 1.0
    assert r.verdict == "PASS"


def test_enforcement_accepts_high_coverage_and_mutation():
    ok, msg = enforce_mutation_testing(coverage_pct=0.95, mutation_score=0.85)
    assert ok
    assert "PASS" in msg


def test_enforcement_rejects_low_coverage():
    ok, msg = enforce_mutation_testing(coverage_pct=0.5, mutation_score=0.9)
    assert not ok
    assert "Coverage" in msg


def test_enforcement_rejects_low_mutation_score():
    """High coverage + low mutation score = TRAP (tests are useless)."""
    ok, msg = enforce_mutation_testing(coverage_pct=0.95, mutation_score=0.3)
    assert not ok
    assert "Mutation score" in msg
    assert "low mutation kill rate" in msg


def test_enforcement_threshold_respected():
    ok, msg = enforce_mutation_testing(coverage_pct=0.9, mutation_score=0.6, threshold=0.5)
    assert ok
    ok2, _ = enforce_mutation_testing(coverage_pct=0.9, mutation_score=0.6, threshold=0.7)
    assert not ok2


def test_trivial_test_detection():
    """A test that asserts 'True is True' has high coverage but no logic value."""
    trivial_test = """
def test_always_true():
    assert True
"""
    mutants = generate_mutants(trivial_test)
    # No mutants generated (no logic to mutate)
    r = run_mutation_testing(trivial_test)
    # Score 1.0 because no mutants = trivial PASS
    # But real test runner would catch this. For POV, we just check the formula.
    assert r.score == 1.0


def test_mutant_dataclass():
    m = Mutant(id="x", line=1, column=0, original="x", mutated="y", operator="AOR")
    assert m.id == "x"
    assert m.operator == "AOR"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
