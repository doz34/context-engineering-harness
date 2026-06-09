# Architecture of the Harness — CE-Harness v1.0

> **Date**: 2026-06-08
> **Status**: Validated v1 — implementation S1-S3
> **Inspired by**: Anthropic long-running harness, ACE (ICLR 2026), MemGPT/Letta, Addy Osmani harness engineering

---

## 1. Macro view

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL INTERFACES                            │
│  CLI (ctxh) │ Python API │ YAML/DSL config │ Hooks SDK │ MCP servers  │
└────────┬─────────────────────────────────────────────┬──────────────────┘
         │                                             │
         ▼                                             ▼
┌─────────────────────────────────┐  ┌──────────────────────────────────┐
│   L0 — Corpus (offline)         │  │   L1 — Memory Blocks            │
│   skills/ playbooks/ corpus/    │  │   persona, facts, episodic,      │
│   never injected in bulk        │  │   semantic, procedural          │
└────────┬────────────────────────┘  └──────────┬───────────────────────┘
         │                                       │
         ▼                                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│              L2 — PHASE/SESSION STATE (SQLite + WAL)                 │
│  ┌────────────┐ ┌─────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │ State DB   │ │ Token Ledger│ │ ACE Playbook │ │ HMAC Chain   │   │
│  └────────────┘ └─────────────┘ └──────────────┘ └──────────────┘   │
└────────┬─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│              L3 — WORKING CONTEXT (4-pillars)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                 │
│  │  WRITE   │ │ SELECT   │ │ COMPRESS │ │ ISOLATE  │                 │
│  │ scratchpad│ │  pre-    │ │ compaction│ │ subagent │                 │
│  │  memory  │ │ hydrate  │ │   ACE   │ │ firewall │                 │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                 │
└────────┬─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│              L4 — IMMEDIATE LLM VIEW (curated)                       │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │ HEAD : gate, budget, constraints phase, top decisions      │      │
│  │ MIDDLE : working context, retrieved data                  │      │
│  │ TAIL : adversarial findings, recent decisions, UDL         │      │
│  └────────────────────────────────────────────────────────────┘      │
└────────┬─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│            ENFORCEMENT LAYER (Hooks + Gates)                         │
│  PreToolUse │ PostToolUse │ SubagentStart │ SubagentEnd │ PhaseStart │
│  T1 casseur │ T2 spec     │ T3 aval      │ Drew 4-modes              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Software components (mapping)

| Component | Language | Dependencies | Status |
|-----------|----------|--------------|--------|
| `bin/ctxh` (CLI) | Python 3.11+ | typer, rich | To code S1 |
| `lib/state.py` | Python | sqlite3 (stdlib) | To code S1 |
| `lib/token_ledger.py` | Python | tiktoken (optional) | To code S1 |
| `lib/dsl.py` | Python | pyyaml | To code S1 |
| `lib/hooks.py` | Python | stdlib | To code S2 |
| `lib/subagent_firewall.py` | Python | stdlib | To code S1 |
| `lib/code_api.py` | Python | RestrictedPython | To code S3 |
| `lib/ace_compact.py` | Python | stdlib | To code S2 |
| `lib/pii_tokenizer.py` | Python | stdlib | To code S2 |
| `lib/subagent_validator.py` | Python | stdlib | To code S2 |
| `lib/security.py` | Python | stdlib + cryptography optional | To code S2 |
| `lib/srs_linter.py` | Python | stdlib | To code S2 |
| `lib/mcp_trust.py` | Python | stdlib | To code S2 |
| `lib/secrets_vault.py` | Python | stdlib | To code S2 |
| `lib/contract_validator.py` | Python | pyyaml optional | To code S2 |
| `lib/memory_blocks.py` | Python | stdlib | To code S2 |
| `lib/mutation_testing.py` | Python | stdlib | To code S2 |
| `lib/ci_cd_pinning.py` | Python | stdlib | To code S3 |
| `lib/image_pin.py` | Python | stdlib | To code S3 |
| `lib/state.py` (audited) | Python | stdlib | To code S3 |
| `lib/archive_anonymizer.py` | Python | stdlib | To code S3 |
| `lib/adversarial_corpus.py` | Python | stdlib | To code S3 |
| `lib/property_tests.py` | Python | stdlib | To code S3 |
| `lib/s3_residual.py` | Python | stdlib | To code S3 |
| `lib/prompts/*.md` | Markdown | — | To write S1 |
| `bin/install.sh` | Bash | curl, pip | To code S1 |
| `tests/test_*.py` | Python | pytest | To code S1+ |

