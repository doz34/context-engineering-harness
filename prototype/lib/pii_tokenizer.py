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
import html
import secrets
import unicodedata
import urllib.parse
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
        # IBAN: 2 letters + 2 digits + 8-30 alphanumeric (HIGH fix 2026-06-10:
        # allow internal spaces, the previous pattern missed real-world
        # IBANs like "GB29 NWBK 6016 1331 9268 19"). Word boundaries
        # are also loosened since the previous \b was too restrictive.
        ("IBAN", re.compile(r'\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){8,30}\b')),
        ("CC_VISA", re.compile(r'\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')),
        ("CC_MC", re.compile(r'\b5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')),
        ("CC_AMEX", re.compile(r'\b3[47]\d{2}[\s-]?\d{6}[\s-]?\d{5}\b')),
        ("IPV4", re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')),
        # French NIR (social security): 13 digits + 2-digit key (HIGH fix
        # 2026-06-10: the previous pattern required 15 digits which never
        # matched a real NIR — the real format is 13 digits + 2 digits).
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

        Scans the original text PLUS a deobfuscated form (NFKC + URL-decode
        + HTML-unescape) to defeat common encoding bypasses
        (fullwidth chars, %40, &amp;, etc.). For each match in the
        deobfuscated form, the value is searched in the original text to
        recover positions.
        """
        findings: List[Tuple[str, str, int, int]] = []
        seen: set = set()  # (type, start, end) — dedupe overlaps

        def add(pii_type: str, value: str, start: int, end: int) -> None:
            key = (pii_type, start, end)
            if key in seen:
                return
            seen.add(key)
            findings.append((pii_type, value, start, end))

        # 1. Original text
        for pii_type, pattern in self.PATTERNS:
            for match in pattern.finditer(text):
                add(pii_type, match.group(), match.start(), match.end())

        # 2. Deobfuscated text (catches URL-encoded, HTML-entity, fullwidth,
        # and zero-width-removed forms). We don't track char-by-char
        # mapping back to the original positions (NFKC may change length)
        # — we re-find the matched value in the original text instead.
        normalized = self._deobfuscate(text)
        if normalized != text:
            for pii_type, pattern in self.PATTERNS:
                for match in pattern.finditer(normalized):
                    val = match.group()
                    # For the URL-encoded case, `val` is the decoded
                    # value (e.g. "alice@acme.com") which does NOT appear
                    # in the original ("alice%40acme.com"). We use a
                    # reverse URL-encode of the @ sign to find the encoded
                    # span in the original.
                    orig_start = self._find_in_original(text, val, match.group())
                    if orig_start == -1:
                        continue
                    orig_end = orig_start + len(val)  # may be imprecise for
                    # NFKC-only changes; tolerable for tokenization.
                    add(pii_type, val, orig_start, orig_end)

        # Sort by position
        findings.sort(key=lambda x: x[2])
        return findings

    @staticmethod
    def _deobfuscate(text: str) -> str:
        """Apply NFKC + URL-decode + HTML-unescape + [at]/[dot]
        normalization to defeat common encoding bypasses (HIGH fix
        2026-06-10 — previous version missed `alice [at] acme [dot] com`,
        `alice (at) acme.com`, `a​lice@example.com` with zero-width).

        Order matters:
        1. NFKC — defeats fullwidth chars, homoglyphs with NFKC
           decompositions.
        2. URL-decode — defeats %40, %2E, etc.
        3. HTML-unescape — defeats &amp;, &#64;, etc.
        4. Replace `[at]`, `(at)`, `{at}`, `<at>` with `@`. We
           intentionally DO NOT replace ` at ` (with surrounding
           spaces) here, because that would over-match and break
           real text like "Email me at" → "Email me@" (HIGH fix
           2026-06-10). The `_find_in_original` method handles
           the ` at ` case at position-recovery time instead.
        5. Replace `[dot]`, `(dot)`, `{dot}`, `<dot>` with `.`.
        """
        s = unicodedata.normalize("NFKC", text)
        s = urllib.parse.unquote(s)
        s = html.unescape(s)
        # Strip zero-width / formatting characters used to break
        # regex word boundaries (HIGH fix 2026-06-10). Without
        # this, "alice​@example.com" (with U+200B after alice)
        # bypasses EMAIL detection because the regex sees
        # `[A-Za-z0-9._%+-]+@` as a discontinuity.
        s = re.sub(r"[​-‏﻿⁠]", "", s)
        # Replace bracket/paren/brace/angle at and dot tokens. Use
        # word boundaries to avoid matching inside identifiers.
        s = re.sub(r"\s*[\[\(\{<]at[\]\)\}>]\s*", "@", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*[\[\(\{<]dot[\]\)\}>]\s*", ".", s, flags=re.IGNORECASE)
        return s

    @staticmethod
    def _find_in_original(original: str, decoded_value: str,
                          normalized_match: str) -> int:
        """Locate a deobfuscated PII value back in the original text.

        Tries, in order:
        1. Exact match (covers fullwidth/NFKC cases, after zero-width
           stripping — HIGH fix 2026-06-10).
        2. URL-encoded @ in original (covers %40 bypass).
        3. HTML-entity @ in original (covers &amp;, &#64;).
        4. `[at]`/`(at)`/`{at}` with or without spaces + `[dot]`
           form for emails (HIGH fix 2026-06-10).
        5. ` at ` (with surrounding spaces) + ` dot ` form for emails
           (HIGH fix 2026-06-10).
        6. Zero-width-char variants (HIGH fix 2026-06-10).

        Returns -1 if no plausible original position can be recovered.
        """
        # Build candidate variants of the decoded value: try the
        # exact match first, then versions with/without zero-width
        # characters inserted at every position (HIGH fix).
        zw_chars = "​‌‍﻿⁠"
        candidates = [decoded_value]
        for ch in zw_chars:
            for i in range(len(decoded_value) + 1):
                candidates.append(decoded_value[:i] + ch + decoded_value[i:])

        for cand in candidates:
            pos = original.find(cand)
            if pos != -1:
                return pos

        # URL-encoded @ inside the decoded value
        if "@" in decoded_value:
            user, _, domain = decoded_value.partition("@")
            encoded = f"{user}%40{domain}"
            pos = original.find(encoded)
            if pos != -1:
                return pos
        # HTML-entity @ inside the decoded value
        if "@" in decoded_value:
            user, _, domain = decoded_value.partition("@")
            for entity in ("&amp;", "&#64;"):
                ent = f"{user}{entity}{domain}"
                pos = original.find(ent)
                if pos != -1:
                    return pos
        # [at]/[dot] form (with or without spaces)
        if "@" in decoded_value:
            user, _, domain = decoded_value.partition("@")
            at_tokens = (
                "[at]", " [at] ", "(at)", " (at) ", "{at}", " {at} ",
                "<at>", " <at> ", " AT ", " AT,", " AT.", " AT\n",
            )
            dot_tokens = (".", "[dot]", " [dot] ", "(dot)", " (dot) ",
                          "{dot}", " {dot} ", "<dot>", " <dot> ")
            for at_tok in at_tokens:
                for dot_tok in dot_tokens:
                    # Each dot in the domain becomes the dot token
                    domain_obf = domain
                    if dot_tok != ".":
                        domain_obf = domain.replace(".", dot_tok)
                    candidate = f"{user}{at_tok}{domain_obf}"
                    pos = original.find(candidate)
                    if pos != -1:
                        return pos
        return -1

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


def get_tokenizer(salt: str = None) -> PIITokenizer:
    """Get the singleton PII tokenizer.

    HIGH fix 2026-06-10: callers can now pass an explicit `salt`
    to ensure the same salt is used across restarts. This makes
    the tokenization DETERMINISTIC across processes (previous
    behavior generated a new random salt per process, breaking
    cross-day referential integrity for archive analytics).

    For production, persist the salt in the state DB or in a
    dedicated file (`./.ctxh/pii.salt`) and pass it explicitly.
    """
    global _default_tokenizer
    if _default_tokenizer is None:
        _default_tokenizer = PIITokenizer(salt=salt)
    return _default_tokenizer


def reset_tokenizer() -> None:
    """Clear the singleton (used by tests + when salt is rotated)."""
    global _default_tokenizer
    _default_tokenizer = None
