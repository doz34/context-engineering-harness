"""
CE-Harness Token Ledger
========================
Live, per-component, per-phase token tracking.
Triggers at 60/70/85/95% of soft_cap.
"""

from typing import Optional
from .state import StateDB


class TokenLedger:
    """
    Track token usage with auto-triggers at 60/70/85/95% of soft cap.

    Usage:
        ledger = TokenLedger()
        ledger.start_phase("P3_ARCH", "P3", soft_cap=8000, hard_cap=15000)
        ledger.record("messages", "input", 1200, model="claude-opus-4-8")
        # → Auto-triggers at 70%: WARN with CC recommendation
    """

    TRIGGERS = {
        0.60: "INFO_60",    # Halfway to soft cap
        0.70: "CC_NOW",     # Compaction Checkpoint required
        0.85: "WARN_85",    # Approaching soft cap
        0.95: "CRITICAL",   # Almost at hard cap
        1.00: "ABORT",      # Hard cap reached
    }

    def __init__(self, state: Optional[StateDB] = None,
                 path: str = ".ctxh/state.db",
                 verbose: bool = True):
        self.state = state or StateDB(path)
        self.verbose = verbose
        self._triggered: dict[str, set[str]] = {}  # phase_id → set of trigger levels

    def start_phase(self, phase_id: str, name: str,
                    soft_cap: int, hard_cap: int,
                    session_id: str = "default") -> None:
        """Start a phase with token budget."""
        self.state.start_phase(phase_id, session_id, name, soft_cap, hard_cap)
        self._triggered[phase_id] = set()
        if self.verbose:
            print(f"[LEDGER] Phase {phase_id} started: soft={soft_cap}, hard={hard_cap}")

    def end_phase(self, phase_id: str, status: str = "complete") -> None:
        """End a phase."""
        total = self.state.phase_total(phase_id)
        if self.verbose:
            soft, hard = self.state.phase_budget(phase_id)
            pct = (total / soft * 100) if soft else 0
            print(f"[LEDGER] Phase {phase_id} ended: {total} tokens ({pct:.1f}% of soft)")
        self.state.end_phase(phase_id, status)

    def record(self, phase_id: str, component: str, direction: str,
               tokens: int, model: str = "", agent: str = "",
               metadata: dict = None) -> dict:
        """
        Record a token event. Returns status dict.

        Triggers at 60/70/85/95% of soft cap and 100% of hard cap.
        """
        total = self.state.record_token(
            phase_id, component, direction, tokens,
            model, agent, metadata
        )

        soft, hard = self.state.phase_budget(phase_id)
        status = self._check_triggers(total, soft, hard, phase_id)

        if self.verbose and status.get("action") not in (None, "INFO_60"):
            print(f"[LEDGER] {phase_id} {total}/{soft} ({total/soft*100:.0f}%) → {status}")

        return status

    def _check_triggers(self, total: int, soft: int, hard: int,
                        phase_id: str) -> dict:
        """Check if any trigger should fire. Returns HIGHEST threshold crossed."""
        if not soft:
            return {"action": None, "pct": 0}

        soft_pct = total / soft
        hard_pct = total / hard if hard else 0

        triggered = self._triggered.setdefault(phase_id, set())

        # Hard cap (highest priority)
        if hard_pct >= 1.0 and "ABORT" not in triggered:
            triggered.add("ABORT")
            return {
                "action": "ABORT",
                "level": "HARD_CAP",
                "tokens": total,
                "soft": soft,
                "hard": hard,
                "message": f"HARD CAP reached. Abort phase {phase_id}.",
            }

        # Find highest soft cap threshold crossed (and not yet triggered)
        # Order: 0.95 > 0.85 > 0.70 > 0.60
        levels = [
            (0.95, "CRITICAL", f"95% reached. End phase or abort."),
            (0.85, "WARN_85", f"85% reached. Reduce tool loading or escalate."),
            (0.70, "CC_NOW", f"70% reached. Compaction Checkpoint (CC) required."),
            (0.60, "INFO_60", f"60% reached. Consider CC proactively."),
        ]

        for threshold, action, message in levels:
            if soft_pct >= threshold and action not in triggered:
                triggered.add(action)
                return {
                    "action": action,
                    "level": f"{int(threshold*100)}%",
                    "tokens": total,
                    "soft": soft,
                    "message": message,
                }

        return {"action": None, "pct": soft_pct}

    def top_components(self, phase_id: str, limit: int = 5) -> list:
        return self.state.top_components(phase_id, limit)

    def dashboard(self, phase_id: str = None) -> str:
        """Return a Rich-formatted dashboard."""
        if phase_id:
            return self._phase_dashboard(phase_id)
        return self._global_dashboard()

    def _phase_dashboard(self, phase_id: str) -> str:
        total = self.state.phase_total(phase_id)
        soft, hard = self.state.phase_budget(phase_id)
        soft_pct = (total / soft * 100) if soft else 0
        hard_pct = (total / hard * 100) if hard else 0

        lines = [
            f"╔══ Phase {phase_id} ══╗",
            f"║ Total: {total:,} tokens",
            f"║ Soft cap: {soft:,} ({soft_pct:.1f}%)",
            f"║ Hard cap: {hard:,} ({hard_pct:.1f}%)",
            f"║ Status: {self._bar(soft_pct)}",
            f"║",
            f"║ Top components:",
        ]

        for comp, t in self.top_components(phase_id, 5):
            pct = (t / total * 100) if total else 0
            lines.append(f"║   {comp:15} {t:>6,} ({pct:>5.1f}%)")

        lines.append("╚" + "═" * 30 + "╝")
        return "\n".join(lines)

    def _global_dashboard(self) -> str:
        # Aggregate all phases
        return "[Dashboard global] Use --phase <id> for details."

    def _bar(self, pct: float, width: int = 20) -> str:
        filled = int(pct / 100 * width)
        return "█" * filled + "░" * (width - filled)
