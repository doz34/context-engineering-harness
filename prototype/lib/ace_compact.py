"""
CE-Harness Compaction ACE-style
=================================
Preserve structure + details. NOT summarization.
Avoid brevity bias and context collapse (per ACE paper, ICLR 2026).
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class CompactionItem:
    """An item that should be preserved across compaction."""
    kind: str  # 'event' | 'decision' | 'constraint' | 'gate_finding' | 'tool_result'
    content: str
    timestamp: str = ""
    ref: str = ""
    importance: int = 1  # 1=low, 2=med, 3=high, 4=critical

    def tokens_est(self) -> int:
        """Rough token estimate (4 chars / token)."""
        return max(1, len(self.content) // 4)


class ACECompact:
    """
    ACE-style compaction:
    - PRESERVE events, decisions, constraints, gate findings
    - DEDUPLICATE semantically similar items
    - COMPRESS only middle/working context
    - KEEP critical items intact (importance >= 3)
    """

    PRESERVE_KINDS = {"event", "decision", "constraint", "gate_finding"}
    COMPRESS_KINDS = {"tool_result", "retrieval", "chat_history"}

    def __init__(self, target_budget: int = 2000):
        self.target_budget = target_budget
        self._seen_hashes: set[str] = set()

    def compact(self, items: List[CompactionItem]) -> dict:
        """
        Compact a list of items to target_budget tokens.
        Returns dict with preserved/compressed/dropped lists + report.
        """
        # Step 1: Separate preserve vs compress
        preserve = [it for it in items if it.kind in self.PRESERVE_KINDS]
        compress = [it for it in items if it.kind in self.COMPRESS_KINDS]

        # Step 2: Deduplicate preserve (by content hash)
        deduped_preserve = self._dedupe(preserve)

        # Step 3: Compress the rest until budget
        compressed, dropped = self._compress_to_budget(
            compress,
            target=self.target_budget - sum(it.tokens_est() for it in deduped_preserve)
        )

        # Step 4: Order: critical first (head), then by timestamp
        ordered = self._order(deduped_preserve + compressed)

        return {
            "items": ordered,
            "report": {
                "preserved": len(deduped_preserve),
                "compressed": len(compressed),
                "dropped": len(dropped),
                "total_in": len(items),
                "total_out": len(ordered),
                "tokens_in": sum(it.tokens_est() for it in items),
                "tokens_out": sum(it.tokens_est() for it in ordered),
                "compression_ratio": (
                    sum(it.tokens_est() for it in items) /
                    max(1, sum(it.tokens_est() for it in ordered))
                ),
            }
        }

    def _dedupe(self, items: List[CompactionItem]) -> List[CompactionItem]:
        """Deduplicate by content hash (semantic dedup TODO: embeddings)."""
        result = []
        for it in items:
            h = self._content_hash(it.content)
            if h not in self._seen_hashes:
                self._seen_hashes.add(h)
                # Keep highest importance version
                existing = next((r for r in result if self._content_hash(r.content) == h), None)
                if existing is None or it.importance > existing.importance:
                    if existing:
                        result.remove(existing)
                    result.append(it)
        return result

    def _content_hash(self, content: str) -> str:
        """Quick content hash (lowercase, whitespace normalized)."""
        import hashlib
        normalized = re.sub(r'\s+', ' ', content.lower().strip())
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def _compress_to_budget(self, items: List[CompactionItem],
                            target: int) -> tuple[List[CompactionItem], List[CompactionItem]]:
        """Compress items to fit within target tokens. Drop low-importance last."""
        # Sort by importance desc, then timestamp asc
        sorted_items = sorted(items, key=lambda x: (-x.importance, x.timestamp))

        kept = []
        dropped = []
        budget = target

        for it in sorted_items:
            t = it.tokens_est()
            if budget - t >= 0:
                kept.append(it)
                budget -= t
            else:
                dropped.append(it)

        return kept, dropped

    def _order(self, items: List[CompactionItem]) -> List[CompactionItem]:
        """Order: critical first, then by timestamp asc (chronological)."""
        return sorted(items, key=lambda x: (-x.importance, x.timestamp))

    def delta_report(self, before: List[CompactionItem], after: List[CompactionItem]) -> str:
        """Generate a delta report of what was preserved vs eliminated."""
        before_keys = {self._content_hash(it.content) for it in before}
        after_keys = {self._content_hash(it.content) for it in after}

        preserved = len(before_keys & after_keys)
        eliminated = len(before_keys - after_keys)

        return (
            f"Compaction delta: {preserved} preserved, {eliminated} eliminated. "
            f"Tokens: {sum(it.tokens_est() for it in before)} → "
            f"{sum(it.tokens_est() for it in after)} "
            f"({sum(it.tokens_est() for it in before) / max(1, sum(it.tokens_est() for it in after)):.1f}× compression)"
        )
