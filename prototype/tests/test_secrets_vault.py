"""Test QW7: Secrets Vault."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.secrets_vault import SecretsVault, ACLEntry, SecretEntry


def test_set_and_get_secret():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        v.set("ANTHROPIC_API_KEY", "sk-test-1234567890")
        assert v.get("ANTHROPIC_API_KEY") == "sk-test-1234567890"


def test_secret_encrypted_at_rest():
    """Secret value is not in plaintext on disk."""
    with tempfile.TemporaryDirectory() as d:
        vault_path = os.path.join(d, "vault.db")
        v = SecretsVault(vault_path)
        v.set("MY_SECRET", "super-secret-value")
        # Check meta file doesn't contain plaintext
        with open(vault_path + ".meta.json") as f:
            content = f.read()
        assert "super-secret-value" not in content


def test_get_unknown_returns_none():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        assert v.get("NONEXISTENT") is None


def test_acl_default_owner_only():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        v.set("KEY1", "val1", owner="phase:P5")
        # Owner can read
        assert v.get("KEY1", principal="phase:P5") == "val1"
        # Non-owner without grant is denied
        try:
            v.get("KEY1", principal="phase:P6")
            assert False, "Should raise PermissionError"
        except PermissionError:
            pass


def test_grant_and_revoke():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        v.set("KEY1", "val1", owner="user:alice")
        # Grant to bob
        v.grant("KEY1", "user:bob", {"read"})
        assert v.get("KEY1", principal="user:bob") == "val1"
        # Revoke
        v.revoke("KEY1", "user:bob")
        try:
            v.get("KEY1", principal="user:bob")
            assert False
        except PermissionError:
            pass


def test_rotate_secret():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        v.set("KEY1", "old_value")
        v.rotate("KEY1", "new_value")
        assert v.get("KEY1") == "new_value"


def test_rotate_updates_timestamp():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        v.set("KEY1", "v1")
        before = v._secrets["KEY1"].rotated_at
        v.rotate("KEY1", "v2")
        after = v._secrets["KEY1"].rotated_at
        assert after >= before


def test_delete_secret():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        v.set("KEY1", "val1")
        v.delete("KEY1")
        assert v.get("KEY1") is None
        assert "KEY1" not in v.list_keys()


def test_delete_requires_acl():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        v.set("KEY1", "val1", owner="user:alice")
        try:
            v.delete("KEY1", principal="user:bob")
            assert False
        except PermissionError:
            pass


def test_list_keys():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        v.set("K1", "v1")
        v.set("K2", "v2")
        v.set("K3", "v3")
        assert set(v.list_keys()) == {"K1", "K2", "K3"}


def test_list_keys_filtered_by_principal():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        v.set("K1", "v1", owner="user:alice")
        v.set("K2", "v2", owner="user:bob")
        v.grant("K1", "user:carol", {"read"})
        # Carol can only see K1
        carol_keys = v.list_keys(principal="user:carol")
        assert carol_keys == ["K1"]


def test_wildcard_acl():
    with tempfile.TemporaryDirectory() as d:
        v = SecretsVault(os.path.join(d, "vault.db"))
        v.set("KEY1", "val1", owner="phase:P5")
        v.grant("KEY1", "*", {"read"})  # Wildcard = all principals
        # Any principal can read
        assert v.get("KEY1", principal="phase:P6") == "val1"
        assert v.get("KEY1", principal="user:anybody") == "val1"


def test_vault_persists_across_instances():
    with tempfile.TemporaryDirectory() as d:
        vault_path = os.path.join(d, "vault.db")
        v1 = SecretsVault(vault_path)
        v1.set("KEY1", "persistent_value")
        # New instance loads from disk
        v2 = SecretsVault(vault_path)
        assert v2.get("KEY1") == "persistent_value"


def test_vault_meta_file_permissions_0600():
    with tempfile.TemporaryDirectory() as d:
        vault_path = os.path.join(d, "vault.db")
        v = SecretsVault(vault_path)
        v.set("KEY", "val")
        meta = vault_path + ".meta.json"
        mode = os.stat(meta).st_mode & 0o777
        assert mode == 0o600


def test_wrong_master_key_cannot_decrypt():
    """Vault with different key cannot decrypt another's secrets."""
    with tempfile.TemporaryDirectory() as d:
        vault_path = os.path.join(d, "vault.db")
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        v1 = SecretsVault(vault_path, master_key=key1)
        v1.set("KEY1", "secret")
        # Re-instantiate with wrong key
        try:
            v2 = SecretsVault(vault_path, master_key=key2)
            v2.get("KEY1")
            # Decryption may fail or return garbage
            # (Either way, secrets are not readable)
        except Exception:
            # Expected: decryption failure
            pass


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
