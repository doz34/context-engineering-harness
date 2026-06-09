# Architecture du Harness — CE-Harness v1.0

> **Date** : 2026-06-08
> **Statut** : Validé v1 — implémentation S1-S4
> **Inspiré de** : Anthropic long-running harness, ACE, MemGPT/Letta, Addy Osmani harness engineering

---

## 1. Vue macro

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL INTERFACES                            │
│  CLI (ctxh) │ Python API │ YAML/DSL config │ Hooks SDK │ MCP servers  │
└────────┬─────────────────────────────────────────────┬──────────────────┘
         │                                             │
         ▼                                             ▼
┌─────────────────────────────────┐  ┌──────────────────────────────────┐
│   L0 — CORPUS (offline)         │  │   L1 — MEMORY BLOCKS            │
│   skills/ playbooks/ corpus/    │  │   persona, facts, episodic,      │
│   jamais injecté en bloc        │  │   semantic, procedural           │
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
│  │ HEAD : gate, budget, contraintes phase, top decisions      │      │
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

## 2. Composants logiciels (mapping)

| Composant | Langage | Dépendances | Statut |
|-----------|---------|-------------|--------|
| `bin/ctxh` (CLI) | Python 3.11+ | typer, rich | À coder S1 |
| `lib/state.py` | Python | sqlite3 (stdlib) | À coder S1 |
| `lib/token_ledger.py` | Python | tiktoken (optional) | À coder S1 |
| `lib/dsl.py` | Python | pyyaml | À coder S1 |
| `lib/hooks.py` | Python | stdlib | À coder S2 |
| `lib/subagent_firewall.py` | Python | stdlib | À coder S1 |
| `lib/code_api.py` | Python | RestrictedPython | À coder S3 |
| `lib/ace_compact.py` | Python | stdlib | À coder S2 |
| `lib/ace_playbook.py` | Python | stdlib, sqlite | À coder S3 |
| `lib/memory_blocks.py` | Python | stdlib | À coder S3 |
| `lib/context_layout.py` | Python | stdlib | À coder S2 |
| `lib/pre_hydrate.py` | Python | stdlib | À coder S2 |
| `lib/adversarial_gate.py` | Python | stdlib, sqlite | À coder S2 |
| `lib/drew_modes.py` | Python | stdlib | À coder S2 |
| `lib/hmac_chain.py` | Python | hmac (stdlib) | À coder S2 |
| `lib/prompts/*.md` | Markdown | — | À rédiger S1 |
| `bin/install.sh` | Bash | curl, pip | À coder S1 |
| `tests/test_*.py` | Python | pytest | À coder S1+ |

**Volumétrie cible v1.0** : ~3000 LOC Python + ~500 LOC Bash + ~2000 LOC Markdown.

## 3. Le State DB (L2)

SQLite WAL, schema :

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
  session_id TEXT REFERENCES session(id),
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
  phase_id TEXT REFERENCES phase(id),
  component TEXT,  -- 'system_prompt','tools','messages','retrieval','tool_result','output'
  direction TEXT CHECK(direction IN ('input','output')),
  tokens INTEGER,
  model TEXT,
  metadata JSON
);

