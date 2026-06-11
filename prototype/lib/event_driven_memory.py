"""
Event-Driven Memory System
============================
Google's Sessions & Memory architecture: immutable event log + mutable state,
long-term memory consolidation, provenance/confidence tracking.
"""

import json
import time
import hashlib
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class MemoryEvent:
    """Immutable event appended to the session log."""
    event_type: str
    content: Any
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0
    source: str = "agent"

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")


@dataclass
class MemoryBlock:
    """Persistent memory block derived from consolidated events."""
    block_type: str
    content: str
    provenance: str
    confidence: float
    last_updated: float = field(default_factory=time.time)

    def key(self) -> str:
        """Stable key: block_type + content hash."""
        h = hashlib.sha256(self.content.encode()).hexdigest()[:12]
        return f"{self.block_type}:{h}"


class EventDrivenMemory:
    """
    Event-driven memory with immutable log, mutable state, and
    long-term memory consolidation.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._events: List[MemoryEvent] = []
        self._state: Dict[str, Any] = {}
        self._memory_blocks: Dict[str, MemoryBlock] = {}

    # ── Immutable event log ──────────────────────────────────────

    def append_event(
        self,
        event_type: str,
        content: Any,
        confidence: float = 1.0,
        source: str = "agent",
    ) -> MemoryEvent:
        """Append an immutable event to the session log."""
        event = MemoryEvent(
            event_type=event_type,
            content=content,
            timestamp=time.time(),
            confidence=confidence,
            source=source,
        )
        self._events.append(event)
        return event

    @property
    def events(self) -> Tuple[MemoryEvent, ...]:
        """Read-only snapshot of the event log."""
        return tuple(self._events)

    # ── Mutable state ────────────────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        """Derive current state by replaying events, then overlaying
        explicit set_state calls.

        Events of type ``state_update`` with dict content are replayed
        in order so that the latest value per key wins.
        """
        derived: Dict[str, Any] = {}
        for ev in self._events:
            if ev.event_type == "state_update" and isinstance(ev.content, dict):
                derived.update(ev.content)
        # Explicit set_state overrides derived
        derived.update(self._state)
        return derived

    def set_state(self, key: str, value: Any) -> None:
        """Set a mutable state key (overrides any derived value)."""
        self._state[key] = value

    # ── Query ────────────────────────────────────────────────────

    def query_memory(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Keyword search across events and memory blocks. Returns
        up to *top_k* results sorted by relevance score."""
        query_terms = set(query.lower().split())
        results: List[Dict[str, Any]] = []

        # Search events
        for ev in self._events:
            text = f"{ev.event_type} {ev.content}".lower()
            if isinstance(ev.content, dict):
                text = f"{ev.event_type} {' '.join(str(v) for v in ev.content.values())}".lower()
            terms = set(text.split())
            overlap = len(query_terms & terms)
            if overlap > 0:
                score = overlap / max(len(query_terms), 1)
                results.append({
                    "type": "event",
                    "event_type": ev.event_type,
                    "content": ev.content,
                    "confidence": ev.confidence,
                    "source": ev.source,
                    "timestamp": ev.timestamp,
                    "score": round(score, 3),
                })

        # Search memory blocks
        for block in self._memory_blocks.values():
            text = f"{block.block_type} {block.content} {block.provenance}".lower()
            terms = set(text.split())
            overlap = len(query_terms & terms)
            if overlap > 0:
                score = overlap / max(len(query_terms), 1)
                results.append({
                    "type": "memory_block",
                    "block_type": block.block_type,
                    "content": block.content,
                    "confidence": block.confidence,
                    "provenance": block.provenance,
                    "score": round(score, 3),
                })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    # ── Consolidation ────────────────────────────────────────────

    def consolidate(self) -> List[str]:
        """Extract repeated patterns from events into long-term memory
        blocks.  An event type appearing 3+ times is consolidated.

        Returns list of new block keys created.
        """
        # Count event types
        type_counts: Dict[str, List[MemoryEvent]] = {}
        for ev in self._events:
            type_counts.setdefault(ev.event_type, []).append(ev)

        new_keys: List[str] = []
        for etype, evts in type_counts.items():
            if len(evts) < 3:
                continue
            # Build pattern summary from repeated events
            avg_conf = sum(e.confidence for e in evts) / len(evts)
            contents = []
            for e in evts:
                if isinstance(e.content, dict):
                    contents.append(json.dumps(e.content, sort_keys=True))
                else:
                    contents.append(str(e.content))
            summary = f"pattern:{etype} count={len(evts)} samples={contents[:5]}"
            provenance = (
                f"consolidated from {len(evts)} '{etype}' events "
                f"(sources: {', '.join(sorted(set(e.source for e in evts)))})"
            )
            block = MemoryBlock(
                block_type=f"pattern:{etype}",
                content=summary,
                provenance=provenance,
                confidence=round(avg_conf, 3),
            )
            key = block.key()
            if key not in self._memory_blocks:
                self._memory_blocks[key] = block
                new_keys.append(key)

        return new_keys

    # ── Drift detection ──────────────────────────────────────────

    def detect_drift(
        self, baseline_instructions: str, window: int = 10
    ) -> float:
        """Compare keywords in *baseline_instructions* against the last
        *window* events.  Returns a drift score in [0, 1] where 0 means
        perfectly aligned and 1 means completely diverged."""
        baseline_terms = set(baseline_instructions.lower().split())

        recent = self._events[-window:] if self._events else []
        if not recent or not baseline_terms:
            return 0.0

        recent_terms: set = set()
        for ev in recent:
            if isinstance(ev.content, dict):
                for v in ev.content.values():
                    recent_terms.update(str(v).lower().split())
            else:
                recent_terms.update(str(ev.content).lower().split())
            recent_terms.update(ev.event_type.lower().split())

        if not recent_terms:
            return 0.0

        overlap = len(baseline_terms & recent_terms)
        union = len(baseline_terms | recent_terms)
        # Drift = 1 - Jaccard similarity
        return round(1.0 - (overlap / union), 3) if union else 0.0

    # ── Summary / export ─────────────────────────────────────────

    def session_summary(self) -> Dict[str, Any]:
        """Return session stats: event count, state size, memory block
        count, and drift score against an empty baseline."""
        return {
            "session_id": self.session_id,
            "event_count": len(self._events),
            "state_size": len(self.get_state()),
            "memory_block_count": len(self._memory_blocks),
            "drift_score": self.detect_drift("", window=10),
        }

    def export_session(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict of the entire session."""
        return {
            "session_id": self.session_id,
            "events": [asdict(e) for e in self._events],
            "state": self.get_state(),
            "memory_blocks": {
                k: asdict(b) for k, b in self._memory_blocks.items()
            },
        }
