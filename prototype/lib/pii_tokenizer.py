"""
CE-Harness PII Tokenizer
=========================
Detect and tokenize PII before LLM injection.
Closes CRIT: PII_TOKENS_NOT_TOKENIZED (CISO HIGH)

Pattern: Anthropic 2025-11 — "the MCP client intercepts the data
and tokenizes PII before it reaches the model".
"""

import re
import hashlib
import secrets
from typing import Tuple, Dict, List
from dataclasses import dataclass, field


@dataclass
class PIIMapping:
    """Mapping of token → original PII (for un-tokenization)."""
    token: str
    pii_type: str
    original_hash: str  # SHA-256, not the original itself


class PIITokenizer:
    """
    Detect and tokenize PII (emails, phones, SSN, IBAN, CC, names).
    Uses regex for detection + HMAC for tokenization (deterministic per session).
    """

    # Patterns with named groups
    PATTERNS = [
        ("EMAIL", re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
        ("PHONE_INTL", re.compile(r'\+\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,9}')),
        ("PHONE_FR", re.compile(r'\b0[1-9](?:[\s.-]?\d{2}){4}\b')),
        ("SSN_US", re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
        ("IBAN", re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b')),
        ("CC_VISA", re.compile(r'\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')),
        ("CC_MC", re.compile(r'\b5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')),
        ("CC_AMEX", re.compile(r'\b3[47]\d{2}[\s-]?\d{6}[\s-]?\d{5}\b')),
        ("IPV4", re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')),
        # French NIR (social security)
        ("NIR_FR", re.compile(r'\b[12]\d{2}(?:0[1-9]|1[0-2])\d{2}\d{3}\d{3}\d{2}\b')),
        # Passport-like (2 letters + 7 digits, common pattern)
        ("PASSPORT", re.compile(r'\b[A-Z]{2}\d{7}\b')),
    ]

    # Common name patterns (basic, will have false positives)
    # We avoid pure name detection to minimize false positives.

    def __init__(self, salt: str = None):
        self.salt = salt or secrets.token_hex(8)
        self._mappings: Dict[str, PIIMapping] = {}

    def _token(self, pii_type: str, value: str) -> str:
        """Generate a deterministic token for a PII value."""
        h = hashlib.sha256(f"{self.salt}:{value}".encode()).hexdigest()[:8]
        return f"[{pii_type}_{h.upper()}]"

    def _hash(self, value: str) -> str:
        """Hash a value without storing the original."""
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def detect(self, text: str) -> List[Tuple[str, str, int, int]]:
        """
        Detect PII in text. Returns list of (type, value, start, end).
        """
        findings = []
        for pii_type, pattern in self.PATTERNS:
            for match in pattern.finditer(text):
                findings.append((pii_type, match.group(), match.start(), match.end()))
        # Sort by position
        findings.sort(key=lambda x: x[2])
        return findings

    def tokenize(self, text: str) -> Tuple[str, List[PIIMapping]]:
        """
        Replace PII in text with tokens. Returns (tokenized_text, mappings).
        """
        findings = self.detect(text)
        if not findings:
            return text, []

        # Deduplicate (same PII → same token)
        seen: Dict[str, str] = {}  # value → token
        mappings: List[PIIMapping] = []

        # Build replacement list, then apply in reverse (to preserve indices)
        replacements: List[Tuple[int, int, str, str]] = []  # start, end, token, type
        for pii_type, value, start, end in findings:
            if value in seen:
                token = seen[value]
            else:
                token = self._token(pii_type, value)
                seen[value] = token
                mapping = PIIMapping(
                    token=token,
                    pii_type=pii_type,
                    original_hash=self._hash(value),
                )
                mappings.append(mapping)
                self._mappings[token] = mapping
            replacements.append((start, end, token, pii_type))

        # Apply replacements right-to-left
        result = text
        for start, end, token, pii_type in sorted(replacements, key=lambda x: -x[0]):
            result = result[:start] + token + result[end:]

        return result, mappings

    def untokenize(self, text: str) -> str:
        """
        Reverse: replace tokens with stored mappings.
        NOTE: We do NOT store originals, only hashes — this is one-way
        for security. The real PII flows from tool_result to tool_call
        via the MCP client (Anthropic 2025-11 pattern).
        """
        # We only have hashes, not originals, so untokenize is a no-op
        # In production, the MCP client maintains a separate vault.
        return text

    def stats(self) -> dict:
        """Stats for telemetry."""
        return {
            "patterns_loaded": len(self.PATTERNS),
            "types": [t for t, _ in self.PATTERNS],
            "mappings_count": len(self._mappings),
            "salt_protected": True,
        }


# Singleton for the harness
_default_tokenizer = None

def get_tokenizer() -> PIITokenizer:
    global _default_tokenizer
    if _default_tokenizer is None:
        _default_tokenizer = PIITokenizer()
    return _default_tokenizer
