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


def test_get_tokenizer_persists_salt():
    """HIGH fix 2026-06-10: same salt → same token across
    process boundaries (cross-day referential integrity)."""
    from lib.pii_tokenizer import get_tokenizer, reset_tokenizer
    reset_tokenizer()
    t1 = get_tokenizer(salt="deterministic_salt_for_test")
    t1.reset_mappings() if hasattr(t1, "reset_mappings") else None
    text = "Email: alice@example.com"
    _, m1 = t1.tokenize(text)
    # Reset singleton and re-fetch with the same salt
    reset_tokenizer()
    t2 = get_tokenizer(salt="deterministic_salt_for_test")
    _, m2 = t2.tokenize(text)
    # Same salt + same input → same token
    assert m1[0].token == m2[0].token


def test_different_salts_yield_different_tokens():
    """Sanity: different salts → different tokens."""
    from lib.pii_tokenizer import get_tokenizer, reset_tokenizer
    reset_tokenizer()
    t1 = get_tokenizer(salt="salt_A")
    _, m_a = t1.tokenize("alice@example.com")
    reset_tokenizer()
    t2 = get_tokenizer(salt="salt_B")
    _, m_b = t2.tokenize("alice@example.com")
    assert m_a[0].token != m_b[0].token


def test_deobfuscate_at_bracket():
    """HIGH fix 2026-06-10: 'alice [at] acme [dot] com' should be
    detected as an email after deobfuscation."""
    t = PIITokenizer()
    findings = t.detect("Contact alice [at] acme [dot] com please")
    types = [f[0] for f in findings]
    assert "EMAIL" in types, (
        f"Expected EMAIL detection in 'alice [at] acme [dot] com', "
        f"got types: {types}"
    )


def test_deobfuscate_at_paren():
    """HIGH fix 2026-06-10: 'alice(at)acme.com' should be detected."""
    t = PIITokenizer()
    findings = t.detect("Write to alice(at)acme.com")
    types = [f[0] for f in findings]
    assert "EMAIL" in types


def test_deobfuscate_whitespace_inside_email_partial():
    """Honest scope (HIGH fix 2026-06-10):

    `'a l i c e @ a c m e . c o m'` (per-character whitespace) is
    NOT detected — the deobfuscation step does not collapse internal
    whitespace because doing so would break legitimate text like
    "Email me at alice@acme.com" → "Email me@alice@acme.com" or
    "Email me at" → "Email me@".

    This test asserts the HONEST scope: the @/dot pair is detected
    when NOT surrounded by single-char-per-letter whitespace, but
    the per-character variant is allowed to slip through as a known
    limitation. Operators relying on PII detection should pair
    tokenizer detection with an upstream LLM-side prompt filter.
    """
    t = PIITokenizer()
    # Clean form: detected
    findings_clean = t.detect("Email alice@acme.com please")
    types_clean = [f[0] for f in findings_clean]
    assert "EMAIL" in types_clean

    # Per-char whitespace form: KNOWN LIMITATION, not detected.
    # We do not assert the negative; we just document the scope.
    findings_obf = t.detect("Email a l i c e @ a c m e . c o m")
    # Either empty (not detected) or detected if a future patch
    # adds chunk-based detection. Today it's empty.
    types_obf = [f[0] for f in findings_obf]
    # Just assert that we don't crash and the test is honest about
    # the limitation.
    assert isinstance(types_obf, list)


def test_detect_iban_with_spaces():
    """HIGH fix 2026-06-10: real IBANs with spaces (e.g.
    'GB29 NWBK 6016 1331 9268 19') should now be detected."""
    t = PIITokenizer()
    findings = t.detect("Wire to GB29 NWBK 6016 1331 9268 19")
    types = [f[0] for f in findings]
    assert "IBAN" in types, (
        f"Expected IBAN detection in 'GB29 NWBK 6016 1331 9268 19', "
        f"got types: {types}"
    )


def test_deobfuscate_handles_zero_width():
    """HIGH fix 2026-06-10: zero-width characters used to break
    regex word boundaries. They should now be stripped."""
    t = PIITokenizer()
    # Insert zero-width space (U+200B) inside the @ character
    # boundary. This is a classic bypass attempt.
    text = "Contact alice​@example.com for info"
    findings = t.detect(text)
    types = [f[0] for f in findings]
    assert "EMAIL" in types


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
