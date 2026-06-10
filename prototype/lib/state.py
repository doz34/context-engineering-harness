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
        """Record a token event, return current phase total.

        Raises ValueError if `tokens` is negative or non-integer (F-003
        audit 2026-06-10). Without this check, a sub-agent or bug could
        call `record_token(-999999)` to silently decrement the phase
        budget and bypass the soft/hard cap enforcement.
        """
        if not isinstance(tokens, int) or isinstance(tokens, bool):
            raise ValueError(
                f"tokens must be int, got {type(tokens).__name__}: {tokens!r}"
            )
        if tokens < 0:
            raise ValueError(
                f"tokens must be >= 0 (got {tokens}). Negative events would "
                f"decrement the phase budget and bypass soft/hard caps."
            )
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
        QW-S3-8: Uses RotatingHMAC for *epoch compartmentalization*
        (NOT forward secrecy in the crypto sense — see RotatingHMAC
        docstring; relabeled 2026-06-10 after adversarial review).

        The read-prev-hash and insert-new-event are now wrapped in a
        single BEGIN/COMMIT transaction to prevent TOCTOU races between
        concurrent appenders (the previous two-`with` layout left a
        window where a parallel writer could fork the chain).
        """
        import hashlib
        import logging
        # Try to use RotatingHMAC (QW-S3-8)
        rh = None
        try:
            from lib.security import RotatingHMAC, load_or_create_master_key
            key = load_or_create_master_key(self.path + ".master")
            rh = RotatingHMAC(key)
        except (ImportError, AttributeError) as e:
            # F-011 audit 2026-06-10: was `except (..., Exception)` which
            # swallowed ALL errors silently. Now narrow + log so the
            # fallback is observable.
            logging.getLogger(__name__).warning(
                "RotatingHMAC unavailable, falling back to legacy SHA-256 "
                "audit chain (no forward secrecy): %s",
                e,
            )
            rh = None

        with self.conn() as c:
            # Single transaction: read prev_hash (if not given), sign, insert.
            # SQLite serializes writes at the database level; BEGIN ensures
            # the read and the insert are not interleaved with another writer.
            c.execute("BEGIN IMMEDIATE")
            try:
                if not prev_hash:
                    row = c.execute(
                        "SELECT hash FROM audit_event ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    prev_hash = row[0] if row else ""

                if rh is not None:
                    event = rh.sign(
                        payload=json.dumps(payload),
                        prev_hash=prev_hash,
                    )
                    h = event["hash"]
                    c.execute(
                        "INSERT INTO audit_event (ts, event_type, payload, prev_hash, hash) "
                        "VALUES (datetime('now'), ?, ?, ?, ?)",
                        (event_type, json.dumps({
                            "payload": payload,
                            "ts": event["ts"],
                            "epoch_id": event["epoch_id"],
                        }), prev_hash, h)
                    )
                else:
                    # Fallback: simple SHA-256 (legacy mode)
                    event = {
                        "ts": "datetime('now')",
                        "type": event_type,
                        "payload": payload,
                        "prev_hash": prev_hash,
                    }
                    content = json.dumps(event, sort_keys=True).encode()
                    h = hashlib.sha256(content).hexdigest()
                    c.execute(
                        "INSERT INTO audit_event (ts, event_type, payload, prev_hash, hash) "
                        "VALUES (datetime('now'), ?, ?, ?, ?)",
                        (event_type, json.dumps(payload), prev_hash, h)
                    )
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return h

    def verify_audit_chain(
        self,
        master_key_path: Optional[str] = None,
        strict_epoch: bool = True,
    ) -> dict:
        """Walk the audit_event table and verify HMAC chain integrity (F-004).

        Returns a dict with keys:
          - `ok` (bool): True if the entire chain is valid
          - `checked` (int): number of events verified
          - `first_invalid_id` (int or None): id of first broken event
          - `reason` (str or None): human-readable failure cause
          - `fallback` (bool): True if RotatingHMAC was unavailable and the
            legacy SHA-256 chain was checked instead (no forward secrecy)

        The check is end-to-end:
          1. Each event's hash is recomputed from (ts, epoch_id, payload,
             prev_hash) using the epoch-specific derived key.
          2. Each event's `prev_hash` must equal the previous event's
             `hash` (chain integrity).
          3. If `strict_epoch=True` (default), the event's `epoch_id` must
             be within the current or previous epoch (rejects pre-computed
             forgeries from the far past or future).

        Limitations:
          - Requires `audit_event.payload` to be JSON-encoded with `payload`,
            `ts`, `epoch_id` keys (the RotatingHMAC mode). Events written by
            the legacy SHA-256 fallback path are not verifiable with the
            rotating key and will be reported as `fallback=True`.
          - The chain is append-only; there is no recovery from tampering
            other than rejecting the chain (`ok=False`).
        """
        result = {
            "ok": True,
            "checked": 0,
            "first_invalid_id": None,
            "reason": None,
            "fallback": False,
        }
        # Try to obtain RotatingHMAC
        rh = None
        try:
            from lib.security import RotatingHMAC, load_or_create_master_key
            key_path = master_key_path or (self.path + ".master")
            key = load_or_create_master_key(key_path)
            rh = RotatingHMAC(key)
        except (ImportError, AttributeError):
            result["fallback"] = True
            result["reason"] = (
                "RotatingHMAC unavailable; cannot perform epoch-aware "
                "verification. Re-run with `cryptography` installed."
            )
            return result

        with self.conn() as c:
            rows = c.execute(
                "SELECT id, payload, prev_hash, hash FROM audit_event "
                "ORDER BY id ASC"
            ).fetchall()

        prev_hash_expected = ""
        for row in rows:
            rid, payload_blob, prev_hash, hash_value = row
            try:
                # payload is JSON-encoded {payload, ts, epoch_id}
                payload_dict = json.loads(payload_blob)
                epoch_id = int(payload_dict.get("epoch_id", "0"))
                ts = str(payload_dict.get("ts", ""))
                # F-004 audit 2026-06-10: the signed event used
                # `json.dumps(payload)` — a string — but the stored
                # `payload` column holds the raw dict. To match what was
                # actually HMAC'd, re-serialize here (sort_keys=True so
                # the order is deterministic).
                raw_payload = payload_dict.get("payload", "")
                if isinstance(raw_payload, dict):
                    inner_payload = json.dumps(raw_payload, sort_keys=True)
                else:
                    inner_payload = str(raw_payload)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                result.update({
                    "ok": False,
                    "first_invalid_id": rid,
                    "reason": f"Malformed payload JSON: {e}",
                })
                return result

            # Reconstruct event and verify. F-004 audit 2026-06-10:
            # we MUST include the `hash` field from the DB row, otherwise
            # `rh.verify` will compare the recomputed hash against "" and
            # the chain will always appear broken.
            event = {
                "ts": ts,
                "epoch_id": str(epoch_id),
                "payload": inner_payload,
                "prev_hash": prev_hash,
                "hash": hash_value,
            }
            if not rh.verify(event, strict_epoch=strict_epoch):
                result.update({
                    "ok": False,
                    "first_invalid_id": rid,
                    "reason": (
                        f"HMAC mismatch or epoch out of range "
                        f"(epoch_id={epoch_id}, strict={strict_epoch})"
                    ),
                })
                return result

            # Chain integrity: prev_hash must match previous row's hash
            if prev_hash != prev_hash_expected:
                result.update({
                    "ok": False,
                    "first_invalid_id": rid,
                    "reason": (
                        f"Chain break: prev_hash={prev_hash!r} != "
                        f"expected {prev_hash_expected!r}"
                    ),
                })
                return result
            prev_hash_expected = hash_value
            result["checked"] += 1

        return result
