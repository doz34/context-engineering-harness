"""
Tests for lib.security_fallback — SHA256-CTR + HMAC-SHA256 fallback cipher.

v1.1.1 (HIGH-1): Brings coverage from 19% to 100%.
"""

import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSha256CtrHmac:
    def test_roundtrip_basic(self):
        """encrypt then decrypt returns original plaintext."""
        from lib.security_fallback import aes_ctr_hmac_encrypt, aes_ctr_hmac_decrypt

        key = os.urandom(32)
        plaintext = b"hello world"
        blob = aes_ctr_hmac_encrypt(key, plaintext)
        recovered = aes_ctr_hmac_decrypt(key, blob)
        assert recovered == plaintext

    def test_nonce_unique_per_call(self):
        """Each encrypt call uses a fresh random nonce (CTR safety)."""
        from lib.security_fallback import aes_ctr_hmac_encrypt

        key = os.urandom(32)
        plaintext = b"same plaintext"
        blobs = [aes_ctr_hmac_encrypt(key, plaintext) for _ in range(10)]
        # All nonces (first 16 bytes) must differ
        nonces = [b[:16] for b in blobs]
        assert len(set(nonces)) == 10, "nonces must be unique per encrypt call"

    def test_tampered_ciphertext_raises(self):
        """Flipping a ciphertext bit must cause MAC verification to fail."""
        from lib.security_fallback import aes_ctr_hmac_encrypt, aes_ctr_hmac_decrypt

        key = os.urandom(32)
        plaintext = b"some important data"
        blob = bytearray(aes_ctr_hmac_encrypt(key, plaintext))
        # Flip a bit in the ciphertext region (skip 16-byte nonce, before 32-byte MAC)
        blob[20] ^= 0x01
        with pytest.raises(ValueError, match="MAC verification failed"):
            aes_ctr_hmac_decrypt(key, bytes(blob))

    def test_wrong_key_raises(self):
        """Decrypting with the wrong key must fail (MAC mismatch)."""
        from lib.security_fallback import aes_ctr_hmac_encrypt, aes_ctr_hmac_decrypt

        key1 = os.urandom(32)
        key2 = os.urandom(32)
        blob = aes_ctr_hmac_encrypt(key1, b"secret")
        with pytest.raises(ValueError, match="MAC verification failed"):
            aes_ctr_hmac_decrypt(key2, blob)

    def test_invalid_key_length_raises(self):
        """Key must be exactly 32 bytes — neither shorter nor longer accepted."""
        from lib.security_fallback import aes_ctr_hmac_encrypt, aes_ctr_hmac_decrypt

        with pytest.raises(ValueError, match="Key must be 32 bytes"):
            aes_ctr_hmac_encrypt(b"short", b"data")
        with pytest.raises(ValueError, match="Key must be 32 bytes"):
            aes_ctr_hmac_encrypt(b"x" * 64, b"data")

    def test_empty_plaintext_roundtrip(self):
        """Empty plaintext encrypts and decrypts to empty bytes."""
        from lib.security_fallback import aes_ctr_hmac_encrypt, aes_ctr_hmac_decrypt

        key = os.urandom(32)
        blob = aes_ctr_hmac_encrypt(key, b"")
        # blob = nonce(16) + mac(32) = 48 bytes
        assert len(blob) == 16 + 32
        assert aes_ctr_hmac_decrypt(key, blob) == b""

    def test_blob_too_short_raises(self):
        """Truncated blob (less than nonce+mac) must raise ValueError."""
        from lib.security_fallback import aes_ctr_hmac_decrypt

        key = os.urandom(32)
        with pytest.raises(ValueError, match="Blob too short"):
            aes_ctr_hmac_decrypt(key, b"x" * 30)

    def test_large_plaintext_roundtrip(self):
        """Multi-block plaintext (>32 bytes triggers CTR counter increment)."""
        from lib.security_fallback import aes_ctr_hmac_encrypt, aes_ctr_hmac_decrypt

        key = os.urandom(32)
        plaintext = b"A" * 100_000  # 100KB → 3125+ SHA256 blocks
        blob = aes_ctr_hmac_encrypt(key, plaintext)
        assert aes_ctr_hmac_decrypt(key, blob) == plaintext


class TestStreamCipher:
    def test_xor_is_reversible(self):
        """Stream cipher is symmetric: encrypt(encrypt) = identity (CTR property)."""
        from lib.security_fallback import _stream_encrypt

        key = os.urandom(32)
        nonce = os.urandom(16)
        data = b"hello world test"
        ct = _stream_encrypt(key, nonce, data)
        # Re-encrypting ciphertext with same keystream returns plaintext
        pt = _stream_encrypt(key, nonce, ct)
        assert pt == data

    def test_keystream_depends_on_nonce(self):
        """Different nonces must produce different ciphertexts for same data."""
        from lib.security_fallback import _stream_encrypt

        key = os.urandom(32)
        data = b"same plaintext"
        ct1 = _stream_encrypt(key, os.urandom(16), data)
        ct2 = _stream_encrypt(key, os.urandom(16), data)
        assert ct1 != ct2

    def test_keystream_depends_on_counter(self):
        """Counter must increment across blocks (otherwise blocks would XOR to 0)."""
        from lib.security_fallback import _stream_encrypt

        key = os.urandom(32)
        nonce = os.urandom(16)
        # Two 32-byte blocks: each XORed with its own keystream block
        data = b"\x00" * 64  # zeros
        ct = _stream_encrypt(key, nonce, data)
        # ct should NOT be all zeros (would mean counter didn't advance)
        assert ct != b"\x00" * 64
        # Two 32-byte halves should differ (different counters)
        assert ct[:32] != ct[32:]
