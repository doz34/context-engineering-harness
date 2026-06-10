"""
Security Fallback — when cryptography lib is not available.

⚠️ IMPORTANT — cipher clarification (F-002, audit 2026-06-10):
This module provides **SHA256-CTR (custom stream cipher) + HMAC-SHA256
(encrypt-then-MAC)** — NOT AES-256-CTR. The original docstring used the
"AES-256-CTR" label, which was misleading: a true AES-256-CTR requires
the `cryptography` (or `pycryptodome`) library, and the stdlib does not
ship AES. To stay zero-dependency, we use a SHA256-based stream cipher
that is functionally similar to AES-CTR (XOR with a keystream) but is
NOT certified as a block cipher.

Limitations (acceptable for POV when cryptography is unavailable):
- Not AES: do NOT use where AES compliance is required (FIPS, RGPD, etc.)
- Vulnerable to nonce reuse: never reuse (key, nonce) pair
- Slower than hardware AES: ~1 SHA256 per 32 bytes (manual CTR)
- Unaudited cipher: prefer `cryptography.AESGCM` when available

Use `lib.security.EncryptedDB.is_secure()` to check whether AESGCM is
active. The fallback path is only a degraded mode for environments
where `cryptography` cannot be installed.
"""

import hashlib
import hmac as _hmac
import os
import struct


def aes_ctr_hmac_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """
    Encrypt-then-MAC: AES-256-CTR + HMAC-SHA256.
    Output: nonce(16) + ct + mac(32)
    """
    if len(key) != 32:
        raise ValueError(f"Key must be 32 bytes, got {len(key)}")
    nonce = os.urandom(16)

    # Derive enc_key and mac_key from master key
    enc_key = hashlib.sha256(b"enc" + key).digest()
    mac_key = hashlib.sha256(b"mac" + key).digest()

    # CTR encryption (manual since stdlib doesn't have AES)
    # Use a simple stream cipher based on SHA256 in counter mode
    ct = _stream_encrypt(enc_key, nonce, plaintext)

    # HMAC over nonce + ct
    mac = _hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()

    return nonce + ct + mac


def aes_ctr_hmac_decrypt(key: bytes, blob: bytes) -> bytes:
    """Decrypt blob = nonce(16) + ct + mac(32). Returns plaintext bytes."""
    if len(blob) < 16 + 32:
        raise ValueError("Blob too short")
    nonce, mac = blob[:16], blob[-32:]
    ct = blob[16:-32]

    enc_key = hashlib.sha256(b"enc" + key).digest()
    mac_key = hashlib.sha256(b"mac" + key).digest()

    # Verify MAC first (constant-time)
    expected_mac = _hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    if not _hmac.compare_digest(expected_mac, mac):
        raise ValueError("MAC verification failed (tampering or wrong key)")

    # Decrypt (CTR is symmetric — re-encrypt ciphertext with same keystream)
    return _stream_encrypt(enc_key, nonce, ct)


def _stream_encrypt(key: bytes, nonce: bytes, data: bytes) -> bytes:
    """
    Simple SHA256-CTR stream cipher (POV fallback).
    Generates a keystream by hashing key+nonce+counter, XORs with data.
    NOT as secure as AES but acceptable for POV without external deps.
    """
    out = bytearray()
    counter = 0
    pos = 0
    while pos < len(data):
        # Generate 32 bytes of keystream
        block_input = key + nonce + struct.pack(">Q", counter)
        keystream = hashlib.sha256(block_input).digest()
        # XOR with data
        chunk_len = min(32, len(data) - pos)
        for i in range(chunk_len):
            out.append(data[pos + i] ^ keystream[i])
        pos += chunk_len
        counter += 1
    return bytes(out)
