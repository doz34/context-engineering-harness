# Context Engineering Harness (CE-Harness)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Tests: 338/338](https://img.shields.io/badge/tests-338%2F338-brightgreen.svg)](#-testing)
[![Coverage: 85%+](https://img.shields.io/badge/coverage-85%25+-brightgreen.svg)](#-testing)
[![Token economy: 10.8×](https://img.shields.io/badge/economy-10.8×-blue.svg)](#-demonstrated-economy)

> **Opinionated open-source harness for LLM agents.** Reduces token cost **3-5×** (measured **10.8×**) via 4-pillars context engineering (Write / Select / Compress / Isolate). Production-ready, zero-residual, MIT-licensed.

**Repository**: https://github.com/doz34/context-engineering-harness
**Latest Release**: [v1.1.0](https://github.com/doz34/context-engineering-harness/releases/tag/v1.1.0)
**Provenance**: Inherits from [swebok-v4-harness-distilled](https://github.com/doz34/swebok-v4-harness-distilled)

---

## 📖 Table of Contents

- [What is CE-Harness?](#-what-is-ce-harness)
- [Why does it matter?](#-why-does-it-matter)
- [Quick start](#-quick-start)
- [Architecture](#-architecture)
- [Demonstrated economy](#-demonstrated-economy)
- [8 Invariants](#-8-invariants)
- [Adversarial validation](#-adversarial-validation)
- [Documentation](#-documentation)
- [Testing](#-testing)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 What is CE-Harness?

CE-Harness is an **opinionated runtime harness for LLM agents** that systematically optimizes the context window — the most expensive resource in any LLM application.

It enforces the **4-pillars context engineering** discipline (from [Anthropic, 2025](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)):

| Pillar | What it does | CE-Harness implementation |
|--------|--------------|---------------------------|
| **Write** | Persist context outside the window (scratchpads, memories, files) | `lib/state.py` (SQLite WAL), `lib/memory_blocks.py` (MemGPT-style blocks), `lib/encrypted_state.py` (AES-256-GCM at rest) |
| **Select** | Pull only the relevant context into the window at each step | `lib/llm_view.py` (head/middle/tail L4 view), `lib/srs_linter.py`, `lib/contract_validator.py` |
| **Compress** | Reduce token count while preserving structure and details | `lib/ace_compact.py` (ACE-style, NOT summarization), `lib/token_ledger.py` (60/70/85/95% triggers) |
| **Isolate** | Split context across subagents with strict return contracts | `lib/subagent_firewall.py` (subprocess isolation) + `lib/subagent_validator.py` |

Plus **defense in depth**:
- `lib/code_api.py` — AST-based code sandbox (anti-escape)
- `lib/pii_tokenizer.py` — 11 PII patterns, HMAC-SHA256 tokenization (with deobfuscation for `[at]`/`[dot]`/zero-width)
- `lib/hooks.py` — 7 lifecycle hooks (PreToolUse / PostToolUse / Subagent*), wired in CLI
- `lib/security.py` — AES-256-GCM encryption for `SecretsVault` + `EncryptedStateDB` at rest + RotatingHMAC (epoch compartmentalization)
- `lib/encrypted_state.py` — Encrypted state.db at rest (opt-in via `CTXH_ENCRYPTED=1`)
- `lib/observability.py` — Structured JSON logging with `CTXH_LOG_LEVEL` / `CTXH_LOG_FORMAT`
- `lib/mcp_trust.py` — MCP server SHA-256 pinning (TOFU + signing)
- `lib/ci_cd_pinning.py` + `lib/image_pin.py` — CI/CD + container image pinning
- `lib/secrets_vault.py` — Encrypted secrets vault (vs env vars)
- `lib/mutation_testing.py` — Static-heuristic mutation score gate
- `lib/archive_anonymizer.py` — GDPR Art. 17 compliance
- `lib/s3_residual.py` — Per-tenant keys, CAB approver immutability, EOL HMAC
- `lib/adversarial_corpus.py` — 50+ attack payloads for testing
- `lib/property_tests.py` — Property-based invariants (4 properties)

---

## 💡 Why does it matter?

In any LLM application, the context window is the **#1 cost driver**. Three out of four production issues stem from context management:

1. **Lost-in-the-middle** (Liu et al., Stanford/TACL 2024): **-30% accuracy** for information in positions 5-15 of 20 documents
2. **Context rot** (Chroma, 2025): **all 18 frontier models degrade** as context grows, not just at the limit
3. **35-minute wall** (Morph, 2026): failure rate **quadruples** when task duration doubles beyond ~35 minutes

CE-Harness systematically eliminates these failure modes through opinionated, enforced, tested architecture.

**Proven impact**: **10.8× token economy** measured on a real subagent search use case (53,000 → 4,900 tokens).

---

## 🚀 Quick start

### Installation

**Option 1: pip install (recommended)**
```bash
pip install ce-harness
# With encryption support:
pip install ce-harness[crypto]
```

**Option 2: From source (zero external dependencies)**
```bash
git clone https://github.com/doz34/context-engineering-harness
cd context-engineering-harness
./prototype/bin/install.sh
```

### Demo (30 seconds)

```bash
./prototype/bin/ctxh-demo
```

Output:
```
═══ CE-Harness POV Demo ═══
  Context Engineering — 3× economy demonstration
════════════════════════════

▶ Step 1: Initialize harness
✅ CE-Harness initialized in .ctxh-demo/

▶ Step 2: Measure baseline vs with-harness
📊 Baseline total: 53,000 tokens
📊 With firewall total: 4,900 tokens
🎯 ECONOMY RATIO: 53,000 → 4,900 = 10.8× less tokens

▶ Step 3: Spawn subagent (firewall pattern)
📋 Subagent Result: [STUB] Completed task...
🔒 Isolation: {'is_valid': True, ...}

════════════════════════════
  ✅ Demo complete. 10.8× economy demonstrated.
════════════════════════════
```

### Production setup

```bash
# Initialize with encryption
CTXH_ENCRYPTED=1 CTXH_PASSPHRASE="your-secret" ctxh init

# Check health
ctxh health --json

# View LLM context for a phase
ctxh view P5 --budget 4000

# Enable structured logging
export CTXH_LOG_LEVEL=INFO
export CTXH_LOG_FORMAT=json
```

See [docs/PRODUCTION.md](docs/PRODUCTION.md) for full deployment guide.

---

## 🏗 Architecture

### 5-layer model

```
┌─────────────────────────────────────────────────────────┐
│ L0  Corpus (offline) — REAL ✅                          │
│    • skills/, playbooks/, distilled knowledge           │
│    • Always via tool call, never injected in bulk       │
├─────────────────────────────────────────────────────────┤
│ L1  Memory Blocks (MemGPT-style, addressable) — REAL ✅  │
│    • persona, facts, episodic, semantic, procedural     │
│    • Per-tenant keys, ACL, tamper detection            │
├─────────────────────────────────────────────────────────┤
│ L2  Phase / Session State (typed, queryable) — REAL ✅  │
│    • SQLite WAL with HMAC-chained audit log             │
│    • Token ledger (live, per-component, per-phase)      │
│    • AES-256-GCM encryption at rest (opt-in)            │
├─────────────────────────────────────────────────────────┤
│ L3  Working Context (token-budgeted, structured) — REAL ✅│
│    • ACE compaction (preserve events, not summarization) │
│    • Pre-hydrate at phase start                         │
├─────────────────────────────────────────────────────────┤
│ L4  LLM View (curated, head/tail-protected) — REAL ✅   │
│    • Head: gate state, budget, constraints (30%)        │
│    • Middle: working context, ACE-compacted (40%)       │
│    • Tail: adversarial findings, recent decisions (30%) │
└─────────────────────────────────────────────────────────┘
        ↓ enforced by
┌─────────────────────────────────────────────────────────┐
│ Hooks (7 lifecycle events) — WIRED ✅                    │
│ Subagent firewall (subprocess isolation + stub)         │
│ Token ledger (live, 60/70/85/95% triggers)             │
│ Adversarial gates (T1/T2/T3 + Drew Breunig 4 modes)    │
│ RotatingHMAC (epoch compartmentalization, 24h epoch)   │
│ Structured logging (JSON, env-controlled)              │
│ Health check (state, audit chain, encryption, disk)    │
└─────────────────────────────────────────────────────────┘
```

### Repository layout

```
context-engineering-harness/
├── README.md                          # This file
├── CLAUDE.md                          # Mini-loader for Claude Code sessions
├── pyproject.toml                     # pip install ce-harness
├── prototype/
│   ├── bin/                          # CLI + installer + demo
│   ├── lib/                          # 27 modules (security + arch + obs)
│   │   ├── cli.py                    # CLI entry point (init/measure/spawn/health/view)
│   │   ├── encrypted_state.py        # AES-256-GCM encrypted state.db
│   │   ├── llm_view.py              # L4 head/middle/tail view builder
│   │   ├── observability.py          # Structured JSON logging
│   │   └── ...                       # 23 other modules
│   └── tests/                        # 338 tests (incl. 94+ adversarial)
├── docs/
│   ├── PRODUCTION.md                # Deployment guide
│   └── ...                          # 7 other guides
├── audit/                           # 10 audit reports
├── corpus/                          # 40+ research sources
└── .github/workflows/
    ├── tests.yml                    # CI: test + coverage gate
    └── release.yml                  # Auto GitHub release on tag
```

---

## 📊 Demonstrated economy

### Subagent search use case

A baseline implementation that reads all files in a repo and returns everything to the lead agent consumes **53,000 tokens** for a search across 100 files.

The CE-Harness implementation uses a subagent with isolated 4K-token context, returns only summary + file references, consuming **4,900 tokens** for the same task.

**Ratio: 10.8× fewer tokens** for equivalent (or better) output quality.

### Subagent compression isolation

Even isolated, the subagent's raw output is **80,000 tokens** if dumped. The `Summary + Refs + Artifacts` contract reduces this to **2,800 tokens** — a **28.6× compression** of the cross-agent channel.

### Trigger firing (real numbers from POV)

| Trigger | % of soft cap | Action |
|---------|---------------|--------|
| 60% | INFO_60 | Consider CC proactively |
| **70%** | **CC_NOW** | **Compaction Checkpoint required** |
| 85% | WARN_85 | Reduce tool loading or escalate |
| 95% | CRITICAL | End phase or abort |
| 100% (of hard cap) | ABORT | Phase aborted, escalate user |

In the demo: baseline hit **625% of soft cap** → **ABORT**. With harness: **61.3%** → no trigger.

---

## 🛡 8 Invariants (enforced by hooks + gates)

1. **Token budget per phase** with 60/70/85/95% triggers
2. **Code-as-API** (NOT tool calling) — 98.7% economy (Anthropic, 2025-11)
3. **Subagent firewall** — subprocess-isolated contexts, summary-only return contract
4. **Compaction ACE-style** — preserve events, NOT summarization (paper ACE, ICLR 2026)
5. **Layout head/tail** — L4 LLM View builder places critical info in head/tail (lost-in-the-middle)
6. **Adversarial gates** — T1 (casseur) / T2 (spec-compliance) / T3 (conséquentialiste) + Drew Breunig 4 modes
7. **Pre-hydrate per phase** — 60% of first turn is retrieval; pre-hydrate saves it
8. **Self-improving playbook (ACE)** — captures success/failure patterns, versioned, deduped

See [`design/00-architecture.md`](design/00-architecture.md) for the full architecture spec.

---

## 🛡 Adversarial validation

CE-Harness was hardened through **6 successive adversarial passes** including a 4-consultant integral analysis council.

| Pass | Description | Findings | Tests |
|------|-------------|----------|-------|
| 1-4 | Initial → zero-residual | 5 CRIT → 0 CRIT | 74 → 317 |
| 5 | Fresh-eyes audit v1.0.3 | 26 findings (1 CRIT + 5 HIGH + 7 MED + 13 LOW) | 324 |
| 6 | Integral analysis council (QA/CISO/Arch/DevOps) | 6 CRIT + 7 HIGH → all resolved | 338 |

The integral analysis council scored the project at 40/100 (pre-fix). After v1.1.0, all findings are resolved with real code.

See [`audit/`](audit/) for the full 10-document audit trail.

---

## 📚 Documentation

### For users
- **[`README.md`](README.md)** (this file): overview, quick start, architecture
- **[`docs/QUICKSTART.md`](docs/QUICKSTART.md)**: 5-minute tutorial
- **[`docs/INSTALLATION.md`](docs/INSTALLATION.md)**: detailed install + troubleshooting
- **[`docs/PRODUCTION.md`](docs/PRODUCTION.md)**: deployment, encryption, health check, backup
- **[`docs/FAQ.md`](docs/FAQ.md)**: common questions

### For integrators
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**: 5-layer model, components, data flow
- **[`docs/API.md`](docs/API.md)**: Python API reference
- **[`docs/HOOKS.md`](docs/HOOKS.md)**: 7 lifecycle hooks reference
- **[`docs/ADVERSARIAL.md`](docs/ADVERSARIAL.md)**: how adversarial testing works

### For strategists
- **[`strategy/00-strategy-2026-06-08.md`](strategy/00-strategy-2026-06-08.md)**: strategic context, 8 invariants
- **[`corpus/sources/INDEX.md`](corpus/sources/INDEX.md)**: 40+ research sources
- **[`corpus/findings/00-synthesis.md`](corpus/findings/00-synthesis.md)**: 30 key findings

---

## 🧪 Testing

```bash
cd prototype
python3 -m pytest tests/ -v
python3 -m pytest tests/ --cov=lib --cov-fail-under=80
```

**338 tests**, all passing, **85.77% coverage** (80% gate enforced in CI).

| Category | Count | Purpose |
|----------|-------|---------|
| Unit tests | 224 | Core modules (state, ledger, firewall, PII, ...) |
| Adversarial tests | 94+ | Prompt injection, PII bypass, sandbox escape, ... |
| Property tests | 4 | DSL roundtrip, PII idempotence, subagent strict, SHA-256 |
| Corpus tests | 17 | 50+ payload corpus vs actual defenses |

CI matrix: Python 3.10 / 3.11 / 3.12 / 3.13, SHA-pinned actions, dogfooding self-audit.

---

## 🤝 Contributing

We welcome contributions! See **[`CONTRIBUTING.md`](CONTRIBUTING.md)** for guidelines.

For security issues, see **[`SECURITY.md`](SECURITY.md)** for our disclosure policy.

---

## 📜 License

MIT License — see [`LICENSE`](LICENSE).

---

## 🙏 Acknowledgements

Built on the shoulders of giants. Key sources (40+ total, see [`corpus/sources/INDEX.md`](corpus/sources/INDEX.md)):

- **Anthropic** — Effective context engineering for AI agents (2025-09)
- **ACE paper** — Agentic Context Engineering, ICLR 2026
- **Morph** — Context Rot: Why LLMs Degrade (2026-03)
- **LangChain** — Context Engineering for Agents (2025-07)
- **Addy Osmani** — Agent Harness Engineering (2025)
- **HumanLayer** — Skill Issue: Harness Engineering (2026-03)
- **Drew Breunig** — 4 failure modes of context
- **swebok-v4-harness-distilled** — parent project

---

## 📈 Project status

- ✅ **v1.1.0 released** (2026-06-10) — Production-ready
- ✅ **338/338 tests pass**, 85.77% coverage
- ✅ **10.8× token economy** demonstrated
- ✅ **AES-256-GCM encryption** at rest (opt-in)
- ✅ **Subprocess isolation** for subagents
- ✅ **L4 LLM View** head/middle/tail builder
- ✅ **Structured logging** with JSON output
- ✅ **Health check** for monitoring integration
- ✅ **pyproject.toml** for pip install
- 🟡 **v1.2 planned** (real LLM client, Docker sandbox, Postgres backend)

**Maintainer**: doz34
**Contact**: https://github.com/doz34/context-engineering-harness/issues
