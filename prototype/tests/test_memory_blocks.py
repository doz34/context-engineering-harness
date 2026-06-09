"""Test QW9: Memory Blocks with ACL."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.memory_blocks import MemoryStore, VALID_TYPES


def test_create_block():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        bid = store.create("facts", "user_pref", "language=fr", owner="user:alice")
        assert bid is not None


def test_invalid_type_rejected():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        try:
            store.create("invalid_type", "x", "content", owner="alice")
            assert False
        except ValueError:
            pass


def test_owner_can_read_own_block():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        bid = store.create("facts", "x", "secret content", owner="user:alice")
        assert store.read(bid, "user:alice") == "secret content"


def test_other_principal_cannot_read_without_grant():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        bid = store.create("facts", "x", "secret", owner="user:alice")
        try:
            store.read(bid, "user:bob")
            assert False, "Should raise PermissionError"
        except PermissionError:
            pass


def test_grant_then_read():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        bid = store.create("facts", "x", "shared content", owner="user:alice")
        store.grant(bid, "user:bob", {"read"})
        assert store.read(bid, "user:bob") == "shared content"


def test_revoke():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        bid = store.create("facts", "x", "c", owner="user:alice")
        store.grant(bid, "user:bob", {"read"})
        store.revoke(bid, "user:bob")
        try:
            store.read(bid, "user:bob")
            assert False
        except PermissionError:
            pass


def test_wildcard_acl():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        bid = store.create("facts", "x", "c", owner="user:alice")
        store.grant(bid, "*", {"read"})
        # Any principal can read
        assert store.read(bid, "user:anybody") == "c"
        assert store.read(bid, "phase:P5") == "c"


def test_update_increments_version():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        bid = store.create("facts", "x", "v1", owner="user:alice")
        store.update(bid, "v2", "user:alice")
        # Read returns new content
        assert store.read(bid, "user:alice") == "v2"
        # Version incremented (check via raw SQL if needed)
        import sqlite3
        with sqlite3.connect(store.db_path) as c:
            v = c.execute("SELECT version FROM memory_blocks WHERE id = ?", (bid,)).fetchone()[0]
        assert v == 2


def test_update_requires_write_perm():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        bid = store.create("facts", "x", "c", owner="user:alice")
        # Grant read but not write
        store.grant(bid, "user:bob", {"read"})
        try:
            store.update(bid, "new", "user:bob")
            assert False
        except PermissionError:
            pass


def test_delete_requires_delete_perm():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        bid = store.create("facts", "x", "c", owner="user:alice")
        store.grant(bid, "user:bob", {"read"})
        try:
            store.delete(bid, "user:bob")
            assert False
        except PermissionError:
            pass


def test_list_blocks_filtered_by_principal():
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        store.create("facts", "a", "c1", owner="user:alice")
        store.create("facts", "b", "c2", owner="user:alice")
        b3 = store.create("facts", "c", "c3", owner="user:bob")
        # Alice has read on 2, bob has read on 1
        alice_blocks = store.list_blocks("user:alice")
        bob_blocks = store.list_blocks("user:bob")
        assert len(alice_blocks) == 2
        assert len(bob_blocks) == 1
        assert alice_blocks[0]["owner"] == "user:alice"


def test_tamper_detection():
    """If a block's content is modified outside the API, hash check fails."""
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        bid = store.create("facts", "x", "original", owner="user:alice")
        # Simulate direct DB tampering
        import sqlite3
        with sqlite3.connect(store.db_path) as c:
            c.execute(
                "UPDATE memory_blocks SET content = 'tampered' WHERE id = ?",
                (bid,)
            )
        try:
            store.read(bid, "user:alice")
            assert False, "Should detect tampering"
        except ValueError as e:
            assert "tampered" in str(e).lower()


def test_block_types():
    assert "persona" in VALID_TYPES
    assert "facts" in VALID_TYPES
    assert "episodic" in VALID_TYPES
    assert "semantic" in VALID_TYPES
    assert "procedural" in VALID_TYPES
    assert "scratchpad" in VALID_TYPES


def test_cross_tenant_isolation():
    """Tenant alice cannot see tenant bob's blocks."""
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(os.path.join(d, "memory.db"))
        alice_block = store.create("facts", "alice_secret", "alice data", owner="user:alice")
        bob_block = store.create("facts", "bob_secret", "bob data", owner="user:bob")
        # Alice can read her own
        assert store.read(alice_block, "user:alice") == "alice data"
        # Bob can read his own
        assert store.read(bob_block, "user:bob") == "bob data"
        # Alice cannot read bob's
        try:
            store.read(bob_block, "user:alice")
            assert False
        except PermissionError:
            pass


def test_memory_store_persists_across_instances():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "memory.db")
        s1 = MemoryStore(path)
        bid = s1.create("facts", "x", "persistent", owner="user:alice")
        s2 = MemoryStore(path)
        assert s2.read(bid, "user:alice") == "persistent"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
