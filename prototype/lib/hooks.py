"""
CE-Harness Hooks System
========================
7 lifecycle hooks with strict events. Closes CRIT:
- TOOL_RESULT_CLEARING_HOOK_MISSING (CISO HIGH)
- Pattern: success silent, failure verbose (HumanLayer 2026)
- Pattern: PostToolUse clears raw results (Anthropic 2025)
"""

import json
import re
from enum import Enum
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


class HookEvent(str, Enum):
    """7 lifecycle events."""
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    SUBAGENT_START = "SubagentStart"
    SUBAGENT_END = "SubagentEnd"
    PHASE_START = "PhaseStart"
    PHASE_END = "PhaseEnd"
    USER_MESSAGE = "UserMessage"


@dataclass
class HookContext:
    """Context passed to hook handlers."""
    event: HookEvent
    payload: Dict[str, Any]
    phase_id: str = ""
    subagent_id: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    timestamp: str = ""


class HookDecision(str, Enum):
    """Hook decisions."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    MODIFY = "MODIFY"
    CLEAR = "CLEAR"  # Specific: clear tool result (PostToolUse)


@dataclass
class HookResult:
    """Result of a hook execution."""
    decision: HookDecision
    modified_payload: Optional[Dict[str, Any]] = None
    reason: str = ""
    silent: bool = True  # Success silent (HumanLayer 2026)


# === HOOK HANDLERS ===

def pre_tool_use_block_destructive(ctx: HookContext) -> HookResult:
    """
    Block destructive bash commands.
    Pattern: 4 hooks (HumanLayer 2026-03).
    """
    destructive = [
        (r"\brm\s+-rf\s+/(?!tmp)", "rm -rf at root"),
        (r"\bgit\s+push\s+--force\s+origin\s+main", "force push to main"),
        (r"\bgit\s+push\s+-f\b", "force push"),
        (r"DROP\s+TABLE", "DROP TABLE"),
        (r"DROP\s+DATABASE", "DROP DATABASE"),
        (r":\(\)\s*\{.*:\|:&\s*\};:", "fork bomb"),
        (r"\bdd\s+if=.*of=/dev/sd", "dd to disk device"),
        (r"mkfs\.\w+\s+/dev/", "format filesystem"),
        (r">\s*/etc/passwd", "overwrite /etc/passwd"),
        (r"chmod\s+-R\s+777\s+/", "world-writable root"),
    ]
    cmd = ctx.tool_args.get("command", "") if ctx.tool_args else ""
    for pattern, desc in destructive:
        if re.search(pattern, cmd, re.IGNORECASE):
            return HookResult(
                decision=HookDecision.DENY,
                reason=f"Destructive command blocked: {desc}",
                silent=False,
            )
    return HookResult(decision=HookDecision.ALLOW, silent=True)


def pre_tool_use_check_budget(ctx: HookContext) -> HookResult:
    """Block tool calls if phase budget exceeded."""
    # Read budget from context payload (set by phase start)
    remaining = ctx.payload.get("budget_remaining", 0)
    if remaining <= 0:
        return HookResult(
            decision=HookDecision.DENY,
            reason=f"Phase budget exhausted ({remaining} tokens remaining)",
            silent=False,
        )
    return HookResult(decision=HookDecision.ALLOW, silent=True)


def post_tool_use_clear_result(ctx: HookContext) -> HookResult:
    """
    THE KEY HOOK: Clear tool result after consumption.
    Pattern: Anthropic 2025 — raw results are rarely re-needed.
    Implementation: keep head+tail (first 200 + last 200 chars),
    offload full to filesystem, return CLEAR with reference.
    """
    if not ctx.tool_result:
        return HookResult(decision=HookDecision.ALLOW, silent=True)

    full = ctx.tool_result
    # If small, keep as-is
    if len(full) <= 400:
        return HookResult(decision=HookDecision.ALLOW, silent=True)

    # If large, offload to filesystem (record in audit chain)
    head = full[:200]
    tail = full[-200:]
    # Sanitize tool_name to a safe filename component. tool_name is
    # caller-controlled and may contain '../' segments that would escape
    # the .ctxh/tool_results/ directory. Restrict to [A-Za-z0-9_.-] and
    # fall back to a hash if the sanitized name is empty.
    import hashlib
    import re
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", ctx.tool_name or "tool")
    if not safe_name or safe_name in (".", ".."):
        safe_name = "tool_" + hashlib.sha256(
            (ctx.tool_name or "").encode()
        ).hexdigest()[:8]
    # F-006 audit 2026-06-10: also sanitize ctx.timestamp. Previously
    # this was inserted verbatim into the path, allowing a caller-
    # controlled value like "../../../etc/cron.daily/payload" to escape
    # the .ctxh/tool_results/ directory. Note: stripping non-[A-Za-z0-9_.-]
    # chars is NOT enough because dots are allowed and a value like
    # "../../etc" becomes ".._.._etc" which still contains ".." segments.
    # We additionally reject any name that contains a ".." substring and
    # fall back to a hash.
    safe_ts = re.sub(r"[^A-Za-z0-9_.-]", "_", ctx.timestamp or "")
    if not safe_ts or ".." in safe_ts:
        safe_ts = "ts_" + hashlib.sha256(
            (ctx.timestamp or "").encode()
        ).hexdigest()[:8]
    # Same hardening for safe_name (in case a tool_name also contains "..")
    if ".." in safe_name:
        safe_name = "tool_" + hashlib.sha256(
            (ctx.tool_name or "").encode()
        ).hexdigest()[:8]
    full_path = f".ctxh/tool_results/{safe_name}_{safe_ts}.txt"
    cleared = (
        f"{head}\n... [CLEARED: {len(full) - 400} chars offloaded to "
        f"{full_path}] ...\n{tail}"
    )

    # Persist full result for re-access (audit chain)
    try:
        import os
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(full)
    except OSError:
        pass

    return HookResult(
        decision=HookDecision.CLEAR,
        modified_payload={
            **ctx.payload,
            "tool_result": cleared,
            "tool_result_full_ref": full_path,
            "tool_result_cleared_chars": len(full) - 400,
        },
        reason=f"Tool result cleared: {len(full)} → {len(cleared)} chars (offloaded to {full_path})",
        silent=True,  # Success silent (HumanLayer 2026)
    )


def post_tool_use_summarize_swallowed(ctx: HookContext) -> HookResult:
    """
    If tool result is 'passing' (test success, lint clean), swallow it.
    Pattern: success silent, failure verbose (HumanLayer 2026-03).

    Anti-bypass: if FAILED/ERROR appears ANYWHERE in the result, do NOT swallow.
    """
    result = ctx.tool_result or ""
    # First check: any failure marker present?
    failure_markers = ["FAIL", "ERROR", "Traceback", "AssertionError", "Exception:"]
    has_failure = any(m in result for m in failure_markers)
    if has_failure:
        return HookResult(decision=HookDecision.ALLOW, silent=False)

    # Detect 'all passing' patterns
    passing_patterns = [
        r"^All \d+ tests? passed",
        r"^OK \(\d+ tests?\)",
        r"^No issues found",
        r"^0 errors?, 0 warnings?",
        r"^Lint: clean",
        r"^Build successful",
    ]
    for pattern in passing_patterns:
        if re.match(pattern, result.strip()):
            return HookResult(
                decision=HookDecision.CLEAR,
                modified_payload={
                    **ctx.payload,
                    "tool_result": f"[swallowed: {ctx.tool_name} passed]",
                },
                reason="Passing result swallowed (success silent)",
                silent=True,
            )
    return HookResult(decision=HookDecision.ALLOW, silent=False)


def pre_tool_use_pii_tokenize(ctx: HookContext) -> HookResult:
    """
    Tokenize PII in tool args before execution.
    Delegates to pii_tokenizer (imported lazily to avoid circular).
    """
    # We don't tokenize args (they may need to be real for execution).
    # PII tokenization happens on tool_result (post).
    return HookResult(decision=HookDecision.ALLOW, silent=True)


def post_tool_use_pii_tokenize(ctx: HookContext) -> HookResult:
    """
    Tokenize PII in tool result after execution.
    """
    if not ctx.tool_result:
        return HookResult(decision=HookDecision.ALLOW, silent=True)

    # F-008 audit 2026-06-10: use the module-level singleton so the
    # same PII value maps to the same token across calls. Previously
    # a new PIITokenizer (with a fresh random salt) was created per
    # call, breaking deterministic tokenization.
    from .pii_tokenizer import get_tokenizer
    tokenizer = get_tokenizer()
    tokenized, mappings = tokenizer.tokenize(ctx.tool_result)

    if mappings:
        return HookResult(
            decision=HookDecision.MODIFY,
            modified_payload={
                **ctx.payload,
                "tool_result": tokenized,
                "pii_tokens": mappings,
            },
            reason=f"PII tokenized: {len(mappings)} items",
            silent=True,
        )
    return HookResult(decision=HookDecision.ALLOW, silent=True)


# === HOOK REGISTRY ===

HOOK_REGISTRY: Dict[HookEvent, list[Callable]] = {
    HookEvent.PRE_TOOL_USE: [
        pre_tool_use_block_destructive,
        pre_tool_use_check_budget,
        pre_tool_use_pii_tokenize,
    ],
    HookEvent.POST_TOOL_USE: [
        post_tool_use_pii_tokenize,
        post_tool_use_clear_result,        # Clear after PII
        post_tool_use_summarize_swallowed,  # Swallow passing results
    ],
    HookEvent.SUBAGENT_START: [],
    HookEvent.SUBAGENT_END: [],
    HookEvent.PHASE_START: [],
    HookEvent.PHASE_END: [],
    HookEvent.USER_MESSAGE: [],
}


class HookSystem:
    """Orchestrate all hooks."""

    def __init__(self):
        self.executed: list = []  # Audit trail

    def fire(self, ctx: HookContext) -> HookResult:
        """
        Fire all hooks for an event. First DENY wins, MODIFY chains.
        """
        handlers = HOOK_REGISTRY.get(ctx.event, [])
        modified_payload = ctx.payload
        for handler in handlers:
            r = handler(ctx)
            self.executed.append({
                "ts": datetime.now().isoformat(),
                "event": ctx.event.value,
                "handler": handler.__name__,
                "decision": r.decision.value,
                "reason": r.reason,
                "silent": r.silent,
            })
            if r.decision == HookDecision.DENY:
                return r
            if r.decision == HookDecision.MODIFY and r.modified_payload:
                modified_payload = r.modified_payload
                ctx.payload = modified_payload
            if r.decision == HookDecision.CLEAR and r.modified_payload:
                modified_payload = r.modified_payload
                ctx.payload = modified_payload
        return HookResult(
            decision=HookDecision.ALLOW,
            modified_payload=modified_payload,
            silent=True,
        )

    def audit_report(self) -> str:
        """Return audit trail."""
        lines = [f"# Hook audit: {len(self.executed)} executions"]
        deny_count = sum(1 for e in self.executed if e["decision"] == "DENY")
        clear_count = sum(1 for e in self.executed if e["decision"] == "CLEAR")
        modify_count = sum(1 for e in self.executed if e["decision"] == "MODIFY")
        allow_count = sum(1 for e in self.executed if e["decision"] == "ALLOW")
        lines.append(f"  ALLOW: {allow_count}, MODIFY: {modify_count}, CLEAR: {clear_count}, DENY: {deny_count}")
        return "\n".join(lines)


# === GLOBAL HOOK SYSTEM INSTANCE ===
_global_hooks = HookSystem()


def get_hooks() -> HookSystem:
    return _global_hooks
