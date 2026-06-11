"""Context Failure Mode Detector.

Implements Drew Breunig's 4 failure modes (distraction, poisoning, clash,
instruction fade) plus context rot detection based on Morph research.

No external dependencies — stdlib only. Python 3.10+.
"""

from __future__ import annotations

import hashlib
import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
    CRIT = "CRIT"


@dataclass
class Finding:
    mode: str
    severity: Severity
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


class ContextFailureDetector:
    """Detects 5 context failure modes in LLM agent sessions."""

    # Morph research: degradation accelerates beyond ~35 min / ~20K tokens
    ROT_TURN_THRESHOLD = 30
    ROT_TOKEN_THRESHOLD = 20_000
    ROT_SEVERE_TURN = 50
    ROT_SEVERE_TOKEN = 40_000

    def __init__(self, max_history: int = 100) -> None:
        self._history: deque[dict[str, str]] = deque(maxlen=max_history)
        self._provided_elements: set[str] = set()
        self._findings: list[Finding] = []

    # -- recording -----------------------------------------------------------

    def record_action(self, action_type: str, content: str) -> None:
        """Record an agent action for later analysis."""
        self._history.append({"type": action_type, "content": content})

    # -- individual detectors ------------------------------------------------

    def detect_distraction(self) -> Finding | None:
        """Detect repeated same-action pattern (3+ similar in last 10)."""
        window = list(self._history)[-10:]
        if len(window) < 3:
            return None

        counts: dict[str, list[int]] = {}
        for i, act in enumerate(window):
            key = self._action_fingerprint(act)
            counts.setdefault(key, []).append(i)

        worst_key, worst_indices = "", []
        for key, indices in counts.items():
            if len(indices) >= 3 and len(indices) > len(worst_indices):
                worst_key, worst_indices = key, indices

        if not worst_indices:
            return None

        repeats = len(worst_indices)
        sev = Severity.CRIT if repeats >= 5 else Severity.HIGH if repeats >= 4 else Severity.MED
        return Finding(
            mode="distraction",
            severity=sev,
            detail=f"Repeated action pattern detected ({repeats}x in last 10)",
            evidence={"fingerprint": worst_key, "indices": worst_indices},
        )

    def detect_poisoning(self, context_elements: list[str] | None = None) -> Finding | None:
        """Detect references to elements not in the provided context."""
        if context_elements is not None:
            self._provided_elements = {e.lower().strip() for e in context_elements}

        if not self._provided_elements:
            return None

        recent = list(self._history)[-20:]
        ghosts: list[str] = []
        for act in recent:
            content_lower = act["content"].lower()
            words = set(re.findall(r"[a-z_][a-z0-9_]{2,}", content_lower))
            for word in words:
                if word not in self._provided_elements:
                    ghosts.append(word)

        if not ghosts:
            return None

        # Only flag if ghost terms appear repeatedly
        from collections import Counter

        ghost_counts = Counter(ghosts)
        persistent = [g for g, c in ghost_counts.items() if c >= 2]

        if not persistent:
            return None

        sev = Severity.HIGH if len(persistent) >= 3 else Severity.MED
        return Finding(
            mode="poisoning",
            severity=sev,
            detail=f"References to {len(persistent)} elements not in provided context",
            evidence={"ghost_elements": persistent[:10]},
        )

    def detect_clash(self, instructions: list[str] | None = None) -> Finding | None:
        """Detect contradictory instructions (negation patterns, conflicts)."""
        if instructions is None:
            return None

        if len(instructions) < 2:
            return None

        clashes: list[dict[str, str]] = []
        directives: dict[str, str] = {}

        for instr in instructions:
            instr_lower = instr.lower().strip()

            # Pattern: "do X" vs "don't do X" / "never do X"
            neg_match = re.match(
                r"(?:don'?t|never|do not|must not|should not)\s+(.+)", instr_lower
            )
            if neg_match:
                verb_phrase = neg_match.group(1).strip().rstrip(".!")
                directives[f"neg:{verb_phrase}"] = instr
                continue

            pos_match = re.match(r"(?:do|always|must|should|please)\s+(.+)", instr_lower)
            if pos_match:
                verb_phrase = pos_match.group(1).strip().rstrip(".!")
                directives[f"pos:{verb_phrase}"] = instr

        # Check for neg/pos pairs on same verb phrase
        neg_keys = {k for k in directives if k.startswith("neg:")}
        for nk in neg_keys:
            verb = nk[4:]
            pk = f"pos:{verb}"
            if pk in directives:
                clashes.append({"affirmative": directives[pk], "negative": directives[nk]})

        if not clashes:
            return None

        sev = Severity.CRIT if len(clashes) >= 3 else Severity.HIGH
        return Finding(
            mode="clash",
            severity=sev,
            detail=f"{len(clashes)} contradictory instruction pair(s) detected",
            evidence={"clashes": clashes},
        )

    def detect_instruction_fade(
        self, baseline_instructions: str | None = None, current_context: str | None = None
    ) -> Finding | None:
        """Measure drift from initial instructions via token overlap."""
        if baseline_instructions is None or current_context is None:
            return None

        base_tokens = self._tokenize(baseline_instructions)
        curr_tokens = self._tokenize(current_context)

        if not base_tokens:
            return None

        overlap = base_tokens & curr_tokens
        ratio = len(overlap) / len(base_tokens)

        if ratio >= 0.7:
            return None

        lost = base_tokens - curr_tokens
        sev = Severity.CRIT if ratio < 0.3 else Severity.HIGH if ratio < 0.5 else Severity.MED
        return Finding(
            mode="instruction_fade",
            severity=sev,
            detail=f"Instruction retention: {ratio:.0%} ({len(lost)}/{len(base_tokens)} tokens lost)",
            evidence={"retention": round(ratio, 3), "lost_tokens": sorted(lost)[:20]},
        )

    def detect_context_rot(
        self,
        turn_count: int = 0,
        context_size: int = 0,
        accuracy_hint: float | None = None,
    ) -> Finding | None:
        """Estimate rot risk based on Morph's degradation curve."""
        if turn_count == 0 and context_size == 0:
            return None

        risk = 0.0
        factors: list[str] = []

        if turn_count > self.ROT_SEVERE_TURN:
            risk += 0.6
            factors.append(f"turns={turn_count} (severe)")
        elif turn_count > self.ROT_TURN_THRESHOLD:
            risk += 0.3
            factors.append(f"turns={turn_count} (elevated)")

        if context_size > self.ROT_SEVERE_TOKEN:
            risk += 0.6
            factors.append(f"tokens={context_size} (severe)")
        elif context_size > self.ROT_TOKEN_THRESHOLD:
            risk += 0.3
            factors.append(f"tokens={context_size} (elevated)")

        if accuracy_hint is not None and accuracy_hint < 0.8:
            risk += 0.3
            factors.append(f"accuracy={accuracy_hint:.0%}")

        risk = min(risk, 1.0)

        if risk < 0.3:
            return None

        sev = Severity.CRIT if risk >= 0.7 else Severity.HIGH if risk >= 0.5 else Severity.MED
        return Finding(
            mode="context_rot",
            severity=sev,
            detail=f"Context rot risk: {risk:.0%}",
            evidence={"risk_score": round(risk, 2), "factors": factors},
        )

    # -- composite -----------------------------------------------------------

    def run_all_checks(
        self,
        baseline_instructions: str | None = None,
        context_elements: list[str] | None = None,
        instructions: list[str] | None = None,
        turn_count: int = 0,
        context_size: int = 0,
        accuracy_hint: float | None = None,
    ) -> dict[str, Any]:
        """Run all detectors, return structured findings dict."""
        self._findings = []

        detectors = [
            self.detect_distraction(),
            self.detect_poisoning(context_elements),
            self.detect_clash(instructions),
            self.detect_instruction_fade(baseline_instructions, None),
            self.detect_context_rot(turn_count, context_size, accuracy_hint),
        ]

        results: dict[str, Finding | None] = {}
        for finding in detectors:
            if finding is not None:
                self._findings.append(finding)
            mode = finding.mode if finding else "none_extra"
            results[finding.mode if finding else "clean"] = finding
            if finding:
                results[finding.mode] = finding

        # Remove the "clean" placeholder if present
        results.pop("clean", None)

        return {
            "findings": [
                {"mode": f.mode, "severity": f.severity.value, "detail": f.detail, "evidence": f.evidence}
                for f in self._findings
            ],
            "total": len(self._findings),
            "has_critical": any(f.severity == Severity.CRIT for f in self._findings),
        }

    def severity(self, finding: Finding) -> Severity:
        """Classify a finding's severity."""
        return finding.severity

    def summary(self) -> str:
        """Human-readable summary of current detector state."""
        lines = [
            f"Context Failure Detector — {len(self._history)} actions recorded",
            f"Provided context elements: {len(self._provided_elements)}",
        ]
        if self._findings:
            lines.append(f"Findings ({len(self._findings)}):")
            for f in self._findings:
                lines.append(f"  [{f.severity.value}] {f.mode}: {f.detail}")
        else:
            lines.append("No findings yet — run run_all_checks() first.")
        return "\n".join(lines)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _action_fingerprint(action: dict[str, str]) -> str:
        """Hash action_type + first 50 chars of content for similarity."""
        raw = f"{action['type']}:{action['content'][:50]}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Simple whitespace+punctuation tokenizer, lowercased."""
        return set(re.findall(r"[a-z][a-z0-9_]{1,}", text.lower()))
