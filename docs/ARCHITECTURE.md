# Architecture

> **Deep dive into the CE-Harness architecture.** For an overview, see [README.md](../README.md). For the spec, see [design/00-architecture.md](../design/00-architecture.md).

---

## 1. 5-layer context model

CE-Harness organizes the context into **5 distinct layers**, each with a clear responsibility:

```
┌─────────────────────────────────────────────────────────────┐
│ L0  Corpus (offline)                                        │
│    • skills/, playbooks/, distilled knowledge               │
│    • Always accessed via tool call, never injected in bulk   │
├─────────────────────────────────────────────────────────────┤
│ L1  Memory Blocks (MemGPT-style, addressable)               │
│    • persona, facts, episodic, semantic, procedural,        │
│      scratchpad                                              │
│    • Per-tenant keys, ACL, tamper detection                  │
├─────────────────────────────────────────────────────────────┤
│ L2  Phase / Session State (typed, queryable)                │
│    • SQLite WAL with HMAC-chained audit log                   │
│    • Token ledger (live, per-component, per-phase)          │
│    • ACE Playbook (versioned, dedup)                        │
├─────────────────────────────────────────────────────────────┤
│ L3  Working Context (token-budgeted, structured)             │
│    • 4-pillars Write/Select/Compress/Isolate                 │
│    • Pre-hydrate at phase start                             │
│    • Head/tail protection (lost-in-the-middle)              │
├─────────────────────────────────────────────────────────────┤
│ L4  Immediate LLM view (curated, head/tail-protected)        │
│    • Gate active, constraints, key facts                    │
│    • Recent decisions (tail)                                │
│    • Adversarial findings (tail)                            │
└─────────────────────────────────────────────────────────────┘
                              ↓ enforced by
┌─────────────────────────────────────────────────────────────┐
│ Hooks (7 lifecycle events)                                   │
│ Subagent firewall (isolation, summary-only return)         │
│ Token ledger (live, 60/70/85/95% triggers)                │
│ Adversarial gates (T1/T2/T3 + Drew Breunig 4 modes)       │
│ RotatingHMAC (forward secrecy, 24h epoch)                │
│ ACE playbook engine (self-improving)                       │
└─────────────────────────────────────────────────────────────┘
```

### L0 — Corpus

- **What**: The distilled knowledge base (40+ research sources, 30 findings, 20 anti-patterns)
- **When**: Only via tool call
- **Why**: Injecting the corpus in bulk causes "context rot" (Chroma 2025)
- **Module**: `corpus/sources/INDEX.md`, `corpus/findings/`, `corpus/anti-patterns/`

### L1 — Memory Blocks

- **What**: Typed, addressable memory slots per principal
- **When**: Explicitly by the LLM (read/write)
- **Why**: 6 types (persona, facts, episodic, semantic, procedural, scratchpad) map to LLM cognitive patterns
- **Module**: `lib/memory_blocks.py`

### L2 — State

- **What**: SQLite WAL with HMAC-chained audit log
- **When**: Continuous (per token, per phase, per gate)
- **Why**: Single source of truth, replayable, tamper-evident
- **Module**: `lib/state.py`, `lib/security.py`

### L3 — Working Context

- **What**: The 4-pillars discipline (Write/Select/Compress/Isolate)
- **When**: Per turn, per tool call
- **Why**: Maximize signal-to-noise ratio in the LLM window
- **Modules**: `lib/hooks.py`, `lib/ace_compact.py`, `lib/pre_hydrate.py`, `lib/subagent_firewall.py`

### L4 — LLM View

- **What**: The actual content sent to the LLM at each turn
- **When**: Per turn, after hooks fire
- **Why**: Critical elements in head/tail, never middle (lost-in-the-middle)
- **Module**: `lib/context_layout.py` (planned S2)

---

## 2. The 4-pillars context engineering

| Pillar | Goal | Implementation in CE-Harness |
|--------|------|-------------------------------|
| **Write** | Persist context outside the window | `lib/state.py` (SQLite WAL), `lib/memory_blocks.py` |
| **Select** | Pull only the relevant context | `lib/pre_hydrate.py`, `lib/srs_linter.py`, `lib/contract_validator.py` |
| **Compress** | Reduce token count while preserving structure | `lib/ace_compact.py` (ACE-style, NOT summarization), `lib/token_ledger.py` |
| **Isolate** | Split context across subagents with strict return | `lib/subagent_firewall.py` + `lib/subagent_validator.py` |

---

## 3. The 8 invariants

Every CE-Harness deployment enforces these 8 invariants:

1. **Token budget per phase** with 60/70/85/95% triggers
2. **Code-as-API** (NOT tool calling) — 98.7% economy (Anthropic, 2025-11)
3. **Subagent firewall** — isolated contexts, summary-only return
4. **Compaction ACE-style** — preserve events, NOT summarization (paper ACE, ICLR 2026)
5. **Layout head/tail** — critical elements in head/tail, never middle
6. **Adversarial gates** — T1/T2/T3 + Drew Breunig 4 modes
7. **Pre-hydrate per phase** — 60% of first turn is retrieval; pre-hydrate saves it
8. **Self-improving playbook (ACE)** — captures success/failure patterns, versioned, deduped

---

## 4. Data flow (per turn)

