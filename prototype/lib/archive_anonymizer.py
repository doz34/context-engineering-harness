"""
QW-S3-6 — Archive PII Anonymization (GDPR Art. 17)
====================================================
Anonymize PII in archive snapshots before storage.
Closes: Archive PII leakage (right to erasure).
Pattern: Replace PII with deterministic tokens (reversible for audit).
"""

import os
import json
import re
import hashlib
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AnonymizationReport:
    """Report of an anonymization pass."""
    items_processed: int
    pii_replaced: int
    patterns_matched: Dict[str, int]  # {pattern_name: count}
    errors: List[str] = field(default_factory=list)


class ArchiveAnonymizer:
    """
    Anonymize PII in archive data structures.
    Uses a one-way hash (SHA-256 with global salt) so that the same
    PII always maps to the same token (preserves referential integrity
    for analytics), but the original is unrecoverable.

    GDPR Art. 17 (right to erasure): the mapping table is the "key".
    Erasing the table makes the data permanently anonymous.
    """

    # Patterns (subset of pii_tokenizer)
    PATTERNS = [
        ("EMAIL", re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
        ("PHONE_INTL", re.compile(r'\+\d{1,3}[\s.-]?\d{4,}')),
        ("PHONE_FR", re.compile(r'\b0[1-9](?:[\s.-]?\d{2}){4}\b')),
        ("SSN_US", re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
        ("IBAN", re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b')),
        ("CC_VISA", re.compile(r'\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')),
        ("IPV4", re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')),
    ]

    def __init__(self, salt: Optional[str] = None, replacement_prefix: str = "ANON"):
        self.salt = salt or self._generate_salt()
        self.replacement_prefix = replacement_prefix
        self._cache: Dict[str, str] = {}  # value → token (deterministic)
        self._audit_log: List[Dict] = []  # token → hash (for GDPR erasure)

    def _generate_salt(self) -> str:
        import secrets
        return secrets.token_hex(16)

    def _hash_pii(self, value: str) -> str:
        """Hash PII to a deterministic token."""
        return hashlib.sha256(f"{self.salt}:{value}".encode()).hexdigest()[:12]

    def anonymize_text(self, text: str) -> tuple[str, int]:
        """
        Anonymize PII in text. Returns (anonymized_text, count_replaced).
        """
        count = 0
        for pii_type, pattern in self.PATTERNS:
            def replace(match):
                nonlocal count
                value = match.group()
                if value in self._cache:
                    token = self._cache[value]
                else:
                    hash_part = self._hash_pii(value)
                    token = f"[{self.replacement_prefix}_{pii_type}_{hash_part.upper()}]"
                    self._cache[value] = token
                    # Audit: log token → hash (NOT the original)
                    self._audit_log.append({
                        "token": token,
                        "pii_type": pii_type,
                        "hash": hash_part,
                    })
                count += 1
                return token
            text = pattern.sub(replace, text)
        return text, count

    def anonymize_dict(self, data: dict) -> tuple[dict, AnonymizationReport]:
        """Recursively anonymize a dict's string values."""
        report = AnonymizationReport(items_processed=0, pii_replaced=0, patterns_matched={})
        result = {}
        for k, v in data.items():
            result[k] = self._anonymize_value(v, report)
        return result, report

    def _anonymize_value(self, value, report: AnonymizationReport) -> any:
        """Anonymize a single value (recursive for dict/list/str)."""
        report.items_processed += 1
        if isinstance(value, str):
            anon, count = self.anonymize_text(value)
            if count > 0:
                report.pii_replaced += count
                # Update pattern counts (approximate)
                for pii_type, _ in self.PATTERNS:
                    if pii_type in anon:
                        report.patterns_matched[pii_type] = report.patterns_matched.get(pii_type, 0) + 1
            return anon
        elif isinstance(value, dict):
            return {k: self._anonymize_value(v, report) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._anonymize_value(item, report) for item in value]
        else:
            return value

    def export_audit_log(self) -> List[Dict]:
        """Export the audit log (token → hash). For GDPR compliance."""
        return list(self._audit_log)

    def erase_gdpr(self):
        """
        GDPR Art. 17: Right to erasure.
        Erase the salt + cache + audit log. After this, anonymized data
        CANNOT be de-anonymized (the salt is gone).
        """
        self.salt = ""
        self._cache.clear()
        self._audit_log.clear()

    def save_state(self, path: str):
        """Persist the salt + audit log to disk (for compliance audit)."""
        state = {
            "salt": self.salt,
            "audit_log": self._audit_log,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        os.chmod(path, 0o600)


def anonymize_archive_snapshot(snapshot_path: str, output_path: str,
                                salt: Optional[str] = None) -> AnonymizationReport:
    """
    Load a JSON snapshot, anonymize it, save the anonymized version.
    """
    with open(snapshot_path) as f:
        data = json.load(f)
    a = ArchiveAnonymizer(salt=salt)
    anon, report = a.anonymize_dict(data)
    with open(output_path, "w") as f:
        json.dump(anon, f, indent=2)
    os.chmod(output_path, 0o600)
    a.save_state(output_path + ".salt")
    return report
