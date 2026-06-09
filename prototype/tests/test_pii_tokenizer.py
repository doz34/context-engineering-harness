"""Test PII Tokenizer (Fix 2)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.pii_tokenizer import PIITokenizer, PIIMapping


def test_tokenizer_imports():
    t = PIITokenizer()
    assert t.stats()["patterns_loaded"] == 11


def test_detect_email():
    t = PIITokenizer()
    findings = t.detect("Contact john.doe@example.com for info")
    assert len(findings) >= 1
    types = [f[0] for f in findings]
    assert "EMAIL" in types


def test_detect_phone_french():
    t = PIITokenizer()
    findings = t.detect("Tel: 01 23 45 67 89")
    types = [f[0] for f in findings]
    assert "PHONE_FR" in types


def test_detect_phone_intl():
    t = PIITokenizer()
    findings = t.detect("Call +33 1 23 45 67 89 or +1 555-123-4567")
    types = [f[0] for f in findings]
    assert "PHONE_INTL" in types


def test_detect_ssn():
    t = PIITokenizer()
    findings = t.detect("SSN: 123-45-6789")
    types = [f[0] for f in findings]
    assert "SSN_US" in types


def test_detect_credit_card_visa():
    t = PIITokenizer()
    findings = t.detect("Card: 4532 1234 5678 9010")
    types = [f[0] for f in findings]
    assert "CC_VISA" in types


def test_detect_iban():
    t = PIITokenizer()
    # IBAN pattern is contiguous (no spaces). Real IBANs have spaces when
    # human-formatted but the canonical form is contiguous.
    findings = t.detect("IBAN: FR7612345678901234567890123")
    types = [f[0] for f in findings]
    assert "IBAN" in types


def test_tokenize_replaces_pii():
    t = PIITokenizer()
    text = "Email: john.doe@example.com, phone: 01 23 45 67 89"
    tokenized, mappings = t.tokenize(text)
    # Original PII should not be present
    assert "john.doe@example.com" not in tokenized
    assert "01 23 45 67 89" not in tokenized
    # Tokens should be present
    assert "[EMAIL_" in tokenized or "[PHONE_FR_" in tokenized


def test_tokenize_deterministic():
    """Same PII → same token (within session)."""
    t = PIITokenizer(salt="fixed_salt")
    text1 = "Contact: john.doe@example.com"
    text2 = "Email: john.doe@example.com again"
    tok1, _ = t.tokenize(text1)
    tok2, _ = t.tokenize(text2)
    # Both should have same token for same email
    import re
    tok1_match = re.search(r'\[EMAIL_[A-F0-9]+\]', tok1)
    tok2_match = re.search(r'\[EMAIL_[A-F0-9]+\]', tok2)
    assert tok1_match and tok2_match
    assert tok1_match.group() == tok2_match.group()


def test_tokenize_no_pii():
    """No PII = text unchanged."""
    t = PIITokenizer()
    text = "Hello world, this is a clean text without sensitive data."
    tokenized, mappings = t.tokenize(text)
    assert tokenized == text
    assert mappings == []


def test_tokenize_multiple_pii_types():
    """Multiple PII types detected in one text."""
    t = PIITokenizer()
    text = "John (john.doe@example.com) tel 01 23 45 67 89, SSN 123-45-6789"
    tokenized, mappings = t.tokenize(text)
    # All 3 types detected
    types = {m.pii_type for m in mappings}
    assert "EMAIL" in types
    assert "PHONE_FR" in types
    assert "SSN_US" in types
    # All 3 originals are gone
    assert "john.doe@example.com" not in tokenized
    assert "01 23 45 67 89" not in tokenized
    assert "123-45-6789" not in tokenized


def test_tokenizer_uses_hashing():
    """Mappings store hash, not original PII."""
    t = PIITokenizer()
    text = "Email: secret@example.com"
    _, mappings = t.tokenize(text)
    assert len(mappings) == 1
    assert "secret@example.com" not in str(mappings[0].__dict__)


def test_get_tokenizer_singleton():
    from lib.pii_tokenizer import get_tokenizer
    t1 = get_tokenizer()
    t2 = get_tokenizer()
    assert t1 is t2


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
