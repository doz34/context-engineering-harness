"""Test ACE-style Compaction."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.ace_compact import ACECompact, CompactionItem


def test_preserve_critical_items():
    """Decisions and constraints must be preserved at any cost."""
    compact = ACECompact(target_budget=2000)

    items = [
        CompactionItem(kind="event", content="Phase started", importance=2),
        CompactionItem(kind="decision", content="Use 5K budget for P3", importance=4),
        CompactionItem(kind="constraint", content="Must validate NFRs", importance=4),
        CompactionItem(kind="tool_result", content="some long output " * 100, importance=1),
    ]

    result = compact.compact(items)
    kinds = [it.kind for it in result["items"]]
    assert "decision" in kinds
    assert "constraint" in kinds


def test_deduplicate_similar_content():
    """Same content should be deduped."""
    compact = ACECompact(target_budget=5000)

    items = [
        CompactionItem(kind="event", content="Phase P3 started at 10:00", importance=2),
        CompactionItem(kind="event", content="Phase P3 started at 10:00", importance=2),
        CompactionItem(kind="event", content="phase p3 started at 10:00", importance=2),  # case-insensitive
    ]

    result = compact.compact(items)
    assert result["report"]["preserved"] == 1
    assert len(result["items"]) == 1


def test_compress_low_importance_first():
    """Low-importance items should be dropped first to fit budget."""
    compact = ACECompact(target_budget=100)

    items = [
        CompactionItem(kind="tool_result", content="A" * 1000, importance=1),
        CompactionItem(kind="decision", content="Critical decision here", importance=4),
    ]

    result = compact.compact(items)
    # Critical should be preserved
    assert any(it.importance == 4 for it in result["items"])


def test_compression_ratio():
    compact = ACECompact(target_budget=50)

    items = [
        CompactionItem(kind="tool_result", content="x" * 1000, importance=1),  # ~250 tokens (low prio, compressible)
        CompactionItem(kind="decision", content="y" * 100, importance=4),  # ~25 tokens (high prio, preserved)
    ]

    result = compact.compact(items)
    tokens_in = result["report"]["tokens_in"]
    tokens_out = result["report"]["tokens_out"]
    # Low-priority tool_result should be dropped (or compressed), only decision kept
    assert tokens_out < tokens_in
    assert result["report"]["dropped"] >= 1


def test_delta_report():
    compact = ACECompact(target_budget=1000)

    before = [
        CompactionItem(kind="event", content="A", importance=2),
        CompactionItem(kind="event", content="B", importance=2),
        CompactionItem(kind="event", content="C", importance=2),
    ]
    after = [before[0]]  # B and C dropped

    report = compact.delta_report(before, after)
    assert "1 preserved" in report
    assert "2 eliminated" in report


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