**Target volume v1.0**: ~3000 LOC Python + ~500 LOC Bash + ~2000 LOC Markdown.

---

## 3. The State DB (L2)

SQLite WAL, schema:

```sql
-- Session-level (one row per session)
CREATE TABLE session (
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  status TEXT CHECK(status IN ('active','paused','closed','error')),
  current_phase TEXT,
  metadata JSON
);

-- Phase-level (one row per phase activation)
CREATE TABLE phase (
  id TEXT PRIMARY KEY,
  session_id TEXT,
  name TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  status TEXT CHECK(status IN ('pending','active','complete','aborted','failed')),
  budget_soft_cap INTEGER,  -- tokens
  budget_hard_cap INTEGER,  -- tokens
  tokens_used INTEGER DEFAULT 0
);

-- Token ledger (per-component, per-phase, append-only)
CREATE TABLE token_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  phase_id TEXT,
  component TEXT,  -- 'system_prompt','tools','messages','retrieval','tool_result','output'
  direction TEXT CHECK(direction IN ('input','output')),
  tokens INTEGER,
  model TEXT,
  metadata JSON
);

-- Memory blocks (MemGPT-style, addressable)
CREATE TABLE memory_block (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  name TEXT NOT NULL,
  content TEXT NOT NULL,
  owner TEXT NOT NULL,  -- tenant/principal
  version INTEGER DEFAULT 1,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  metadata JSON,
  hash TEXT  -- HMAC of content for tamper detection
);

-- ACE Playbook entries (versioned, deduped)
CREATE TABLE playbook (
  id TEXT PRIMARY KEY,
  bullet TEXT NOT NULL,  -- the "learned" insight
  score REAL DEFAULT 0.0,  -- promote/demote
  times_applied INTEGER DEFAULT 0,
  times_helped INTEGER DEFAULT 0,
  times_hurt INTEGER DEFAULT 0,
  version INTEGER DEFAULT 1,
  tags JSON,
  embedding BLOB,  -- for dedup, optional
  created_at TEXT NOT NULL,
  updated_at TEXT,
  hash TEXT
);

-- HMAC chain (tamper-evident log)
CREATE TABLE audit_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  event_type TEXT,  -- 'phase_start','phase_end','tool_call','gate_decision',...
  payload JSON,
  prev_hash TEXT,
  hash TEXT NOT NULL  -- HMAC of (payload || prev_hash)
);

-- Gates (adversarial)
CREATE TABLE gate (
  id TEXT PRIMARY KEY,
  phase_id TEXT REFERENCES phase(id),
  role TEXT CHECK(role IN ('T1','T2','T3','drew_poisoning','drew_distraction','drew_confusion','drew_clash')),
  verdict TEXT CHECK(verdict IN ('PASS','FAIL','WARN')),
  rationale TEXT,
  ts TEXT NOT NULL
);

-- User Decision Ledger (UDL)
CREATE TABLE user_decision (
  id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  phase_id TEXT REFERENCES phase(id),
  context_snapshot JSON,
  options JSON,
  decision TEXT,
  reversibility TEXT CHECK(reversibility IN ('high','medium','low','none'))
);
```

**Critical indexes**:
- `idx_token_event_phase` on `(phase_id, ts)`
- `idx_playbook_score` on `score DESC`
- `idx_audit_event_ts` on `ts`
- `idx_memory_block_type` on `type`

---

## 4. The Token Ledger (critical component)

**Objective**: measure, in real time, where tokens go.

**Granularity**:
- Per **session** (total)
- Per **phase** (P0-P10 or custom)
- Per **component** (`system_prompt`, `tools`, `messages`, `retrieval`, `tool_result`, `output`)
- Per **model** (`claude-opus-4-8`, `gpt-5.5`, `qwen36-27b`, etc.)
- Per **agent** (lead, subagent name)
- Per **turn**

**API**:

