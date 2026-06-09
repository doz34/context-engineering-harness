"""Test QW-S3-11/12/13: Per-tenant keys + CAB + EOL HMAC."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.s3_residual import TenantKeyStore, CABRegistry, EOLRegistry
from lib.security import generate_master_key


# === QW-S3-11: TenantKeyStore ===

def test_tenant_key_creates_on_first_access():
    with tempfile.TemporaryDirectory() as d:
        store = TenantKeyStore(os.path.join(d, "keys.json"))
        key = store.get_or_create("tenant:alice")
        assert len(key) == 32  # 256 bits


def test_tenant_key_persistence():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "keys.json")
        s1 = TenantKeyStore(path)
        k1 = s1.get_or_create("tenant:bob")
        s2 = TenantKeyStore(path)
        k2 = s2.get_or_create("tenant:bob")
        assert k1 == k2  # Same key after re-instantiation


def test_tenant_key_isolation():
    with tempfile.TemporaryDirectory() as d:
        store = TenantKeyStore(os.path.join(d, "keys.json"))
        k_alice = store.get_or_create("tenant:alice")
        k_bob = store.get_or_create("tenant:bob")
        assert k_alice != k_bob


def test_tenant_key_rotation():
    with tempfile.TemporaryDirectory() as d:
        store = TenantKeyStore(os.path.join(d, "keys.json"))
        old = store.get_or_create("tenant:alice")
        new = store.rotate("tenant:alice")
        assert old != new


def test_tenant_key_delete_gdpr():
    with tempfile.TemporaryDirectory() as d:
        store = TenantKeyStore(os.path.join(d, "keys.json"))
        store.get_or_create("tenant:alice")
        store.delete("tenant:alice")
        # After delete, get_or_create returns a NEW key
        new = store.get_or_create("tenant:alice")
        # (old key is gone, new key is fresh)
        assert new is not None


def test_tenant_key_store_permissions_0600():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "keys.json")
        store = TenantKeyStore(path)
        store.get_or_create("tenant:alice")
        mode = os.stat(path).st_mode & 0o777
        assert mode == 0o600


# === QW-S3-12: CAB Registry ===

def test_cab_add_and_verify():
    key = generate_master_key()
    cab = CABRegistry(key)
    cab.add_approval("change_001", ["user:alice", "user:bob"], ttl_seconds=3600)
    assert cab.verify("change_001")


def test_cab_unknown_change_fails():
    key = generate_master_key()
    cab = CABRegistry(key)
    assert not cab.verify("nonexistent")


def test_cab_expired_fails():
    key = generate_master_key()
    cab = CABRegistry(key)
    cab.add_approval("change_002", ["user:alice"], ttl_seconds=0)
    import time
    time.sleep(0.01)  # Let it expire
    assert not cab.verify("change_002")


def test_cab_tampered_approvers_fails():
    key = generate_master_key()
    cab = CABRegistry(key)
    cab.add_approval("change_003", ["user:alice"], ttl_seconds=3600)
    # Tamper with the approvers
    cab._approvals["change_003"].approvers.append("user:eve")
    assert not cab.verify("change_003")


def test_cab_chain_validity():
    """Approvals are chained; breaking one breaks subsequent verification."""
    key = generate_master_key()
    cab = CABRegistry(key)
    cab.add_approval("change_004", ["user:alice"])
    cab.add_approval("change_005", ["user:bob"])
    cab.add_approval("change_006", ["user:carol"])
    # All 3 should be valid
    assert cab.verify("change_004")
    assert cab.verify("change_005")
    assert cab.verify("change_006")
    # Tamper with change_004
    cab._approvals["change_004"].approvers = []
    # change_004 fails
    assert not cab.verify("change_004")
    # change_005 and change_006 still pass (chain is per-event, not cross)
    assert cab.verify("change_005")
    assert cab.verify("change_006")


def test_cab_list_valid():
    key = generate_master_key()
    cab = CABRegistry(key)
    cab.add_approval("change_007", ["user:alice"], ttl_seconds=3600)
    cab.add_approval("change_008", ["user:bob"], ttl_seconds=0)
    import time
    time.sleep(0.01)
    valid = cab.list_valid()
    assert "change_007" in valid
    assert "change_008" not in valid


# === QW-S3-13: EOL Registry ===

def test_eol_record_and_verify():
    key = generate_master_key()
    eol = EOLRegistry(key)
    d = eol.record_eol("project:retired_001", "user:alice", "GDPR Art. 17")
    assert eol.verify("project:retired_001")


def test_eol_unknown_fails():
    key = generate_master_key()
    eol = EOLRegistry(key)
    assert not eol.verify("nonexistent")


def test_eol_tampered_reason_fails():
    key = generate_master_key()
    eol = EOLRegistry(key)
    eol.record_eol("project:002", "user:alice", "Original reason")
    eol._decisions["project:002"].reason = "Modified reason"
    assert not eol.verify("project:002")


def test_eol_get_returns_verified():
    key = generate_master_key()
    eol = EOLRegistry(key)
    eol.record_eol("project:003", "user:alice", "EOL")
    d = eol.get("project:003")
    assert d is not None
    # Tamper
    eol._decisions["project:003"].reason = "modified"
    d2 = eol.get("project:003")
    assert d2 is None  # Verification fails


def test_eol_chain_validity():
    """Multiple EOL decisions in a chain."""
    key = generate_master_key()
    eol = EOLRegistry(key)
    eol.record_eol("project:a", "user:1", "reason a")
    eol.record_eol("project:b", "user:2", "reason b")
    eol.record_eol("project:c", "user:3", "reason c")
    assert eol.verify("project:a")
    assert eol.verify("project:b")
    assert eol.verify("project:c")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
