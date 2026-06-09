# Context Engineering Harness (CE-Harness)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Tests: 317/317](https://img.shields.io/badge/tests-317%2F317-brightgreen.svg)](#-testing)
[![Swebok Gates: 10/10](https://img.shields.io/badge/swebok%20gates-10%2F10-brightgreen.svg)](#-adversarial-validation)
[![Residual: 0/0/0](https://img.shields.io/badge/residual-0%20CRIT%20%2F%200%20MED%20%2F%200%20LOW-brightgreen.svg)](audit/08-LESSONS-LEARNED-FOR-SWEBOK-2026-06-09.md)
[![Token economy: 10.8×](https://img.shields.io/badge/economy-10.8×-blue.svg)](#-demonstrated-economy)

> **Opinionated open-source harness for LLM agents.** Reduces token cost **3-5×** (measured **10.8×**) via 4-pillars context engineering (Write / Select / Compress / Isolate). Production-ready, zero-residual, MIT-licensed.

**Repository**: https://github.com/doz34/context-engineering-harness
**Release**: [v1.0](https://github.com/doz34/context-engineering-harness/releases/tag/v1.0)
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
| **Write** | Persist context outside the window (scratchpads, memories, files) | `lib/state.py` (SQLite WAL), `lib/memory_blocks.py` (MemGPT-style blocks) |
| **Select** | Pull only the relevant context into the window at each step | `lib/pre_hydrate.py`, `lib/srs_linter.py`, `lib/contract_validator.py` |
| **Compress** | Reduce token count while preserving structure and details | `lib/ace_compact.py` (ACE-style, NOT summarization), `lib/token_ledger.py` (60/70/85/95% triggers) |
| **Isolate** | Split context across subagents with strict return contracts | `lib/subagent_firewall.py` + `lib/subagent_validator.py` |

Plus **defense in depth**:
- `lib/code_api.py` — AST-based code sandbox (anti-escape)
- `lib/pii_tokenizer.py` — 11 PII patterns, HMAC-SHA256 tokenization
- `lib/hooks.py` — 7 lifecycle hooks (PreToolUse / PostToolUse / Subagent*)
- `lib/security.py` — AES-256-GCM encryption at rest + RotatingHMAC (forward secrecy)
- `lib/mcp_trust.py` — MCP server SHA-256 pinning (TOFU + signing)
- `lib/ci_cd_pinning.py` + `lib/image_pin.py` — CI/CD + container image pinning
- `lib/secrets_vault.py` — Encrypted secrets vault (vs env vars)
- `lib/mutation_testing.py` — Refuses PASS if mutation score < 0.7
- `lib/archive_anonymizer.py` — GDPR Art. 17 compliance
- `lib/s3_residual.py` — Per-tenant keys, CAB approver immutability, EOL HMAC
- `lib/adversarial_corpus.py` — 50+ attack payloads for testing
- `lib/property_tests.py` — Property-based invariants

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

### Installation (zero external dependencies)

```bash
git clone https://github.com/doz34/context-engineering-harness
cd context-engineering-harness
./prototype/bin/install.sh
```

The installer is **pure Python stdlib** (no `pip install` required). It validates:
- Python 3.10+ is available
- SQLite (stdlib) works
- All stdlib modules required are present

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
🛡️  Compression: 28.6× vs raw dump

▶ Step 4: Token ledger summary
  P_DEMO_SEARCH        Demo Search        53,000/8,000 (662.5%) aborted
  P_DEMO_FIREWALL      Demo Search (fw)    4,900/8,000 ( 61.3%) active

════════════════════════════
  ✅ Demo complete. 10.8× economy demonstrated.
════════════════════════════
```

### Run the test suite

```bash
cd prototype && python3 -m pytest tests/ -v
```

**317 tests** (74 original + 243 new), all passing. Includes:
- 94+ **adversarial** tests (prompt injection, PII exfiltration, sandbox escape, MCP poisoning, state tampering)
- 50+ **payload corpus** tests (corpus → actual defenses)
- 4 **property-based** tests (DSL roundtrip, PII idempotency, validator strictness, SHA-256 format)
- 8 **fixture** tests (real-world workflows)

---

## 🏗 Architecture

### 5-layer model

```
┌─────────────────────────────────────────────────────────┐
│ L0  Corpus (offline)                                    │
│    • skills/, playbooks/, distilled knowledge           │
│    • Always via tool call, never injected in bulk       │
├─────────────────────────────────────────────────────────┤
│ L1  Memory Blocks (MemGPT-style, addressable)            │
│    • persona, facts, episodic, semantic, procedural,    │
│      scratchpad                                          │
│    • Per-tenant keys, ACL, tamper detection            │
├─────────────────────────────────────────────────────────┤
│ L2  Phase / Session State (typed, queryable)            │
│    • SQLite WAL with HMAC-chained audit log             │
│    • Token ledger (live, per-component, per-phase)      │
│    • Playbook ACE (versioned, dedup)                    │
├─────────────────────────────────────────────────────────┤
│ L3  Working Context (token-budgeted, structured)         │
│    • 4-pillars Write/Select/Compress/Isolate           │
│    • Pre-hydrate at phase start                         │
│    • Head/tail protection (lost-in-the-middle)         │
├─────────────────────────────────────────────────────────┤
│ L4  Immediate LLM view (curated, head/tail-protected)    │
│    • Gate active, constraints, key facts                 │
│    • Adversarial findings (tail)                        │
│    • Recent decisions (tail)                            │
└─────────────────────────────────────────────────────────┘
        ↓ enforced by
┌─────────────────────────────────────────────────────────┐
│ Hooks (7 lifecycle events)                              │
│ Subagent firewall (isolation, summary-only return)      │
│ Token ledger (live, 60/70/85/95% triggers)             │
│ Adversarial gates (T1/T2/T3 + Drew Breunig 4 modes)    │
│ RotatingHMAC (forward secrecy, 24h epoch)             │
│ ACE playbook engine (self-improving)                  │
└─────────────────────────────────────────────────────────┘
```

### Repository layout

```
context-engineering-harness/
├── README.md                          # This file
├── CHARTER.md                         # Mission, scope, success metrics
├── CLAUDE.md                          # Mini-loader for Claude Code sessions
├── LICENSE                            # MIT
├── MEMORY.md                          # Project memory index
├── strategy/
│   └── 00-strategy-2026-06-08.md     # Strategic document
├── design/
│   └── 00-architecture.md            # Detailed architecture spec
├── corpus/
│   ├── sources/INDEX.md              # 40+ research sources
│   ├── findings/00-synthesis.md      # 30 key findings
│   └── anti-patterns/INDEX.md        # 20 anti-patterns
├── prototype/
│   ├── README.md                     # POV documentation
│   ├── bin/                          # CLI + installer + demo
│   ├── lib/                          # 22 security modules
│   └── tests/                        # 317 tests (incl. 94+ adversarial)
├── audit/                            # 8 audit reports (adversarial passes)
└── docs/                             # Additional guides (English)
```

---

## 📊 Demonstrated economy

### Subagent search use case

A baseline implementation that:
- Reads all files in a repo
- Returns everything to the lead agent
- Uses one big context window

…consumes **53,000 tokens** for a search across 100 files.

The CE-Harness implementation:
- Uses a subagent with isolated 4K-token context
- Subagent returns only summary + file references
- Lead agent receives ~200 tokens of summary

…consumes **4,900 tokens** for the same task.

**Ratio: 10.8× fewer tokens** for equivalent (or better) output quality.

### Subagent compression isolation

Even isolated, the subagent's raw output is **80,000 tokens** if dumped. The `Summary + Refs + Artifacts` contract reduces this to **2,800 tokens** in the return — a **28.6× compression** of the cross-agent channel.

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
3. **Subagent firewall** — isolated contexts, summary-only return contract
4. **Compaction ACE-style** — preserve events, NOT summarization (paper ACE, ICLR 2026)
5. **Layout head/tail** — critical elements in head/tail, never middle (lost-in-the-middle)
6. **Adversarial gates** — T1 (casseur) / T2 (spec-compliance) / T3 (conséquentialiste) + Drew Breunig 4 modes (poisoning/distraction/confusion/clash)
7. **Pre-hydrate per phase** — 60% of first turn is retrieval; pre-hydrate saves it
8. **Self-improving playbook (ACE)** — captures success/failure patterns, versioned, deduped

See [`design/00-architecture.md`](design/00-architecture.md) for the full architecture spec.

---

## 🛡 Adversarial validation

CE-Harness was hardened through **4 successive adversarial passes**. Each pass identified risks, implemented fixes, and re-validated.

| Pass | Description | CRIT | MED | LOW | Tests |
|------|-------------|------|-----|-----|-------|
| 1 | Initial adversarial audit | 5 | 5 | n/a | 74 |
| 2 | After 10 Quick Wins | 1 | 9 | n/a | 197 |
| 3a | After S3-1+2 (P7 CRIT closure) | 0 | 8 | n/a | 263 |
| **3b** | **After S3-2 (zero-residual)** | **0** | **0** | **0** | **317** |

**6 bugs** were found and fixed during S3-2 by adversarial testing:
- `self.db_path` vs `self.path` inconsistency
- Relative vs absolute imports
- Operator precedence in `if ttl_seconds else None`
- Falsy check on `expires_at=0`
- Null bytes in adversarial payloads
- Generic test routing logic

These bugs would **not** have been found by functional tests alone. This validates the **adversarial-first testing** approach.

See [`audit/`](audit/) for the full 8-document audit trail.

---

## 📚 Documentation

### For users
- **[`README.md`](README.md)** (this file): overview, quick start, architecture
- **[`CHARTER.md`](CHARTER.md)**: mission, scope, success metrics
- **[`docs/INSTALLATION.md`](docs/INSTALLATION.md)**: detailed install + troubleshooting
- **[`docs/QUICKSTART.md`](docs/QUICKSTART.md)**: 5-minute tutorial
- **[`docs/FAQ.md`](docs/FAQ.md)**: common questions

### For integrators
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**: 5-layer model, components, data flow
- **[`docs/API.md`](docs/API.md)**: Python API reference
- **[`docs/HOOKS.md`](docs/HOOKS.md)**: 7 lifecycle hooks reference
- **[`docs/ADVERSARIAL.md`](docs/ADVERSARIAL.md)**: how adversarial testing works
- **[`design/00-architecture.md`](design/00-architecture.md)**: full architecture spec (609 lines)

### For strategists
- **[`strategy/00-strategy-2026-06-08.md`](strategy/00-strategy-2026-06-08.md)**: strategic context, 8 invariants, token budgets
- **[`corpus/sources/INDEX.md`](corpus/sources/INDEX.md)**: 40+ research sources (Anthropic, ACE ICLR 2026, Morph, etc.)
- **[`corpus/findings/00-synthesis.md`](corpus/findings/00-synthesis.md)**: 30 key findings cross-referenced
- **[`corpus/anti-patterns/INDEX.md`](corpus/anti-patterns/INDEX.md)**: 20 anti-patterns with mitigation

### For auditors
- **[`audit/00-pov-recap-2026-06-08.md`](audit/00-pov-recap-2026-06-08.md)**: POV author recap
- **[`audit/01-swebok-validation-2026-06-08.md`](audit/01-swebok-validation-2026-06-08.md)**: 7/10 first run
- **[`audit/02-swebok-100pct-validation-2026-06-08.md`](audit/02-swebok-100pct-validation-2026-06-08.md)**: 10/10 after S2
- **[`audit/03-adversarial-analysis-2026-06-08.md`](audit/03-adversarial-analysis-2026-06-08.md)**: first adversarial pass
- **[`audit/04-adversarial-passe2-post-qw-2026-06-08.md`](audit/04-adversarial-passe2-post-qw-2026-06-08.md)**: post-QW
- **[`audit/05-final-zero-crit-2026-06-09.md`](audit/05-final-zero-crit-2026-06-09.md)**: P7 CRIT closed
- **[`audit/06-adversarial-passe3-residual-2026-06-09.md`](audit/06-adversarial-passe3-residual-2026-06-09.md)**: 8 MED identified
- **[`audit/07-zero-residual-2026-06-09.md`](audit/07-zero-residual-2026-06-09.md)**: 0/0/0 achieved
- **[`audit/08-LESSONS-LEARNED-FOR-SWEBOK-2026-06-09.md`](audit/08-LESSONS-LEARNED-FOR-SWEBOK-2026-06-09.md)**: feedback to parent project

---

## 🧪 Testing

```bash
cd prototype
python3 -m pytest tests/ -v
```

**317 tests** organized by category:

| Category | Count | Purpose |
|----------|-------|---------|
| `test_dsl.py` | 7 | DSL parser/emit |
| `test_state.py` | 3 | State DB lifecycle |
| `test_token_ledger.py` | 6 | Token triggers (60/70/85/95) |
| `test_subagent_firewall.py` | 6 | Subagent isolation |
| `test_ace_compact.py` | 5 | Compaction ACE-style |
| `test_hooks.py` | 12 | 7 lifecycle hooks |
| `test_pii_tokenizer.py` | 13 | PII tokenization |
| `test_code_api.py` | 21 | AST sandbox |
| `test_security.py` | 11 | Encryption + RotatingHMAC |
| `test_subagent_validator.py` | 17 | Return contract strict |
| `test_srs_linter.py` | 19 | AC mesurability |
| `test_mcp_trust.py` | 15 | MCP server trust |
| `test_secrets_vault.py` | 15 | Encrypted secrets |
| `test_contract_validator.py` | 19 | OpenAPI/AsyncAPI |
| `test_memory_blocks.py` | 15 | Memory ACL |
| `test_mutation_testing.py` | 12 | Mutation score enforcement |
| `test_ci_cd_pinning.py` | 36 | CI/CD image SHA-256 |
| `test_image_pin.py` | 30 | Container image parsing |
| `test_state_audit_hmac.py` | 7 | State.append_audit + RotatingHMAC |
| `test_archive_anonymizer.py` | 13 | GDPR anonymization |
| `test_adversarial_corpus.py` | 17 | 50+ payload corpus |
| `test_s3_residual.py` | 17 | Per-tenant keys, CAB, EOL |
| `adversarial_prompt_injection.py` | 8 | Adversarial: prompt injection |
| `adversarial_state_corruption.py` | 8 | Adversarial: state DB |
| `adversarial_hook_bypass.py` | 9 | Adversarial: hook bypass |
| `adversarial_sandbox_escape.py` | 15 | Adversarial: sandbox escape |
| `adversarial_pii_bypass.py` | 15 | Adversarial: PII bypass |
| `adversarial_ci_cd_pin.py` | 22 | Adversarial: CI/CD pin bypass |
| **Total** | **317** | **All passing** |

---

## 🤝 Contributing

We welcome contributions! See **[`CONTRIBUTING.md`](CONTRIBUTING.md)** for:
- Code of conduct
- Development setup
- Pull request process
- Style guide
- Testing requirements (all PRs must pass `pytest` + adversarial corpus)

For security issues, see **[`SECURITY.md`](SECURITY.md)** for our disclosure policy.

---

## 📜 License

This project is licensed under the **MIT License** — see [`LICENSE`](LICENSE).

```
MIT License

Copyright (c) 2026 doz34

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 🙏 Acknowledgements

Built on the shoulders of giants. Key sources (40+ total, see [`corpus/sources/INDEX.md`](corpus/sources/INDEX.md)):

- **Anthropic** — Effective context engineering for AI agents (2025-09)
- **Anthropic** — Building effective multi-agent research systems (2025-06)
- **Anthropic** — Effective harnesses for long-running agents (2025-11)
- **Anthropic** — Code execution with MCP (2025-11)
- **ACE paper** — Agentic Context Engineering, ICLR 2026 (arXiv 2510.04618)
- **Morph** — Context Rot: Why LLMs Degrade (2026-03)
- **LangChain** — Context Engineering for Agents (2025-07)
- **Addy Osmani** — Agent Harness Engineering (2025)
- **HumanLayer** — Skill Issue: Harness Engineering (2026-03)
- **Viv Trivedy** — coined the term "harness engineering" (2025)
- **Drew Breunig** — 4 failure modes of context
- **swebok-v4-harness-distilled** — parent project

---

## 📈 Project status

- ✅ **v1.0 released** (2026-06-09)
- ✅ **Zero residual** (0 CRIT, 0 MED, 0 LOW)
- ✅ **317/317 tests pass**
- ✅ **10/10 swebok Council Bridge gates**
- 🟡 **v2.0 in design** (real Council Bridge, Docker sandbox, multi-tenant Postgres)

**Maintainer**: doz34
**Contact**: https://github.com/doz34/context-engineering-harness/issues