```
User message
    ↓
[UserMessage hook] UDL record + decision threshold classify
    ↓
L4 LLM view (curated)
    ↓
LLM produces response
    ↓
[PreToolUse hook] validate args + budget + scope
    ↓
Tool executed (sandboxed if code)
    ↓
[PostToolUse hook] PII tokenize + clear large results + silent on success
    ↓
State updated (SQLite WAL + token ledger)
    ↓
[Audit] RotatingHMAC chain appended
    ↓
[60/70/85/95% triggers] CC_NOW if needed
    ↓
Next turn
```

---

## 5. Subagent pattern

```
Lead agent
    ↓ (spawns with brief + budget + tools)
[SubagentStart hook] Init isolated context
    ↓
Subagent (separate process, separate context window)
    ↓
[Writes artifacts to state.db]
    ↓
[SubagentEnd hook] Extract summary
    ↓
Lead agent (receives only summary + refs, not transcript)
```

**Isolation guarantees**:
- Subagent never sees parent context
- Subagent only gets: brief + budget + limited tools
- Subagent writes to state.db (persistent)
- Lead receives summary DSL + pointers, not dump

**Measured impact**: 10.8× fewer tokens for equivalent task (vs single-agent).

---

## 6. Token budget triggers

| Trigger | % of soft cap | Action | Example |
|---------|---------------|--------|---------|
| 60% | INFO_60 | Consider CC proactively | "Phase at 60%, headroom available" |
| **70%** | **CC_NOW** | **Compaction Checkpoint mandatory** | "Phase at 70%, running CC..." |
| 85% | WARN_85 | Reduce tool loading or escalate | "Phase at 85%, suggest user input" |
| 95% | CRITICAL | End phase or abort | "Phase at 95%, abort imminent" |
| 100% (of hard cap) | ABORT | Phase aborted, escalate user | "Hard cap reached, abort" |

These triggers are **enforced** by `lib/token_ledger.py`. They cannot be bypassed.

---

## 7. Security architecture

CE-Harness implements **defense in depth**:

```
┌─────────────────────────────────────────────────────┐
│            EXTERNAL INTERFACES                        │
│   CLI / Python API / YAML / Hooks SDK / MCP         │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────▼─────────────┐
        │     ENFORCEMENT LAYER     │
        │   (7 hooks, 14 modules)   │
        └────────────┬─────────────┘
                     │
        ┌────────────▼─────────────┐
        │   5-LAYER CONTEXT MODEL    │
        └────────────┬─────────────┘
                     │
        ┌────────────▼─────────────┐
        │    STATE & STORAGE LAYER  │
        │  ┌──────┐ ┌──────┐ ┌─────┐│
        │  │SQLite│ │Vault │ │Memory││  Encrypted at rest
        │  └──────┘ └──────┘ └─────┘│  Per-tenant keys
        └────────────┬─────────────┘
                     │
        ┌────────────▼─────────────┐
        │       AUDIT LAYER         │
        │  RotatingHMAC chain       │  Forward secrecy
        │  CAB registry             │  HMAC-signed
        │  EOL registry             │  Tamper-evident
        └────────────────────────────┘
```

See [SECURITY.md](../SECURITY.md) for the full security policy and best practices.

---

## 8. Performance characteristics

### Measured

| Metric | Value | How |
|--------|-------|-----|
| Token economy (subagent search) | **10.8×** | `bin/ctxh-demo` |
| Subagent return compression | 28.6× | `lib/subagent_firewall.py` |
| Tests | 317/317 pass | `pytest tests/` |
| Swebok Council Bridge gates | 10/10 PASS | `audit/run_council_gates.sh` |
| Adversarial residual | 0 CRIT, 0 MED, 0 LOW | 4 successive passes |

### Theoretical (Anthropic 2025-11)

- Code-as-API: 98.7% economy vs tool calling
- Pre-hydrate: 2.5× gain on first turn

### Design targets (v1.1)

- P50 latency overhead: < 10ms per hook
- P99 latency overhead: < 50ms per hook
- Memory overhead: < 50MB for state.db + audit chain

---

## 9. Testing strategy

```
┌─────────────────────────────────────┐
│  UNIT TESTS (per module)             │  ← 150+ tests
├─────────────────────────────────────┤
│  INTEGRATION TESTS (per feature)     │  ← 70+ tests
├─────────────────────────────────────┤
│  ADVERSARIAL TESTS (5 vectors)       │  ← 94+ tests
│   - prompt_injection                 │
│   - pii_exfil                        │
│   - sandbox_escape                   │
│   - mcp_poisoning                    │
│   - state_tampering                  │
├─────────────────────────────────────┤
│  PROPERTY-BASED TESTS               │  ← 4 properties
│   - DSL roundtrip                    │
│   - PII idempotency                  │
│   - Validator strictness             │
│   - SHA-256 format                  │
├─────────────────────────────────────┤
│  PAYLOAD CORPUS                      │  ← 50+ payloads
│   - 5 attack vectors                 │
│   - tagged by target defense         │
└─────────────────────────────────────┘
```

**All 317 tests pass in < 5 seconds** on a standard laptop.

---

## 10. Where to go from here

- **Code** — Browse [prototype/lib/](../prototype/lib/) for 22 modules
- **Tests** — Browse [prototype/tests/](../prototype/tests/) for 317 tests
- **Audit** — Read [audit/](../audit/) for 8 reports documenting the validation
- **API** — See [API.md](API.md) for the Python reference
- **Patterns** — See [corpus/](../corpus/) for 40+ research sources
- **Hooks** — See [HOOKS.md](HOOKS.md) for the 7 lifecycle hooks

---

*Architecture document version 1.0 (2026-06-09). Maintained alongside the codebase.*