```python
from lib.token_ledger import TokenLedger

ledger = TokenLedger(state_db="state.db")
ledger.start_phase("P3_ARCHITECTURE", soft_cap=8000, hard_cap=15000)
ledger.record(
    component="messages",
    direction="input",
    tokens=1200,
    model="claude-opus-4-8",
    metadata={"turn": 1, "agent": "lead"}
)
# → Triggers at 70%, 85%, 95% of soft_cap

# Query
top_components = ledger.top_components(phase="P3_ARCHITECTURE", limit=5)
# → [("messages", 5400), ("tools", 1800), ("retrieval", 800), ...]

# Dashboard
ledger.dashboard()  # Rich text output
```

**Automatic triggers**:

- **70% of soft cap**: CC (Compaction Checkpoint) required
- **85% of soft cap**: WARN displayed + suggestion of escalation
- **95% of soft cap**: HARD WARN + automatic reduction of loaded tools
- **100% of hard cap**: ABORT phase, escalate user

---

## 5. The Subagent Firewall (I3)

**Pattern**: each subagent is an **isolated process** with a **dedicated context window** and a **strict return contract**.

```python
from lib.subagent_firewall import spawn_subagent

result = spawn_subagent(
    role="code_searcher",  # NOT 'engineer', but a context-controlled role
    brief=dsl_brief(  # structured 4-champs
        OBJECT="Find all call sites of the function 'parse_query' across the codebase",
        FORMAT="JSON: {file: str, line: int, code: str}[]",
        TOOLS=["grep", "read"],  # limited tool set
        BOUND="max 20 results, max 5 minutes, no file modifications"
    ),
    context_budget=4000,
    parent_phase="P3_ARCHITECTURE",
    model="claude-sonnet-4-5",  # cheaper for subagent
)
# → Returns only summary + refs, never full transcript
print(result.summary)
print(result.refs)  # ["src/parser.py:142", "src/lexer.py:88", ...]
print(result.artifacts)  # paths to files written
```

**Guarantees**:
- The subagent NEVER sees the parent context
- The subagent only receives the brief + budget + limited tools
- The subagent writes to `state.db` (persistent artifact)
- The parent receives a **summary DSL** + **pointers**, not a dump

**Security metaphor**: "Context firewall" (HumanLayer 2026-03). The subagent is in an isolated VM.

---

## 6. The Code-as-API (I2)

**Pattern Anthropic 2025-11**: expose tools as code, not as tool calling.

```
servers/
├── google-drive/
│   ├── getDocument.ts
│   ├── listFiles.ts
│   └── index.ts
├── salesforce/
│   ├── updateRecord.ts
│   └── index.ts
└── ...
```

**Measured benefit**: 150K tokens (tools in JSON) → 2K tokens (code API), **98.7% economy**.

**Our implementation**:

```python
# lib/code_api.py
class CodeAPIRunner:
    def discover_tools(self, servers_dir="servers/"):
        """List available tools via filesystem (no injection in context)."""
        
    def run_tool(self, server, tool, input_data):
        """Execute tool in sandbox, return result (sandboxed, not in context)."""
        
    def agent_can_use(self, sandbox: CodeAPISandbox, code: str) -> SandboxResult:
        """Validate that agent-written code is safe to run."""
```

**Use case**: the agent navigates the `servers/` filesystem to find the right tool, reads the code, calls it. The result stays in the sandbox unless explicitly logged.

---

## 7. The Compaction ACE-style (I4)

**Inspired by**: ACE paper (arXiv 2510.04618, ICLR 2026)

**Difference vs summarization**:
- **Summarization**: paraphrase, loses details
- **Compaction ACE**: preserve structure + details, dedupe, version

**API**:

```python
from lib.ace_compact import compact

result = compact(
    context=current_context,
    preserve=["events", "decisions", "constraints", "gate_findings"],
    dedup=True,  # semantic dedup of similar items
    target_budget=2000,  # tokens
)
# Returns compacted context + compaction_id + delta_report
```

**Mechanism**:
1. Identify **discrete events** (vs prose)
2. Deduplicate semantically
3. Group by theme
4. Preserve timestamps and hashes
5. Emit a delta_report (what was preserved vs eliminated)

**Avoids**:
- **Brevity bias**: loss of critical details
- **Context collapse**: iterative degradation