-- Memory blocks (MemGPT-style, addressable)
CREATE TABLE memory_block (
  id TEXT PRIMARY KEY,
  type TEXT CHECK(type IN ('persona','facts','episodic','semantic','procedural','scratchpad')),
  name TEXT,
  content TEXT,
  metadata JSON,
  version INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT,
  hash TEXT  -- HMAC of (content + prev_hash) for chain
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

**Index critiques** :
- `idx_token_event_phase` sur `(phase_id, ts)`
- `idx_playbook_score` sur `score DESC`
- `idx_audit_event_ts` sur `ts`
- `idx_memory_block_type` sur `type`

## 4. Le Token Ledger (composant critique)

**Objectif** : mesurer, en temps réel, où vont les tokens.

**Granularité** :
- Par **session** (total)
- Par **phase** (P0-P10 ou custom)
- Par **composant** (`system_prompt`, `tools`, `messages`, `retrieval`, `tool_result`, `output`)
- Par **modèle** (`claude-opus-4-8`, `gpt-5.5`, `qwen36-27b`, etc.)
- Par **agent** (lead, subagent name)
- Par **turn**

**API** :

```python
from lib.token_ledger import TokenLedger

ledger = TokenLedger(state_db="state.db")
ledger.start_phase(phase="P3_ARCHITECTURE", soft_cap=8000, hard_cap=15000)
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

**Triggers automatiques** :

- **70% du soft cap** : CC (Compaction Checkpoint) obligatoire
- **85% du soft cap** : WARN affiché + suggestion d'escalade
- **95% du soft cap** : HARD WARN + réduction automatique des tools chargés
- **100% du hard cap** : ABORT phase, escalate user

## 5. Le Subagent Firewall (I3)

**Pattern** : Chaque subagent est un **processus isolé** avec un **context window dédié** et un **return contract strict**.

**API** :

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
# → Returns only summary + ref, never full transcript
print(result.summary)
print(result.refs)  # ["src/parser.py:142", "src/lexer.py:88", ...]
print(result.artifacts)  # paths to files written
```

**Garanties** :
- Le subagent ne voit **jamais** le contexte parent
- Le subagent ne reçoit que le brief + budget + tools limités
- Le subagent écrit dans `state.db` (artefact persistant)
- Le parent reçoit un **résumé DSL** + **pointeurs**, pas un dump

**Métaphor security** : "Context firewall" (HumanLayer 2026-03). Le subagent est dans une VM isolée.

## 6. Le Code-as-API (I2)

**Pattern Anthropic 2025-11** : exposer les tools comme du code, pas comme du tool calling.

**Implémentation** :

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

**Avantage mesuré** : 150K tokens (tools en JSON) → 2K tokens (code API), **98.7% économie**.

**Notre implémentation** :

```python
# lib/code_api.py
class CodeAPIRunner:
    def discover_tools(self, servers_dir="servers/"):
        """List available tools via filesystem (no injection in context)."""
        
    def run_tool(self, server, tool, input_data):
        """Execute tool in sandbox, return result (sandboxed, not in context)."""
        
    def agent_can_use(self, code):
        """Validate agent-written code is safe (RestrictedPython)."""
```

**Use case** : L'agent navigue le filesystem `servers/` pour trouver le bon tool, lit le code, l'appelle. Le résultat reste dans la sandbox sauf si explicitement loggé.

## 7. Le Compaction ACE-style (I4)

**Inspiré de** : ACE paper (arXiv 2510.04618, ICLR 2026)

**Différence vs summarization** :
- **Summarization** : paraphrase, perd les détails
- **Compaction ACE** : préserve structure + détails, déduplique, versionne

**API** :

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

**Mécanisme** :
1. Identifier les **événements discrets** (vs prose)
2. Dédupliquer sémantiquement
3. Regrouper par thème
4. Préserver les timestamps et hashes
5. Émettre un delta_report (ce qui a été préservé vs éliminé)

**Évite** :
- **Brevity bias** : perte de détails critiques
- **Context collapse** : dégradation itérative

## 8. Le Context Layout (I5)

**Pattern** : head/tail protection contre lost-in-the-middle.

**Schéma** :

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

**Implémentation** :

```python
from lib.context_layout import build_layout

context = build_layout(
    head=head_items,  # OrderedDict, key=position
    middle=middle_items,
    tail=tail_items,
    budget=8000,
)
```

**Test** : Lost-in-the-middle audit = placer des éléments critiques au milieu, vérifier qu'ils sont **rejetés** par le layout.

## 9. Le Pre-hydrate (I7)

**Inspiré de** : Cognition Labs (60% du 1er tour = retrieval), Anthropic long-running harness.

**API** :

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

**Mécanisme** :
- À l'entrée de phase, identifier ce que l'agent va chercher
- Pré-charger dans `state.db` (pas dans le contexte LLM, mais accessible en 1 call)
- Réduire le 1er tour de 60% retrieval à ~20% (gain 2.5×)

## 10. Les Adversarial Gates (I6)

**3 rôles + 4 modes** :

```python
from lib.adversarial_gate import Gate

# T1 — Casseur
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

# T3 — Aval (prédiction P+1)
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

**Verdict** : `PASS | WARN | FAIL`. FAIL = retry ou escalate. WARN = continuer avec log.

## 11. Le Playbook ACE (I8)

**Inspiré de** : ACE paper (ICLR 2026) — self-improving contexts.

**Mécanisme** :
- À chaque outcome (gate verdict, user decision), capturer l'insight
- Stocker dans `playbook` table avec score
- Dédup sémantique (embeddings, optional)
- Promote/demote basé sur outcomes

**API** :

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

**Cycle self-improving** : Phase 1 produit 50 bullets. Phase 10 en a retenu 12 (score > 0.7), 38 sont tombés (score < 0.3). Le playbook grossit en qualité, pas en taille.

## 12. Le HMAC Chain (audit)

**Pattern** : Cossack Labs 2025, RJV Audit Vault.

**Implémentation** :

```python
import hmac, hashlib, json

class HMACChain:
    def __init__(self, key_path=".audit_key"):
        with open(key_path, "rb") as f:
            self.key = f.read()
    
    def append(self, event_type, payload):
        prev_hash = self._get_last_hash()
        event = {
            "ts": now(),
            "type": event_type,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        event["hash"] = hmac.new(
            self.key,
            json.dumps(event, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()
        self._insert(event)
        return event["hash"]
    
    def verify(self):
        """Replay all events, verify chain integrity."""
        ...
```

**Usage** : Tous les events (phase_start, phase_end, tool_call, gate_decision, ledger_event) sont hashés et chaînés. Modification = chaîne cassée = détectée.

## 13. Le DSL (KEY:VALUE;;KEY:VALUE)

**Inspiré de** : swebok-v4-harness DSL, Anthropic subagent brief 4-champs.

**Format** :
```
KEY1:VALUE1;;KEY2:VALUE2;;KEY3:VALUE3
```

**Avantages** :
- Human-readable
- Machine-parseable (regex simple)
- Lisible en clair (pas de JSON braces)
- Compatible terminal (newline-safe)

**Use cases** :
- Brief subagent : `OBJECT:...;;FORMAT:...;;TOOLS:...;;BOUND:...`
- Gate verdict : `VERDICT:PASS;;RATIONALE:...;;FINDINGS:...`
- Phase transition : `PHASE:P4_DESIGN;;STATUS:ACTIVE;;BUDGET:8000`
- Token event : `COMPONENT:MESSAGES;;DIRECTION:INPUT;;TOKENS:1200;;MODEL:CLAUDE-OPUS-4-8`

**Parser** :

```python
def parse_dsl(line: str) -> dict:
    """Parse KEY:VALUE;;KEY:VALUE format."""
    pairs = line.split(";;")
    return {k.strip(): v.strip() for k, v in (p.split(":", 1) for p in pairs)}
```

## 14. Hooks (cycle de vie)

**7 hooks lifecycle** :

| Hook | Quand | Action |
|------|-------|--------|
| `PreToolUse` | Avant chaque tool call | Valider args, budget, scope |
| `PostToolUse` | Après tool call | Clear result, log, dedup |
| `SubagentStart` | Avant spawn subagent | Init isolated context, return contract |
| `SubagentEnd` | Après subagent complete | Summary extraction, firewall check |
| `PhaseStart` | Début de phase | Pre-hydrate, budget init, gate init |
| `PhaseEnd` | Fin de phase | Compaction, ledger snapshot, gate audit |
| `UserMessage` | À chaque msg user | UDL record, decision threshold classify |

**Implémentation** : chaque hook = un script Python dans `hooks/` avec une fonction `def main(event): ...`.

## 15. Distribution & installation

```bash
# Install
curl -fsSL https://raw.githubusercontent.com/doz34/context-engineering-harness/main/install.sh | bash
# ou
pip install ctxh  # PyPI

# Init dans un projet
cd my-project
ctxh init
# Crée : .ctxh/state.db, .ctxh/CLAUDE.md, .ctxh/hooks/

# Usage
ctxh measure --demo  # Token ledger demo
ctxh run --phase P3_ARCHITECTURE --brief brief.dsl
ctxh compact --target 2000
ctxh gate --role T1 --artifact spec.md
```

## 16. Tests & validation

- **Unit tests** : pytest, 100% coverage cible
- **Integration tests** : harness sur 5 use-cases réels
- **Adversarial tests** : 4 Drew Breunig modes × 3 T-rôles
- **Benchmark** : 3-5× économie mesurée vs baseline
- **Acceptance** : 5 projets pilote valident en production

## 17. Roadmap technique

| Sprint | Cible | Livrable | Critère PASS |
|--------|-------|----------|--------------|
| S1 | POV | `bin/ctxh`, `lib/state`, `lib/token_ledger`, `lib/dsl`, `lib/subagent_firewall` | Demo 1 use-case, 3× économie |
| S2 | MVP | + `lib/hooks`, `lib/ace_compact`, `lib/context_layout`, `lib/adversarial_gate` | 5 hooks, 4-mode audit |
| S3 | Beta | + `lib/code_api`, `lib/ace_playbook`, `lib/memory_blocks`, `lib/pre_hydrate` | Memory + self-improving |
| S4 | v1.0 | + tests adversariaux, docs, install.sh, PyPI | 100% tests, MIT, 3-5× mesuré |

---

*Architecture rédigée 2026-06-08 par discovery-orchestrator. 17 sections, 17 invariants. À réviser après S1.*
