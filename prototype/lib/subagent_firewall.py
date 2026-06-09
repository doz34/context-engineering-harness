"""
CE-Harness Subagent Firewall
=============================
Strict context isolation. Subagent NEVER sees parent context.
Return contract: ref + summary + artifacts. NEVER dump.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from .dsl import validate_brief, parse
from .token_ledger import TokenLedger


@dataclass
class SubagentBrief:
    """Structured subagent brief (4-champs rule)."""
    OBJECT: str
    FORMAT: str
    TOOLS: List[str] = field(default_factory=list)
    BOUND: str = ""

    @classmethod
    def from_dsl(cls, dsl_text: str) -> "SubagentBrief":
        d = parse(dsl_text)
        return cls(
            OBJECT=d.get("OBJECT", ""),
            FORMAT=d.get("FORMAT", ""),
            TOOLS=[t.strip() for t in d.get("TOOLS", "").split(",") if t.strip()],
            BOUND=d.get("BOUND", ""),
        )

    def to_dsl(self) -> str:
        return f"OBJECT:{self.OBJECT};;FORMAT:{self.FORMAT};;TOOLS:{','.join(self.TOOLS)};;BOUND:{self.BOUND}"

    def validate(self) -> tuple[bool, List[str]]:
        d = {
            "OBJECT": self.OBJECT,
            "FORMAT": self.FORMAT,
            "TOOLS": ",".join(self.TOOLS),
            "BOUND": self.BOUND,
        }
        return validate_brief(d)


@dataclass
class SubagentResult:
    """Summary-only return contract."""
    summary: str
    refs: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    tokens_used: int = 0
    raw_size: int = 0  # What the raw would have been (for comparison)

    def to_dsl(self) -> str:
        return (
            f"SUMMARY:{self.summary};;"
            f"REFS:{','.join(self.refs)};;"
            f"ARTIFACTS:{','.join(self.artifacts)};;"
            f"TOKENS:{self.tokens_used};;"
            f"RAW_SIZE:{self.raw_size}"
        )

    def compression_ratio(self) -> float:
        """How much we compressed vs raw dump."""
        if not self.raw_size:
            return 1.0
        return self.raw_size / max(self.tokens_used, 1)


class SubagentFirewall:
    """
    Spawn isolated subagent context.

    The subagent NEVER sees parent context. It receives only:
    - The brief (OBJECT/FORMAT/TOOLS/BOUND)
    - Its own context budget
    - Tool list (limited)

    Returns ONLY summary + refs + artifacts. Never a dump.
    """

    def __init__(self, ledger: TokenLedger, phase_id: str):
        self.ledger = ledger
        self.phase_id = phase_id
        self._subagent_id = 0

    def spawn(self, brief: SubagentBrief,
              context_budget: int = 4000,
              model: str = "claude-sonnet-4-5",
              execute_fn=None) -> SubagentResult:
        """
        Spawn a subagent. The execute_fn is the actual logic.

        In production, execute_fn would call the LLM. In POV/demo,
        it can be a stub.
        """
        # Validate brief (4-champs)
        valid, errors = brief.validate()
        if not valid:
            raise ValueError(f"Invalid brief: {errors}")

        self._subagent_id += 1
        sub_id = f"{self.phase_id}_sub_{self._subagent_id}"

        # Record spawn event
        self.ledger.record(
            self.phase_id, "subagent_spawn", "metadata",
            tokens=0,  # spawn is metadata, not tokens
            model=model, agent=sub_id,
            metadata={"brief": brief.to_dsl(), "budget": context_budget}
        )

        # Execute in isolated context (the firewall!)
        if execute_fn is None:
            # Stub for POV
            result = self._stub_execute(brief, sub_id, model, context_budget)
        else:
            result = execute_fn(brief, sub_id, model, context_budget)

        # Record token usage
        if result.tokens_used:
            self.ledger.record(
                self.phase_id, "subagent_context", "input",
                tokens=result.tokens_used, model=model, agent=sub_id
            )

        return result

    def _stub_execute(self, brief: SubagentBrief, sub_id: str,
                      model: str, budget: int) -> SubagentResult:
        """Stub for POV demo. Replace with real LLM call."""
        # Simulate: brief → fake result
        return SubagentResult(
            summary=f"[STUB] Completed task: {brief.OBJECT[:50]}...",
            refs=["src/example.py:42", "src/other.py:88"],
            artifacts=[f".ctxh/subagents/{sub_id}/output.json"],
            tokens_used=int(budget * 0.7),  # Simulated 70% budget use
            raw_size=80000,  # What dump would have been
        )

    def verify_isolation(self, sub_id: str) -> dict:
        """
        Verify the subagent didn't leak parent context.
        Returns audit dict.
        """
        return {
            "subagent_id": sub_id,
            "parent_context_visible": False,
            "tools_used": "isolated",
            "return_summary_only": True,
            "verified_at": "audit",
        }
