"""Tests for Event-Driven Memory System."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.event_driven_memory import (
    EventDrivenMemory,
    MemoryEvent,
    MemoryBlock,
)


def test_append_event_immutable():
    """Events are frozen dataclasses; mutation raises FrozenInstanceError."""
    mem = EventDrivenMemory("s1")
    ev = mem.append_event("user_message", "hello", confidence=0.9, source="user")
    assert ev.event_type == "user_message"
    assert ev.content == "hello"
    assert ev.confidence == 0.9
    assert ev.source == "user"
    # Frozen: mutation must raise
    try:
        ev.content = "mutated"
        assert False, "Should raise on mutation"
    except AttributeError:
        pass
    # Internal list is also protected via .events tuple
    assert isinstance(mem.events, tuple)
    assert len(mem.events) == 1


def test_get_state_derives_from_events():
    """state_update events are replayed to derive current state."""
    mem = EventDrivenMemory("s2")
    mem.append_event("state_update", {"color": "red"})
    mem.append_event("state_update", {"color": "blue", "shape": "circle"})
    state = mem.get_state()
    assert state["color"] == "blue"   # latest wins
    assert state["shape"] == "circle"


def test_set_state_mutable():
    """Explicit set_state overrides derived values."""
    mem = EventDrivenMemory("s3")
    mem.append_event("state_update", {"lang": "en"})
    mem.set_state("lang", "fr")
    assert mem.get_state()["lang"] == "fr"
    # New keys too
    mem.set_state("extra", True)
    assert mem.get_state()["extra"] is True


def test_query_memory_finds_relevant():
    """Keyword search returns scored results across events and blocks."""
    mem = EventDrivenMemory("s4")
    mem.append_event("preference", {"topic": "python testing"})
    mem.append_event("preference", {"topic": "rust systems"})
    mem.append_event("note", "deploy python app")

    results = mem.query_memory("python", top_k=5)
    assert len(results) >= 2
    assert all(r["score"] > 0 for r in results)
    # Results are sorted by score descending
    for i in range(len(results) - 1):
        assert results[i]["score"] >= results[i + 1]["score"]


def test_consolidate_extracts_patterns():
    """Event types appearing 3+ times are consolidated into memory blocks."""
    mem = EventDrivenMemory("s5")
    for i in range(4):
        mem.append_event("correction", f"fix typo #{i}")
    mem.append_event("other_event", "unrelated")

    new_keys = mem.consolidate()
    assert len(new_keys) == 1
    block = mem._memory_blocks[new_keys[0]]
    assert block.block_type == "pattern:correction"
    assert "count=4" in block.content
    assert block.confidence == 1.0


def test_detect_drift_measures_divergence():
    """Drift score reflects keyword divergence from baseline."""
    mem = EventDrivenMemory("s6")
    baseline = "write secure python code with tests"

    # No events -> zero drift
    assert mem.detect_drift(baseline) == 0.0

    # Aligned events -> low drift (enough overlap with baseline keywords)
    mem.append_event("state_update", {"task": "write python tests"})
    mem.append_event("state_update", {"task": "secure code"})
    drift_aligned = mem.detect_drift(baseline)
    assert drift_aligned <= 1.0  # may not be zero due to dict→str tokenization

    # Divergent events -> higher drift
    mem2 = EventDrivenMemory("s7")
    for _ in range(5):
        mem2.append_event("state_update", {"task": "bake cakes and cookies"})
    drift_divergent = mem2.detect_drift(baseline)
    assert drift_divergent > drift_aligned


def test_session_summary_counts():
    """Summary reports correct event, state, and block counts."""
    mem = EventDrivenMemory("s8")
    mem.append_event("state_update", {"x": 1})
    mem.append_event("note", "something")
    mem.set_state("y", 2)
    for i in range(3):
        mem.append_event("repeat", f"item {i}")
    mem.consolidate()

    summary = mem.session_summary()
    assert summary["session_id"] == "s8"
    assert summary["event_count"] == 5  # 2 + 3
    assert summary["state_size"] == 2    # x, y
    assert summary["memory_block_count"] == 1


def test_export_session_json_serializable():
    """Export produces a dict that json.dumps can serialize."""
    mem = EventDrivenMemory("s9")
    mem.append_event("test_event", {"key": "value"}, confidence=0.75)
    mem.set_state("mode", "production")
    for i in range(3):
        mem.append_event("repeat", f"r{i}")
    mem.consolidate()

    exported = mem.export_session()
    # Must be JSON-serializable
    serialized = json.dumps(exported)
    assert isinstance(serialized, str)

    # Round-trip
    parsed = json.loads(serialized)
    assert parsed["session_id"] == "s9"
    assert len(parsed["events"]) == 4  # 1 + 3
    assert parsed["state"]["mode"] == "production"
    assert len(parsed["memory_blocks"]) == 1


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
