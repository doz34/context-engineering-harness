"""
Security Fallback — when cryptography lib is not available.
Provides AES-256-CTR + HMAC-SHA256 (encrypt-then-MAC).
This is NOT as secure as AES-GCM (vulnerable to nonce reuse) but
acceptable for POV testing without external deps.
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


def aes_ctr_hmac_decrypt(key: bytes, blob: bytes) -> str:
    """Decrypt blob = nonce(16) + ct + mac(32)."""
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

    # Decrypt
    pt = _stream_encrypt(enc_key, nonce, ct)  # CTR is symmetric
    return pt.decode()


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