---

## 8. The Context Layout (I5)

**Pattern**: head/tail protection against lost-in-the-middle.

**Schema**:

```
[ HEAD: Critical (1-2K tokens) ]
  - Current gate state
  - Phase budget + ledger summary
  - Top-3 user decisions
  - Critical constraints (security, compliance)
  - Active subagent contracts

[ MIDDLE: Working context (3-6K tokens) ]
  - Current task description
  - Retrieved data (RAG results)
  - Tool definitions (only what's needed)
  - Conversation history (compacted)

[ TAIL: Recent + adversarial (1-2K tokens) ]
  - Last 3 turns
  - Recent adversarial findings
  - Recent decisions
  - Next-step reminder
```

**Implementation**:

```python
from lib.context_layout import build_layout

context = build_layout(
    head=head_items,  # OrderedDict, key=position
    middle=middle_items,
    tail=tail_items,
    budget=8000,
)
```

**Test**: Lost-in-the-middle audit = place critical elements in middle, verify they are **rejected** by the layout.

---

## 9. The Pre-hydrate (I7)

**Inspired by**: Cognition Labs (60% of first turn = retrieval), Anthropic long-running harness.

**API**:

```python
from lib.pre_hydrate import pre_hydrate

state = pre_hydrate(
    phase="P3_ARCHITECTURE",
    session=session_id,
    expected_needs=[
        "ADRs from P2",
        "NFRs from P2",
        "Code conventions from repo",
        "Existing components from codebase",
    ],
)
# → state.db now contains hot_context with pre-resolved refs
```

**Mechanism**:
- At phase entry, identify what the agent will need to look up
- Pre-load in `state.db` (not in LLM context, but accessible in 1 call)
- Reduce the first turn from 60% retrieval to ~20% (2.5× gain)

---

## 10. The Adversarial Gates (I6)

**3 roles + 4 modes**:

```python
from lib.adversarial_gate import Gate

# T1 — Breaker
verdict = Gate(role="T1").check(
    artifact=spec_p3,
    attack_vectors=[
        "internal_contradiction",
        "missing_constraint",
        "ambiguous_term",
        "non_measurable_requirement",
    ],
)

# T2 — Spec compliance
verdict = Gate(role="T2").check(
    artifact=code_p5,
    spec=spec_p2,
    adrs=adrs_p3,
    nfrs=nfrs_p2,
)

# T3 — Downstream (P+1 prediction)
verdict = Gate(role="T3").predict(
    artifact=code_p5,
    next_phase_contracts=contracts_p6,
    future_nfrs=nfrs_p7,
)

# Drew Breunig 4 modes
for mode in ['poisoning', 'distraction', 'confusion', 'clash']:
    verdict = Gate(role=f"drew_{mode}").check(
        context=current_context,
        source=phase_outputs,
    )
```

**Verdict**: `PASS | WARN | FAIL`. FAIL = retry or escalate. WARN = continue with log.

---

## 11. The Playbook ACE (I8)

**Inspired by**: ACE paper (ICLR 2026) — self-improving contexts.

**Mechanism**:
- At each outcome (gate verdict, user decision), capture the insight
- Store in `playbook` table with score
- Deduplicate semantically (embeddings, optional)
- Promote/demote based on outcomes

**API**:

```python
from lib.ace_playbook import Playbook

pb = Playbook(state_db="state.db")

# Capture
pb.add(
    bullet="When token budget > 70%, trigger CC before next tool call",
    tags=["budget", "compaction"],
    source_phase="P3_ARCHITECTURE",
)

# Promote on success
pb.promote(bullet_id, helped=True)

# Demote on failure
pb.demote(bullet_id, hurt=True)

# Get top bullets for current context
relevant = pb.retrieve(query="compaction strategy", top_k=5)
```

**Self-improving cycle**: Phase 1 produces 50 bullets. Phase 10 has retained 12 (score > 0.7), 38 fell (score < 0.3). The playbook grows in quality, not in size.

---

## 12. The HMAC Chain (audit)

**Pattern**: Cossack Labs 2025, RJV Audit Vault.

**Implementation**:

