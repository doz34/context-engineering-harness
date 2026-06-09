"""
CE-Harness State Manager
========================
SQLite WAL-based state. Schema documented in design/00-architecture.md.
"""

import sqlite3
import json
import os
from contextlib import contextmanager
from typing import Optional, Iterator


class StateDB:
    """SQLite state with WAL, atomic operations."""

    def __init__(self, path: str = ".ctxh/state.db"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._init_schema()

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        """Context manager for connections."""
        c = sqlite3.connect(self.path, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
        finally:
            c.close()

    def _init_schema(self):
        """Create tables if not exist."""
        with self.conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS session (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    current_phase TEXT,
                    metadata JSON
                );

                CREATE TABLE IF NOT EXISTS phase (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    status TEXT DEFAULT 'active',
                    budget_soft_cap INTEGER,
                    budget_hard_cap INTEGER,
                    tokens_used INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS token_event (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    phase_id TEXT,
                    component TEXT,
                    direction TEXT,
                    tokens INTEGER,
                    model TEXT,
                    agent TEXT,
                    metadata JSON
                );

                CREATE INDEX IF NOT EXISTS idx_token_phase
                    ON token_event(phase_id, ts);

                CREATE TABLE IF NOT EXISTS audit_event (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    event_type TEXT,
                    payload JSON,
                    prev_hash TEXT,
                    hash TEXT
                );
            """)

    def start_session(self, session_id: str, metadata: dict = None) -> None:
        """Start or replace a session."""
        with self.conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO session (id, started_at, status, metadata) "
                "VALUES (?, datetime('now'), 'active', ?)",
                (session_id, json.dumps(metadata or {}))
            )

    def start_phase(self, phase_id: str, session_id: str, name: str,
                    soft_cap: int, hard_cap: int) -> None:
        """Start a phase with token budget."""
        with self.conn() as c:
            c.execute(
                "INSERT INTO phase (id, session_id, name, started_at, "
                "budget_soft_cap, budget_hard_cap) "
                "VALUES (?, ?, ?, datetime('now'), ?, ?)",
                (phase_id, session_id, name, soft_cap, hard_cap)
            )

    def end_phase(self, phase_id: str, status: str = "complete") -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE phase SET ended_at = datetime('now'), status = ? "
                "WHERE id = ?",
                (status, phase_id)
            )

    def record_token(self, phase_id: str, component: str,
                     direction: str, tokens: int,
                     model: str = "", agent: str = "",
                     metadata: dict = None) -> int:
        """Record a token event, return current phase total."""
        with self.conn() as c:
            c.execute(
                "INSERT INTO token_event (ts, phase_id, component, direction, "
                "tokens, model, agent, metadata) "
                "VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?)",
                (phase_id, component, direction, tokens,
                 model, agent, json.dumps(metadata or {}))
            )
            c.execute(
                "UPDATE phase SET tokens_used = tokens_used + ? WHERE id = ?",
                (tokens, phase_id)
            )
            row = c.execute(
                "SELECT tokens_used FROM phase WHERE id = ?", (phase_id,)
            ).fetchone()
            return row[0] if row else 0

    def phase_total(self, phase_id: str) -> int:
        with self.conn() as c:
            row = c.execute(
                "SELECT tokens_used FROM phase WHERE id = ?", (phase_id,)
            ).fetchone()
            return row[0] if row else 0

    def phase_budget(self, phase_id: str) -> tuple[int, int]:
        """Return (soft_cap, hard_cap)."""
        with self.conn() as c:
            row = c.execute(
                "SELECT budget_soft_cap, budget_hard_cap FROM phase WHERE id = ?",
                (phase_id,)
            ).fetchone()
            return (row[0], row[1]) if row else (0, 0)

    def top_components(self, phase_id: str, limit: int = 5) -> list[tuple[str, int]]:
        """Get top N components by token usage."""
        with self.conn() as c:
            rows = c.execute(
                "SELECT component, SUM(tokens) as total "
                "FROM token_event WHERE phase_id = ? "
                "GROUP BY component ORDER BY total DESC LIMIT ?",
                (phase_id, limit)
            ).fetchall()
            return rows

    def append_audit(self, event_type: str, payload: dict,
                     prev_hash: str = "") -> str:
        """
        Append audit event, return hash.
        QW-S3-8: Uses RotatingHMAC for forward secrecy.
        """
        import hashlib
        # Try to use RotatingHMAC (QW-S3-8)
        rh = None
        try:
            from lib.security import RotatingHMAC, load_or_create_master_key
            key = load_or_create_master_key(self.path + ".master")
            rh = RotatingHMAC(key)
        except (ImportError, AttributeError, Exception):
            rh = None

        if rh is not None:
            # Use RotatingHMAC
            with self.conn() as c:
                if not prev_hash:
                    row = c.execute(
                        "SELECT hash FROM audit_event ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    prev_hash = row[0] if row else ""
            # Sign with RotatingHMAC
            event = rh.sign(
                payload=json.dumps(payload),
                prev_hash=prev_hash,
            )
            h = event["hash"]
            # Store the full signed event (with epoch_id for verification)
            with self.conn() as c:
                c.execute(
                    "INSERT INTO audit_event (ts, event_type, payload, prev_hash, hash) "
                    "VALUES (datetime('now'), ?, ?, ?, ?)",
                    (event_type, json.dumps({
                        "payload": payload,
                        "ts": event["ts"],
                        "epoch_id": event["epoch_id"],
                    }), prev_hash, h)
                )
            return h
        else:
            # Fallback: simple SHA-256 (legacy mode)
            event = {
                "ts": "datetime('now')",
                "type": event_type,
                "payload": payload,
                "prev_hash": prev_hash,
            }
            with self.conn() as c:
                if not prev_hash:
                    row = c.execute(
                        "SELECT hash FROM audit_event ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    prev_hash = row[0] if row else ""
                    event["prev_hash"] = prev_hash
            content = json.dumps(event, sort_keys=True).encode()
            h = hashlib.sha256(content).hexdigest()
            with self.conn() as c:
                c.execute(
                    "INSERT INTO audit_event (ts, event_type, payload, prev_hash, hash) "
                    "VALUES (datetime('now'), ?, ?, ?, ?)",
                    (event_type, json.dumps(payload), prev_hash, h)
                )
            return h
