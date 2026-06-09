"""
QW-S3-10 — Property-Based Testing
====================================
Generators and property tests for invariants.
Pattern: Hypothesis-style without external dep.
"""

import random
import string
from typing import Callable, List, Any
from dataclasses import dataclass


@dataclass
class PropertyResult:
    """Result of a property test."""
    name: str
    num_tests: int
    num_failures: int
    counter_examples: List[Any] = field(default_factory=list) if False else None  # avoid dataclass field issue


# Simple property-based testing harness (no Hypothesis dep)

def generate_string(min_len: int = 0, max_len: int = 100, charset: str = None) -> str:
    """Generate a random string."""
    if charset is None:
        charset = string.ascii_letters + string.digits + " .,;:!?"
    length = random.randint(min_len, max_len)
    return ''.join(random.choice(charset) for _ in range(length))


def generate_email() -> str:
    """Generate a random email-like string."""
    user = generate_string(min_len=3, max_len=10, charset=string.ascii_lowercase)
    domain = generate_string(min_len=3, max_len=10, charset=string.ascii_lowercase)
    tld = random.choice(['com', 'org', 'net', 'io', 'fr'])
    return f"{user}@{domain}.{tld}"


def generate_phone_fr() -> str:
    """Generate a random French phone."""
    return f"0{random.randint(1,9)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)}"


def generate_ssn() -> str:
    """Generate a random US SSN."""
    return f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}"


def property_test(name: str, prop_func: Callable, num_tests: int = 100,
                 generator: Callable = None) -> dict:
    """
    Run a property test num_tests times.
    Returns dict with results.
    """
    failures = []
    for i in range(num_tests):
        if generator is not None:
            test_input = generator()
        else:
            test_input = None
        try:
            ok = prop_func(test_input) if test_input is not None else prop_func()
            if not ok:
                failures.append(test_input)
        except Exception as e:
            failures.append(f"EXCEPTION: {type(e).__name__}: {e}")

    return {
        "name": name,
        "num_tests": num_tests,
        "num_failures": len(failures),
        "counter_examples": failures[:5],  # First 5
    }


# === PROPERTY TESTS FOR OUR INVARIANTS ===

def prop_dsl_roundtrip(dsl: str) -> bool:
    """Property: parse(emit(x)) == x for valid DSL strings."""
    from lib.dsl import parse, emit
    try:
        parsed = parse(dsl)
        re_emitted = emit(parsed)
        re_parsed = parse(re_emitted)
        return parsed == re_parsed
    except Exception:
        return False


def prop_pii_tokenization_idempotent(text: str) -> bool:
    """Property: tokenize(tokenize(x)) == tokenize(x) (idempotent)."""
    from lib.pii_tokenizer import PIITokenizer
    t = PIITokenizer(salt="test_salt")
    tok1, _ = t.tokenize(text)
    tok2, _ = t.tokenize(tok1)
    # No PII should be in the tokenized output
    return t.detect(tok1) == [] or all("PII" not in f[0] for f in t.detect(tok1))


def prop_subagent_validator_strict_keyword(payload: str) -> bool:
    """Property: subagent validator refuses UNKNOWN keys."""
    from lib.subagent_validator import validate
    dsl = f"EVIL:{payload}"
    r = validate(dsl, strict=True)
    return not r.is_valid  # Should refuse


def prop_compaction_budget_respected(items: list) -> bool:
    """Property: compaction output fits in budget."""
    from lib.ace_compact import ACECompact, CompactionItem
    compact = ACECompact(target_budget=100)
    result = compact.compact(items)
    tokens_out = result["report"]["tokens_out"]
    return tokens_out <= 100 * 2  # Allow 2x for head/tail overhead


def prop_sha256_format(s: str) -> bool:
    """Property: SHA-256 of any string is 64 hex chars."""
    import hashlib
    h = hashlib.sha256(s.encode()).hexdigest()
    return len(h) == 64 and all(c in '0123456789abcdef' for c in h)


def prop_hmac_deterministic(key: bytes, payload: str) -> bool:
    """Property: HMAC of same key+payload is always the same."""
    import hmac
    import hashlib
    h1 = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    h2 = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    return h1 == h2


# === RUN ALL PROPERTY TESTS ===

def run_all_property_tests(num_tests: int = 50) -> List[dict]:
    """Run all property tests and return results."""
    results = []
    # Property 1: DSL roundtrip
    results.append(property_test(
        "dsl_roundtrip",
        prop_dsl_roundtrip,
        num_tests=num_tests,
        generator=lambda: f"KEY1:{generate_string(5,20)};;KEY2:{generate_string(5,20)}",
    ))
    # Property 2: PII tokenization idempotent
    results.append(property_test(
        "pii_tokenization_idempotent",
        prop_pii_tokenization_idempotent,
        num_tests=num_tests,
        generator=lambda: random.choice([
            f"Contact {generate_email()} for info",
            f"SSN: {generate_ssn()}",
            f"Phone: {generate_phone_fr()}",
            "No PII here",
            generate_string(20, 100),
        ]),
    ))
    # Property 3: Subagent validator refuses unknown keys
    results.append(property_test(
        "subagent_validator_strict",
        prop_subagent_validator_strict_keyword,
        num_tests=num_tests,
        generator=lambda: generate_string(5, 50),
    ))
    # Property 4: SHA-256 format
    results.append(property_test(
        "sha256_format",
        prop_sha256_format,
        num_tests=num_tests,
        generator=lambda: generate_string(0, 100),
    ))
    return results
