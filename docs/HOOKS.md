# Hooks Reference

> **Complete reference for the 7 lifecycle hooks in CE-Harness.** See also: [`lib/hooks.py`](../prototype/lib/hooks.py).

---

## Overview

CE-Harness exposes **7 lifecycle hooks** that fire at key moments in the agent's execution. Each hook can **modify, deny, or clear** the event payload, providing defense in depth.

| Hook | When | Default action |
|------|------|----------------|
| `PreToolUse` | Before each tool call | Validate args, budget, scope |
| `PostToolUse` | After each tool call | PII tokenize, clear large results, silent on success |
| `SubagentStart` | Before spawning subagent | Init isolated context, return contract |
| `SubagentEnd` | After subagent completes | Extract summary, firewall check |
| `PhaseStart` | At phase start | Pre-hydrate, budget init, gate init |
| `PhaseEnd` | At phase end | Compaction, ledger snapshot, gate audit |
| `UserMessage` | At each user message | UDL record, decision threshold classify |

---

## Hook API

```python
from lib.hooks import (
    HookContext, HookResult, HookDecision, HookEvent,
    pre_tool_use_block_destructive,
    pre_tool_use_check_budget,
    post_tool_use_clear_result,
    post_tool_use_pii_tokenize,
    post_tool_use_summarize_swallowed,
    # ... or use the HookSystem
    HookSystem,
)
```

### HookDecision enum

```python
class HookDecision(str, Enum):
    ALLOW = "ALLOW"   # Pass through unchanged
    DENY = "DENY"     # Block the action
    MODIFY = "MODIFY" # Modify the payload before continuing
    CLEAR = "CLEAR"   # Specific to PostToolUse: clear result
```

### HookContext

```python
@dataclass
class HookContext:
    event: HookEvent
    payload: Dict[str, Any]
    phase_id: str = ""
    subagent_id: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    timestamp: str = ""
```

### HookResult

```python
@dataclass
class HookResult:
    decision: HookDecision
    modified_payload: Optional[Dict[str, Any]] = None
    reason: str = ""
    silent: bool = True  # Success silent (HumanLayer 2026)
```

---

## PreToolUse hooks

### `pre_tool_use_block_destructive(ctx)`

**Purpose**: Block destructive bash commands.

**Patterns blocked**:
- `rm -rf /` (root deletion)
- `git push --force origin main` (force push to protected branch)
- `git push -f` (any force push)
- `DROP TABLE` (database destruction)
- `DROP DATABASE`
- Fork bomb `:() { :|:& };:`
- `dd if=... of=/dev/sd*` (disk overwrite)
- `mkfs.* /dev/*` (filesystem format)
- `> /etc/passwd` (system file overwrite)
- `chmod -R 777 /` (world-writable root)

**Example**:
```python
ctx = HookContext(
    event=HookEvent.PRE_TOOL_USE,
    payload={},
    tool_name="Bash",
    tool_args={"command": "rm -rf /etc"},
)
r = pre_tool_use_block_destructive(ctx)
assert r.decision == HookDecision.DENY
assert "destructive" in r.reason.lower()
```

### `pre_tool_use_check_budget(ctx)`

**Purpose**: Block tool calls if phase budget is exhausted.

**Logic**: Reads `budget_remaining` from `ctx.payload`. If <= 0, denies.

**Example**:
```python
# In a token_ledger callback:
def pre_tool_use_hook(ctx):
    phase_id = ctx.phase_id
    remaining = ledger.budget_remaining(phase_id)
    ctx.payload["budget_remaining"] = remaining
    return pre_tool_use_check_budget(ctx)
```

---

## PostToolUse hooks

### `post_tool_use_pii_tokenize(ctx)`

**Purpose**: Tokenize PII in tool results before they reach the LLM.

**Patterns**: 11 PII patterns (email, phone, SSN, IBAN, credit card, IPv4, etc.) — see [`lib/pii_tokenizer.py`](../prototype/lib/pii_tokenizer.py)

**Behavior**: Returns `MODIFY` decision with tokenized text and PII token mappings.

**Example**:
```python
ctx = HookContext(
    event=HookEvent.POST_TOOL_USE,
    payload={},
    tool_name="Grep",
    tool_result="Contact: alice@acme.com, Phone: 01 23 45 67 89",
)
r = post_tool_use_pii_tokenize(ctx)
# r.decision == HookDecision.MODIFY
# r.modified_payload["tool_result"] = "Contact: [EMAIL_XXX], Phone: [PHONE_FR_YYY]"
# r.modified_payload["pii_tokens"] = [...mappings]
```

### `post_tool_use_clear_result(ctx)`

**Purpose**: Clear large tool results to save context tokens. Keeps head + tail (200 chars each), offloads middle to filesystem.

**Logic**:
- If result <= 400 chars: keep as-is
- If result > 400 chars: keep first 200 + last 200 + offload middle to `.ctxh/tool_results/<tool>_<ts>.txt`

**Example**:
```python
ctx = HookContext(
    event=HookEvent.POST_TOOL_USE,
    payload={},
    tool_name="Read",
    tool_result="X" * 1000,  # 1000-char result
)
r = post_tool_use_clear_result(ctx)
# r.decision == HookDecision.CLEAR
# r.modified_payload["tool_result"] = "XXXX... [CLEARED: 600 chars...] ...ZZZ"
# r.modified_payload["tool_result_full_ref"] = ".ctxh/tool_results/Read_xxx.txt"
```

