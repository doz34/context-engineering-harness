"""Test QW-S3-6: Archive PII Anonymization."""
import sys
import os
import json
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.archive_anonymizer import ArchiveAnonymizer, anonymize_archive_snapshot


def test_anonymize_email():
    a = ArchiveAnonymizer(salt="fixed_salt")
    text = "Contact: alice@example.com"
    anon, count = a.anonymize_text(text)
    assert "alice@example.com" not in anon
    assert "ANON_EMAIL" in anon
    assert count >= 1


def test_anonymize_phone():
    a = ArchiveAnonymizer(salt="fixed_salt")
    text = "Phone: 01 23 45 67 89"
    anon, count = a.anonymize_text(text)
    assert "01 23 45 67 89" not in anon
    assert "ANON_PHONE_FR" in anon


def test_anonymize_ssn():
    a = ArchiveAnonymizer(salt="fixed_salt")
    text = "SSN: 123-45-6789"
    anon, count = a.anonymize_text(text)
    assert "123-45-6789" not in anon
    assert "ANON_SSN_US" in anon


def test_anonymize_no_pii():
    a = ArchiveAnonymizer(salt="fixed_salt")
    text = "Hello world, no PII here."
    anon, count = a.anonymize_text(text)
    assert anon == text
    assert count == 0


def test_anonymize_deterministic():
    """Same PII + same salt = same token (preserves referential integrity)."""
    a1 = ArchiveAnonymizer(salt="same")
    a2 = ArchiveAnonymizer(salt="same")
    t1, _ = a1.anonymize_text("alice@acme.com")
    t2, _ = a2.anonymize_text("alice@acme.com")
    # Same token (deterministic)
    assert "[ANON_EMAIL_" in t1
    assert t1 == t2


def test_anonymize_different_salt_different_token():
    a1 = ArchiveAnonymizer(salt="salt1")
    a2 = ArchiveAnonymizer(salt="salt2")
    t1, _ = a1.anonymize_text("alice@acme.com")
    t2, _ = a2.anonymize_text("alice@acme.com")
    assert t1 != t2  # Different salts = different tokens


def test_anonymize_dict():
    a = ArchiveAnonymizer(salt="x")
    data = {
        "user": "alice@acme.com",
        "metadata": {
            "phone": "01 23 45 67 89",
            "ssn": "123-45-6789",
        },
        "tags": ["a", "b"],
    }
    anon, report = a.anonymize_dict(data)
    assert "alice@acme.com" not in str(anon)
    assert "01 23 45 67 89" not in str(anon)
    assert "123-45-6789" not in str(anon)
    assert report.pii_replaced >= 3


def test_anonymize_list():
    a = ArchiveAnonymizer(salt="x")
    data = {"emails": ["a@b.com", "c@d.com"]}
    anon, report = a.anonymize_dict(data)
    assert "a@b.com" not in str(anon)
    assert "c@d.com" not in str(anon)
    assert report.pii_replaced == 2


def test_gdpr_erasure_makes_data_irrecoverable():
    a = ArchiveAnonymizer(salt="original_salt")
    text = "alice@acme.com"
    anon, _ = a.anonymize_text(text)
    # Token includes hash derived from salt
    # Erase
    a.erase_gdpr()
    # Salt is gone, so future anonymization uses different salt
    # The old token cannot be reversed without the salt
    assert a.salt == ""
    assert a._cache == {}
    assert a._audit_log == []


def test_audit_log_doesnt_contain_originals():
    """The audit log should never contain original PII values."""
    a = ArchiveAnonymizer(salt="x")
    a.anonymize_text("alice@acme.com")
    log = a.export_audit_log()
    log_str = str(log)
    assert "alice@acme.com" not in log_str
    # Only token, type, and hash
    assert "ANON_EMAIL" in log_str


def test_anonymize_archive_snapshot_file():
    """End-to-end: load JSON, anonymize, save."""
    with tempfile.TemporaryDirectory() as d:
        in_path = os.path.join(d, "snapshot.json")
        out_path = os.path.join(d, "snapshot_anon.json")
        snapshot = {
            "users": [
                {"email": "a@b.com", "phone": "01 23 45 67 89"},
                {"email": "c@d.com", "ssn": "123-45-6789"},
            ],
            "metadata": {"created": "2026-06-09", "pii": "alice@evil.com"},
        }
        with open(in_path, "w") as f:
            json.dump(snapshot, f)
        report = anonymize_archive_snapshot(in_path, out_path, salt="test_salt")
        with open(out_path) as f:
            anon = json.load(f)
        # All PII replaced
        assert "a@b.com" not in str(anon)
        assert "c@d.com" not in str(anon)
        assert "01 23 45 67 89" not in str(anon)
        assert "123-45-6789" not in str(anon)
        assert "alice@evil.com" not in str(anon)
        # At least 5 PII replaced
        assert report.pii_replaced >= 5


def test_anonymized_output_file_permissions_0600():
    """The anonymized file should be owner-only readable."""
    with tempfile.TemporaryDirectory() as d:
        in_path = os.path.join(d, "input.json")
        out_path = os.path.join(d, "output.json")
        with open(in_path, "w") as f:
            json.dump({"email": "a@b.com"}, f)
        anonymize_archive_snapshot(in_path, out_path, salt="x")
        mode = os.stat(out_path).st_mode & 0o777
        assert mode == 0o600


def test_pii_type_counted_in_report():
    a = ArchiveAnonymizer(salt="x")
    data = {
        "emails": ["a@b.com", "c@d.com"],
        "phones": ["01 23 45 67 89", "06 12 34 56 78"],
    }
    _, report = a.anonymize_dict(data)
    assert report.pii_replaced == 4
    assert "EMAIL" in report.patterns_matched
    assert "PHONE_FR" in report.patterns_matched


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
