"""Test QW4: MCP Trust Store (Hash Pinning)."""
import sys
import os
import tempfile
import hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.mcp_trust import (
    MCPServerEntry, validate_mcp_at_boot, load_trust_store, save_trust_store,
    sign_entry, verify_entry_signature, sha256_file, sha256_bytes,
    tofu_pin, DEFAULT_TRUSTED_PUBLISHERS,
)
import hmac


def test_sha256_file_correct():
    """sha256 of a file is correct."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"hello world")
        path = f.name
    try:
        h = sha256_file(path)
        # Known SHA-256 of "hello world"
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert h == expected
    finally:
        os.unlink(path)


def test_sha256_bytes():
    assert sha256_bytes(b"hello") == hashlib.sha256(b"hello").hexdigest()


def test_trust_store_roundtrip():
    """Save and load preserves all fields."""
    with tempfile.TemporaryDirectory() as d:
        store_path = os.path.join(d, "trust.json")
        entry = MCPServerEntry(
            name="test-mcp", publisher="anthropic",
            expected_sha256="abc123", version="1.0.0",
            signed_at="2026-06-08T00:00:00", signature="sig123",
        )
        store = {"test-mcp": entry}
        save_trust_store(store_path, store)
        loaded = load_trust_store(store_path)
        assert "test-mcp" in loaded
        assert loaded["test-mcp"].expected_sha256 == "abc123"
        assert loaded["test-mcp"].publisher == "anthropic"


def test_trust_store_permissions_0600():
    with tempfile.TemporaryDirectory() as d:
        store_path = os.path.join(d, "trust.json")
        save_trust_store(store_path, {})
        mode = os.stat(store_path).st_mode & 0o777
        assert mode == 0o600


def test_sign_and_verify_entry():
    """HMAC signature on a trust entry is correct."""
    entry = MCPServerEntry(
        name="test", publisher="anthropic",
        expected_sha256="hash", version="1.0",
        signed_at="2026-06-08", signature="",
    )
    key = b"a" * 32
    sign_entry(entry, key)
    assert entry.signature != ""
    assert verify_entry_signature(entry, key)
    # Wrong key fails
    assert not verify_entry_signature(entry, b"b" * 32)
    # Tampered entry fails
    entry.expected_sha256 = "modified"
    assert not verify_entry_signature(entry, key)


def test_validate_mcp_at_boot_happy_path():
    """Server with matching hash and trusted publisher is validated."""
    with tempfile.TemporaryDirectory() as d:
        # Create a fake MCP server file
        server_path = os.path.join(d, "mcp1.py")
        with open(server_path, "w") as f:
            f.write("# fake mcp server\n")
        actual_hash = sha256_file(server_path)

        # Trust store with this hash
        entry = MCPServerEntry(
            name="mcp1", publisher="anthropic",
            expected_sha256=actual_hash, version="1.0",
            signed_at="2026-06-08", signature="sig",
        )
        store = {"mcp1": entry}

        result = validate_mcp_at_boot(
            servers={"mcp1": server_path},
            trust_store=store,
        )
        assert result.valid
        assert "mcp1" in result.validated_servers


def test_validate_unknown_mcp_rejected():
    """Server not in trust store is rejected (typosquatting)."""
    with tempfile.TemporaryDirectory() as d:
        server_path = os.path.join(d, "evil_mcp.py")
        with open(server_path, "w") as f:
            f.write("# malicious server\n")

        result = validate_mcp_at_boot(
            servers={"evil_mcp": server_path},
            trust_store={},  # Empty trust store
        )
        assert not result.valid
        assert "evil_mcp" in result.rejected_servers
        assert any("trust store" in e.lower() for e in result.errors)


def test_validate_hash_mismatch_rejected():
    """Server whose hash doesn't match expected is rejected (tampered)."""
    with tempfile.TemporaryDirectory() as d:
        server_path = os.path.join(d, "mcp2.py")
        with open(server_path, "w") as f:
            f.write("# current content\n")
        # Trust store claims a different hash
        entry = MCPServerEntry(
            name="mcp2", publisher="anthropic",
            expected_sha256="0" * 64, version="1.0",
            signed_at="2026-06-08", signature="sig",
        )
        store = {"mcp2": entry}

        result = validate_mcp_at_boot(
            servers={"mcp2": server_path},
            trust_store=store,
        )
        assert not result.valid
        assert "mcp2" in result.rejected_servers
        assert any("mismatch" in e.lower() for e in result.errors)


