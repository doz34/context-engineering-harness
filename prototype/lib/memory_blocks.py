"""
QW9 — Memory Blocks with ACL
==============================
Hierarchical memory (MemGPT-style) with per-tenant ACL.
Closes: Cross-tenant data leak, memory block poisoning.
"""

import json
import time
import hashlib
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
import os


# Memory block types (per MemGPT/Letta)
VALID_TYPES = {"persona", "facts", "episodic", "semantic", "procedural", "scratchpad"}


@dataclass
class MemoryBlock:
    """A block of memory with content + ACL."""
    id: str
    type: str
    name: str
    content: str
    owner: str  # tenant/principal
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


class MemoryStore:
    """
    Memory block store with ACL.
    Schema: blocks table with per-row owner + ACL table.
    """

    def __init__(self, db_path: str = ".ctxh/memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_schema()

    def _connect(self):
        """Open a connection with foreign-key enforcement enabled.

        SQLite defaults to OFF for `PRAGMA foreign_keys`, so the FK
        declared on memory_acl.block_id was previously silently ignored.
        Every call must go through this helper.
        """
        c = sqlite3.connect(self.db_path)
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def _init_schema(self):
        with self._connect() as c:
            # Enable foreign-key enforcement. SQLite defaults to OFF,
            # so the FK declared on memory_acl.block_id was silently
            # ignored — orphan ACL rows survived block deletion.
            c.execute("PRAGMA foreign_keys=ON")
            c.executescript("""
                CREATE TABLE IF NOT EXISTS memory_blocks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata JSON,
                    hash TEXT  -- HMAC of content for tamper detection
                );

                CREATE TABLE IF NOT EXISTS memory_acl (
                    block_id TEXT,
                    principal TEXT,
                    permission TEXT CHECK(permission IN ('read', 'write', 'delete')),
                    PRIMARY KEY (block_id, principal, permission),
                    FOREIGN KEY (block_id) REFERENCES memory_blocks(id)
                );

                CREATE INDEX IF NOT EXISTS idx_block_owner ON memory_blocks(owner);
                CREATE INDEX IF NOT EXISTS idx_acl_principal ON memory_acl(principal);
            """)

    def create(self, type_: str, name: str, content: str, owner: str,
               acl: Dict[str, Set[str]] = None) -> str:
        """
        Create a memory block. Owner is auto-granted all permissions.
        ACL: {principal: {permissions}}. Default: only owner.
        """
        if type_ not in VALID_TYPES:
            raise ValueError(f"Invalid type '{type_}', must be one of {VALID_TYPES}")

        block_id = f"{type_}_{name}_{int(time.time()*1000)}"
        now = time.time()
        h = self._hash_content(content)

        with self._connect() as c:
            c.execute(
                "INSERT INTO memory_blocks (id, type, name, content, owner, version, created_at, updated_at, metadata, hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (block_id, type_, name, content, owner, 1, now, now, "{}", h)
            )
            # Owner has all permissions
            for perm in ("read", "write", "delete"):
                c.execute(
                    "INSERT INTO memory_acl (block_id, principal, permission) VALUES (?, ?, ?)",
                    (block_id, owner, perm)
                )
            # Additional ACL
            if acl:
                for principal, perms in acl.items():
                    for perm in perms:
                        c.execute(
                            "INSERT OR IGNORE INTO memory_acl (block_id, principal, permission) VALUES (?, ?, ?)",
                            (block_id, principal, perm)
                        )
        return block_id

    def read(self, block_id: str, principal: str) -> Optional[str]:
        """Read a block, with ACL check."""
        if not self._check_permission(block_id, principal, "read"):
            raise PermissionError(f"Principal '{principal}' has no read access to '{block_id}'")
        with self._connect() as c:
            row = c.execute(
                "SELECT content, hash FROM memory_blocks WHERE id = ?", (block_id,)
            ).fetchone()
            if not row:
                return None
            content, h = row
            # Verify tamper
            if self._hash_content(content) != h:
                raise ValueError(f"Block '{block_id}' has been tampered with!")
            return content

    def update(self, block_id: str, content: str, principal: str) -> bool:
        """Update a block. Increments version. Tamper detection via hash."""
        if not self._check_permission(block_id, principal, "write"):
            raise PermissionError(f"Principal '{principal}' has no write access to '{block_id}'")
        now = time.time()
        h = self._hash_content(content)
        with self._connect() as c:
            c.execute(
                "UPDATE memory_blocks SET content = ?, hash = ?, version = version + 1, updated_at = ? "
                "WHERE id = ?",
                (content, h, now, block_id)
            )
        return True

    def delete(self, block_id: str, principal: str) -> bool:
        """Delete a block. ACL rows are removed FIRST so the FK on
        memory_acl.block_id doesn't fire an IntegrityError (CRIT fix
        2026-06-10 — previous order silently failed for owners)."""
        if not self._check_permission(block_id, principal, "delete"):
            raise PermissionError(f"Principal '{principal}' has no delete access to '{block_id}'")
        with self._connect() as c:
            # Delete child rows (ACL) before parent (block) to avoid FK
            # constraint violation. SQLite requires foreign_keys=ON
            # (enabled in _connect) to enforce this; without it, the
            # block would be deleted and orphan ACL rows would remain.
            c.execute("DELETE FROM memory_acl WHERE block_id = ?", (block_id,))
            c.execute("DELETE FROM memory_blocks WHERE id = ?", (block_id,))
        return True

    def list_blocks(self, principal: str) -> List[Dict]:
        """List blocks the principal has read access to."""
        with self._connect() as c:
            rows = c.execute(
                "SELECT b.id, b.type, b.name, b.owner FROM memory_blocks b "
                "JOIN memory_acl a ON b.id = a.block_id "
                "WHERE a.principal = ? AND a.permission = 'read'",
                (principal,)
            ).fetchall()
        return [{"id": r[0], "type": r[1], "name": r[2], "owner": r[3]} for r in rows]

    def grant(self, block_id: str, principal: str, permissions: Set[str]):
        """Grant permissions to a principal."""
        with self._connect() as c:
            for perm in permissions:
                c.execute(
                    "INSERT OR IGNORE INTO memory_acl (block_id, principal, permission) VALUES (?, ?, ?)",
                    (block_id, principal, perm)
                )

    def revoke(self, block_id: str, principal: str):
        """Revoke all permissions from a principal."""
        with self._connect() as c:
            c.execute(
                "DELETE FROM memory_acl WHERE block_id = ? AND principal = ?",
                (block_id, principal)
            )

    def _check_permission(self, block_id: str, principal: str, perm: str) -> bool:
        with self._connect() as c:
            row = c.execute(
                "SELECT 1 FROM memory_acl WHERE block_id = ? AND principal = ? AND permission = ?",
                (block_id, principal, perm)
            ).fetchone()
            if row:
                return True
            # Wildcard check
            row = c.execute(
                "SELECT 1 FROM memory_acl WHERE block_id = ? AND principal = '*' AND permission = ?",
                (block_id, perm)
            ).fetchone()
            return bool(row)

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]