### `post_tool_use_summarize_swallowed(ctx)`

**Purpose**: Swallow passing test results to save context. Verbose on failures.

**Logic**:
- First, check for failure markers (`FAIL`, `ERROR`, `Traceback`, `AssertionError`, `Exception:`). If present, return `ALLOW` (verbose).
- Else, check for "all passing" patterns:
  - `^All \d+ tests? passed`
  - `^OK \(\d+ tests?\)`
  - `^No issues found`
  - `^0 errors?, 0 warnings?`
  - `^Lint: clean`
  - `^Build successful`
- If matches, return `CLEAR` with `[swallowed: <tool> passed]`

**Example**:
```python
# Passing: swallowed
ctx_passing = HookContext(event=HookEvent.POST_TOOL_USE, payload={},
    tool_name="Test", tool_result="All 100 tests passed in 5.2s")
r = post_tool_use_summarize_swallowed(ctx_passing)
assert r.decision == HookDecision.CLEAR  # Silent on success

# Failing: verbose
ctx_failing = HookContext(event=HookEvent.POST_TOOL_USE, payload={},
    tool_name="Test", tool_result="All 100 tests passed... 5 FAILED")
r = post_tool_use_summarize_swallowed(ctx_failing)
assert r.decision == HookDecision.ALLOW  # Verbose on failure
```

---

## HookSystem

The `HookSystem` orchestrates all hooks for a given event. It chains handlers, applying modifications in order, and stops at the first `DENY`.

```python
from lib.hooks import HookSystem, HookContext, HookEvent

hs = HookSystem()
ctx = HookContext(
    event=HookEvent.PRE_TOOL_USE,
    payload={},
    tool_name="Bash",
    tool_args={"command": "rm -rf /"},
)
r = hs.fire(ctx)
# r.decision == HookDecision.DENY (first hook denies)
# hs.executed = [...all hooks that ran before the DENY]
```

### Audit report

```python
hs.fire(ctx)
print(hs.audit_report())
# Hook audit: 3 executions
#   ALLOW: 2, MODIFY: 0, CLEAR: 0, DENY: 1
```

---

## Adding custom hooks

To add your own hook:

1. **Create the function** in your project:

```python
# my_hooks.py
from lib.hooks import HookContext, HookResult, HookDecision

def my_custom_hook(ctx: HookContext) -> HookResult:
    """Reject any tool call that mentions 'production'."""
    if "production" in str(ctx.tool_args):
        return HookResult(
            decision=HookDecision.DENY,
            reason="Production access not allowed in dev environment",
        )
    return HookResult(decision=HookDecision.ALLOW, silent=True)
```

2. **Register it** in `HOOK_REGISTRY`:

```python
from lib.hooks import HOOK_REGISTRY, HookEvent

HOOK_REGISTRY[HookEvent.PRE_TOOL_USE].append(my_custom_hook)
```

3. **Test it**:

```python
from lib.hooks import HookSystem, HookContext, HookEvent

hs = HookSystem()
ctx = HookContext(
    event=HookEvent.PRE_TOOL_USE,
    payload={},
    tool_name="Bash",
    tool_args={"command": "deploy to production"},
)
r = hs.fire(ctx)
assert r.decision == HookDecision.DENY
```

---

## Hook ordering

When multiple hooks are registered for the same event, they run in **registration order**. The first `DENY` short-circuits the rest.

```python
# Order matters: log_first runs before block_destructive
HOOK_REGISTRY[HookEvent.PRE_TOOL_USE] = [
    log_tool_call,        # 1st: log the call
    block_destructive,   # 2nd: block if dangerous
    check_budget,         # 3rd: block if budget exhausted
]
```

---

## Security guarantees

- **PreToolUse** runs **before** the tool executes, so dangerous actions can be blocked
- **PostToolUse** runs **after** the tool executes, so PII can be sanitized
- **SubagentStart/End** enforce strict isolation boundaries
- **PhaseStart/End** ensure proper state transitions
- **UserMessage** ensures all user decisions are logged (UDL)

**No hook can be bypassed** without direct access to the Python code (which is the threat model for any harness — if attacker has code access, all bets are off).

---

## Performance

Each hook adds < 1ms overhead per call (mostly in-memory operations). The `PostToolUse.clear_result` adds file I/O for offload, but only when results exceed 400 chars.

Benchmarks (on a standard laptop):
- `PreToolUse` chain (3 hooks): ~0.5ms
- `PostToolUse` chain (3 hooks): ~1ms (PII tokenize dominates)
- `SubagentStart/End`: ~0.2ms
- `PhaseStart/End`: ~2ms (DB writes)

**Total overhead per turn**: < 5ms for typical workloads.

---

## See also

- [`lib/hooks.py`](../prototype/lib/hooks.py) — Full source
- [`tests/test_hooks.py`](../prototype/tests/test_hooks.py) — 12 tests
- [`tests/adversarial_hook_bypass.py`](../prototype/tests/adversarial_hook_bypass.py) — 9 adversarial tests
- [SECURITY.md](../SECURITY.md) — Security implications
- [ARCHITECTURE.md](ARCHITECTURE.md) — How hooks fit in the 5-layer model