```python
import hmac, hashlib, json

class HMACChain:
    def __init__(self, key_path=".audit_key"):
        with open(key_path, "rb") as f:
            self.key = f.read()

    def append(self, event_type, payload, prev_hash=""):
        event = {
            "ts": now(),
            "type": event_type,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        content = json.dumps(event, sort_keys=True).encode()
        h = hmac.new(self.key, content, hashlib.sha256).hexdigest()
        event["hash"] = h
        return event["hash"]

    def verify(self):
        """Replay all events, verify chain integrity."""
        ...
```

**Usage**: all events (phase_start, phase_end, tool_call, gate_decision, ledger_event) are hashed and chained. Modification = broken chain = detected.

---

## 13. The DSL (KEY:VALUE;;KEY:VALUE)

**Inspired by**: swebok-v4-harness DSL, Anthropic subagent brief 4-champs.

**Format**:
```
KEY1:VALUE1;;KEY2:VALUE2;;KEY3:VALUE3
```

**Advantages**:
- Human-readable
- Machine-parseable (simple regex)
- Readable as plain text (no JSON braces)
- Terminal compatible (newline-safe)

**Use cases**:
- Subagent brief: `OBJECT:...;;FORMAT:...;;TOOLS:...;;BOUND:...`
- Gate verdict: `VERDICT:PASS;;RATIONALE:...;;FINDINGS:...`
- Phase transition: `PHASE:P4_DESIGN;;STATUS:ACTIVE;;BUDGET:8000`
- Token event: `COMPONENT:MESSAGES;;DIRECTION:INPUT;;TOKENS:1200;;MODEL:CLAUDE-OPUS-4-8`

**Parser**:

```python
def parse_dsl(line: str) -> dict:
    """Parse KEY:VALUE;;KEY:VALUE format."""
    if not line or "::" not in line and ":" not in line:
        return {}
    pairs = line.split(";;")
    result = {}
    for p in pairs:
        if ":" not in p:
            continue
        k, v = p.split(":", 1)
        result[k.strip()] = v.strip()
    return result
```

---

## 14. Hooks (lifecycle)

**7 lifecycle hooks**:

| Hook | When | Action |
|------|-------|--------|
| `PreToolUse` | Before each tool call | Validate args, budget, scope |
| `PostToolUse` | After tool call | Clear result, log, dedup |
| `SubagentStart` | Before subagent spawn | Init isolated context, return contract |
| `SubagentEnd` | After subagent complete | Summary extraction, firewall check |
| `PhaseStart` | Phase begin | Pre-hydrate, budget init, gate init |
| `PhaseEnd` | Phase end | Compaction, ledger snapshot, gate audit |
| `UserMessage` | Each user msg | UDL record, decision threshold classify |

**Implementation**: each hook = a Python script in `hooks/` with a function `def main(event): ...`.

---

## 15. Distribution & installation

```bash
# Install
curl -fsSL https://raw.githubusercontent.com/doz34/context-engineering-harness/main/install.sh | bash
# or
pip install ctxh  # PyPI

# Init in a project
cd my-project
ctxh init
# Creates: .ctxh/state.db, .ctxh/CLAUDE.md, .ctxh/hooks/

# Usage
ctxh measure --demo  # Token ledger demo
ctxh run --phase P3_ARCHITECTURE --brief brief.dsl
ctxh compact --target 2000
ctxh gate --role T1 --artifact spec.md
```

---

## 16. Tests & validation

- **Unit tests**: pytest, 100% coverage target
- **Integration tests**: harness on 5 real use cases
- **Adversarial tests**: 4 Drew Breunig modes × 3 T-rôles
- **Benchmark**: 3-5× economy measured vs baseline
- **Acceptance**: 5 pilot projects validate in production

---

## 17. Technical roadmap

| Sprint | Target | Effort | Acceptance criterion |
|--------|--------|--------|----------------------|
| S1 | POV (Proof of Value) | M | Token ledger live + 1 use case end-to-end |
| S2 | MVP | M | 5 hooks + state machine + ledger + 4-failure-mode gates |
| S3 | Beta | L | Code-as-API + ACE playbook + memory blocks |
| S4 | v1.0 | L | Production-ready, adversarial tests, PyPI |

---

*Architecture written 2026-06-08 by discovery-orchestrator. 17 sections, 17 invariants. To be revised after S1. v1.0 release 2026-06-09.*
