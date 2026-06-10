"""
CE-Harness LLM View Builder (L4 Layer)
=========================================
Curated LLM context with head/middle/tail layout.

Implements the "lost-in-the-middle" mitigation (Invariant 5):
LLMs attend most to the beginning and end of context. Critical
info goes to head/tail; working data goes to middle and gets
compacted via ACE.

Layout budget allocation:
- HEAD (~30%): gate state, budget status, active constraints
- MIDDLE (~40%): working context, tool results, retrieval (ACE-compacted)
- TAIL (~30%): adversarial findings, recent decisions, UDL

v1.1 — Implements L4 from the 5-layer architecture (previously aspirational).
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .ace_compact import ACECompact, CompactionItem


@dataclass
class ViewSection:
    """A section of the curated LLM view."""
    label: str
    priority: int  # 1=head, 2=middle, 3=tail
    content: str
    tokens_est: int = 0

    def __post_init__(self):
        if self.tokens_est == 0 and self.content:
            self.tokens_est = max(1, len(self.content) // 4)


class LLMViewBuilder:
    """Build a curated LLM view with head/middle/tail layout.

    Head: gate state + budget + constraints (always visible, high attention).
    Middle: working context, retrieved data (compressible via ACE).
    Tail: adversarial findings + recent decisions (high attention at end).

    Usage:
        builder = LLMViewBuilder(state, phase_id="P5", budget=4000)
        builder.add_budget_status()
        builder.add_constraints(["max 5000 tokens", "no external calls"])
        builder.add_working_context(items)
        builder.add_adversarial_findings(["potential injection in tool result"])
        view = builder.build()
    """

    HEAD_FRACTION = 0.30
    MIDDLE_FRACTION = 0.40
    TAIL_FRACTION = 0.30

    def __init__(self, state=None, phase_id: str = "",
                 budget: int = 4000):
        self.state = state
        self.phase_id = phase_id
        self.budget = budget
        self._sections: List[ViewSection] = []

    def add_section(self, label: str, priority: int, content: str) -> None:
        """Add a section to the view (1=head, 2=middle, 3=tail)."""
        if priority not in (1, 2, 3):
            raise ValueError(f"Priority must be 1 (head), 2 (middle), or 3 (tail), got {priority}")
        self._sections.append(ViewSection(
            label=label, priority=priority, content=content
        ))

    def add_gate_state(self, gate_results: Dict[str, Any]) -> None:
        """Add gate pass/fail status to HEAD."""
        lines = ["## Gate State"]
        for gate, result in gate_results.items():
            status = "PASS" if result.get("ok") else "FAIL"
            lines.append(f"- {gate}: {status}")
        self.add_section("gate_state", 1, "\n".join(lines))

    def add_budget_status(self) -> None:
        """Add current budget usage to HEAD (reads from StateDB)."""
        if self.state is None:
            return
        try:
            total = self.state.phase_total(self.phase_id)
            soft, hard = self.state.phase_budget(self.phase_id)
            pct = (total / hard * 100) if hard else 0
            bar_len = 20
            filled = int(bar_len * pct / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            content = (
                f"## Budget Status\n"
                f"- Phase: {self.phase_id}\n"
                f"- Used: {total:,} / {hard:,} tokens ({pct:.1f}%)\n"
                f"- [{bar}]"
            )
            self.add_section("budget_status", 1, content)
        except Exception:
            self.add_section("budget_status", 1, "## Budget Status\n- Phase not found")

    def add_constraints(self, constraints: List[str]) -> None:
        """Add phase constraints to HEAD."""
        if not constraints:
            return
        lines = ["## Active Constraints"]
        for c in constraints:
            lines.append(f"- {c}")
        self.add_section("constraints", 1, "\n".join(lines))

    def add_working_context(self, items: List[CompactionItem]) -> None:
        """Add working context items to MIDDLE (compressible via ACE)."""
        if not items:
            return
        middle_budget = int(self.budget * self.MIDDLE_FRACTION)
        compactor = ACECompact(target_budget=middle_budget)
        result = compactor.compact(items)
        lines = ["## Working Context"]
        for item in result["items"]:
            lines.append(f"- [{item.kind}] {item.content}")
        if result["report"]["dropped"] > 0:
            lines.append(
                f"\n_({result['report']['dropped']} items compacted/dropped, "
                f"{result['report']['compression_ratio']:.1f}× ratio)_"
            )
        self.add_section("working_context", 2, "\n".join(lines))

    def add_adversarial_findings(self, findings: List[str]) -> None:
        """Add adversarial gate findings to TAIL."""
        if not findings:
            return
        lines = ["## ⚠ Adversarial Findings"]
        for f in findings:
            lines.append(f"- {f}")
        self.add_section("adversarial_findings", 3, "\n".join(lines))

    def add_recent_decisions(self, decisions: List[str], limit: int = 5) -> None:
        """Add recent audit decisions to TAIL."""
        if not decisions:
            return
        lines = ["## Recent Decisions"]
        for d in decisions[:limit]:
            lines.append(f"- {d}")
        self.add_section("recent_decisions", 3, "\n".join(lines))

    def build(self) -> str:
        """Assemble head + compacted_middle + tail within budget.

        Returns the final curated string ready for LLM consumption.
        Layout preserves head and tail even when total exceeds budget
        (middle is truncated first).
        """
        head_budget = int(self.budget * self.HEAD_FRACTION)
        middle_budget = int(self.budget * self.MIDDLE_FRACTION)
        tail_budget = int(self.budget * self.TAIL_FRACTION)

        head_sections = [s for s in self._sections if s.priority == 1]
        middle_sections = [s for s in self._sections if s.priority == 2]
        tail_sections = [s for s in self._sections if s.priority == 3]

        parts = []

        # HEAD — always preserved
        head_content = "\n\n".join(s.content for s in head_sections)
        head_tokens = max(1, len(head_content) // 4)
        if head_content:
            parts.append(head_content)

        # MIDDLE — truncatable
        middle_content = "\n\n".join(s.content for s in middle_sections)
        if middle_content:
            # Truncate middle if it exceeds its budget
            max_chars = middle_budget * 4
            if len(middle_content) > max_chars:
                middle_content = middle_content[:max_chars] + "\n\n_[truncated]_"
            parts.append(middle_content)

        # TAIL — always preserved
        tail_content = "\n\n".join(s.content for s in tail_sections)
        if tail_content:
            parts.append(tail_content)

        if not parts:
            return f"# LLM View — {self.phase_id}\n(budget: {self.budget} tokens, no sections)"

        header = (
            f"# LLM View — {self.phase_id}\n"
            f"_Budget: {self.budget} tokens | "
            f"Sections: {len(head_sections)}H + {len(middle_sections)}M + {len(tail_sections)}T_"
        )
        return header + "\n\n" + "\n\n---\n\n".join(parts)

    def section_report(self) -> Dict[str, Any]:
        """Return token counts per section for diagnostics."""
        report = {"phase": self.phase_id, "budget": self.budget, "sections": []}
        for s in self._sections:
            priority_name = {1: "head", 2: "middle", 3: "tail"}.get(s.priority, "unknown")
            report["sections"].append({
                "label": s.label,
                "zone": priority_name,
                "tokens_est": s.tokens_est,
                "chars": len(s.content),
            })
        total = sum(s["tokens_est"] for s in report["sections"])
        report["total_tokens_est"] = total
        report["budget_utilization"] = round(total / max(1, self.budget) * 100, 1)
        return report