def test_validate_untrusted_publisher_rejected():
    with tempfile.TemporaryDirectory() as d:
        server_path = os.path.join(d, "mcp3.py")
        with open(server_path, "w") as f:
            f.write("# content\n")
        h = sha256_file(server_path)
        entry = MCPServerEntry(
            name="mcp3", publisher="evil-publisher",
            expected_sha256=h, version="1.0",
            signed_at="2026-06-08", signature="sig",
        )
        store = {"mcp3": entry}

        result = validate_mcp_at_boot(
            servers={"mcp3": server_path},
            trust_store=store,
        )
        assert not result.valid
        assert "mcp3" in result.rejected_servers
        assert any("untrusted publisher" in e.lower() for e in result.errors)


def test_validate_invalid_signature_rejected():
    with tempfile.TemporaryDirectory() as d:
        server_path = os.path.join(d, "mcp4.py")
        with open(server_path, "w") as f:
            f.write("# content\n")
        h = sha256_file(server_path)
        entry = MCPServerEntry(
            name="mcp4", publisher="anthropic",
            expected_sha256=h, version="1.0",
            signed_at="2026-06-08", signature="INVALID",
        )
        store = {"mcp4": entry}
        signing_key = b"a" * 32

        result = validate_mcp_at_boot(
            servers={"mcp4": server_path},
            trust_store=store,
            signing_key=signing_key,
        )
        assert not result.valid
        assert any("invalid signature" in e.lower() for e in result.errors)


def test_tofu_pin_creates_initial_store():
    """TOFU creates initial trust entries from current state."""
    with tempfile.TemporaryDirectory() as d:
        s1 = os.path.join(d, "s1.py")
        s2 = os.path.join(d, "s2.py")
        with open(s1, "w") as f:
            f.write("# server 1")
        with open(s2, "w") as f:
            f.write("# server 2")

        store = tofu_pin({"s1": s1, "s2": s2})
        assert "s1" in store
        assert "s2" in store
        assert store["s1"].expected_sha256 == sha256_file(s1)
        assert store["s1"].publisher == "ce-harness-internal"


def test_tofu_pin_skips_missing_files():
    with tempfile.TemporaryDirectory() as d:
        s1 = os.path.join(d, "exists.py")
        with open(s1, "w") as f:
            f.write("# exists")
        store = tofu_pin({"exists": s1, "missing": "/nonexistent.py"})
        assert "exists" in store
        assert "missing" not in store


def test_trust_store_persists_across_runs():
    """Save → load → validate works across sessions."""
    with tempfile.TemporaryDirectory() as d:
        server_path = os.path.join(d, "stable.py")
        with open(server_path, "w") as f:
            f.write("# stable content\n")
        h = sha256_file(server_path)

        # First run: TOFU
        store_path = os.path.join(d, "trust.json")
        store = tofu_pin({"stable": server_path})
        save_trust_store(store_path, store)

        # Second run: load + validate
        loaded = load_trust_store(store_path)
        result = validate_mcp_at_boot(
            servers={"stable": server_path},
            trust_store=loaded,
        )
        assert result.valid


def test_default_trusted_publishers_includes_anthropic():
    assert "anthropic" in DEFAULT_TRUSTED_PUBLISHERS


def test_server_modification_detected():
    """Modifying a server after pinning is detected on next boot."""
    with tempfile.TemporaryDirectory() as d:
        server_path = os.path.join(d, "modify.py")
        with open(server_path, "w") as f:
            f.write("# v1 content\n")
        h1 = sha256_file(server_path)
        entry = MCPServerEntry(
            name="modify", publisher="anthropic",
            expected_sha256=h1, version="1.0",
            signed_at="2026-06-08", signature="sig",
        )
        store = {"modify": entry}

        # Server is modified
        with open(server_path, "w") as f:
            f.write("# v2 malicious content\n")

        result = validate_mcp_at_boot(
            servers={"modify": server_path},
            trust_store=store,
        )
        assert not result.valid
        assert any("mismatch" in e.lower() for e in result.errors)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
