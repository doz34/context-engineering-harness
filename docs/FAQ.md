# Frequently Asked Questions (FAQ)

> **Common questions about CE-Harness.** If your question isn't here, open a [GitHub Discussion](https://github.com/doz34/context-engineering-harness/discussions).

---

## General

### What is CE-Harness?

CE-Harness is an **opinionated open-source harness for LLM agents** that systematically optimizes the context window using the 4-pillars context engineering discipline (Write / Select / Compress / Isolate).

It's MIT-licensed, has zero external runtime dependencies, and reduces token cost **3-5×** (measured **10.8×** in our benchmarks).

### Why another harness?

Because in 2026, there is **no opinionated open-source harness** that:
- Treats context as a first-class budget (with live token ledger)
- Implements subagent firewall with strict return contract
- Combines code-as-API (Anthropic 2025) + AST sandbox
- Has zero external dependencies
- Is hardened with adversarial testing (94+ tests, 50+ payload corpus)

### Is CE-Harness production-ready?

**Yes**, for v1.0:
- 317/317 tests pass
- 10/10 swebok Council Bridge gates
- 0 CRIT, 0 MED, 0 LOW residual after 4 adversarial passes
- 14 security modules with documented threats mitigated
- Mitigations: see [SECURITY.md](../SECURITY.md)

Known limitations (documented in audit):
- Sandbox is AST-only (not OS-level; v1.1 will add Docker)
- Council Bridge is simulated (no real nexus-* agents; v1.1 will integrate)

### How is CE-Harness different from LangChain / LlamaIndex / etc.?

| | CE-Harness | LangChain | LlamaIndex |
|---|------------|-----------|------------|
| Focus | Context engineering | LLM orchestration | RAG |
| Runtime deps | 0 (stdlib only) | Many (langchain, langgraph, ...) | Many (llama-index, ...) |
| Adversarial tests | 94+ | Limited | Limited |
| Token ledger | Built-in | No | No |
| Subagent firewall | Built-in | Manual | No |
| Subagent return contract | Strict (5 fields, 7 anti-smugglings) | No | No |
| Production hardening | Zero-residual certified | Unknown | Unknown |

CE-Harness is **complementary** to LangChain/LlamaIndex: you can use them together.

---

## Installation

### What are the system requirements?

- **Python 3.10+** (we test on 3.10, 3.11, 3.12)
- ~10MB disk
- Zero external runtime dependencies

See [INSTALLATION.md](INSTALLATION.md) for details.

### Does it work on Windows?

Yes, via Python 3.10+ (native or WSL2).

### Does it work with any LLM?

The harness is **LLM-agnostic** — it manages context, not model calls. You can use it with Claude, GPT-5, Gemini, Qwen, local models, etc. The `model` field in `token_ledger.record()` is just metadata.

---

## Usage

### How do I use it with my existing agent?

CE-Harness provides Python modules. Integrate them in your agent code:

```python
from lib.state import StateDB
from lib.token_ledger import TokenLedger
from lib.subagent_firewall import SubagentFirewall, SubagentBrief

# In your agent loop
ledger = TokenLedger()
ledger.start_phase("P1", "My Phase", soft_cap=8000, hard_cap=15000)
ledger.record("P1", "messages", "input", 1200, model="gpt-5", agent="lead")

# Spawn subagent
firewall = SubagentFirewall(ledger, "P1")
result = firewall.spawn(...)
```

See [API.md](API.md) for the complete reference.

### Can I use only some modules?

Yes! Each module is **independent**. For example, you can use just:
- `lib.token_ledger` for token tracking
- `lib.subagent_firewall` for subagent isolation
- `lib.pii_tokenizer` for PII protection
- `lib.code_api` for code execution sandboxing

### Does it work with Claude Code / Cursor / Windsurf?

Not directly (yet). These tools have their own hooks systems. CE-Harness is a **standalone harness** that you integrate into your own agents.

In v1.1, we plan to provide a `claude-code-hooks/` adapter.

### Can I use it for non-LLM contexts?

Mostly yes. Most modules (token ledger, PII tokenizer, DSL parser, audit chain, sandbox) are **LLM-agnostic**. Only the hooks system assumes LLM-style tool calls.

---

## Architecture

### Why 5 layers?

Each layer has a **distinct responsibility**:
- **L0** = corpus (offline, never injected)
- **L1** = memory blocks (per-principal typed slots)
- **L2** = state (SQLite + HMAC chain)
- **L3** = working context (4-pillars)
- **L4** = LLM view (curated, head/tail)

The layers prevent cross-contamination and enforce the 4-pillars discipline.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the deep dive.

### Why 8 invariants?

Each invariant addresses a **specific failure mode**:
1. Token budget → 35-min wall
2. Code-as-API → 98.7% economy
3. Subagent firewall → 10.8× measured
4. ACE compaction → preserves details
5. Head/tail layout → lost-in-the-middle
6. Adversarial gates → Drew Breunig 4 modes
7. Pre-hydrate → 2.5× first-turn gain
8. ACE playbook → self-improving

Each invariant has a **module** that enforces it. Removing an invariant = accepting the corresponding failure mode.

### Why 7 hooks?

The 7 hooks correspond to the **natural lifecycle** of an agent:
- Pre/Post tool call (3 hooks in many systems, but we use 1+3=4 for richer semantics)
- Subagent spawn/return (2 hooks for isolation)
- Phase start/end (2 hooks for budget and audit)
- User message (1 hook for UDL)

Adding more hooks = more overhead. 7 is the **minimum for complete coverage**.

---

## Performance

### What token economy can I expect?

**3-5×** typical, **10.8×** measured on subagent search use case.

The economy depends on:
- **How many subagents you use** (more = more savings)
- **How verbose your current context is** (more = more savings)
- **What fraction is tool results** (PII tokenize, clear_result help)

### What's the latency overhead?

< 5ms per turn for typical workloads. Most operations are in-memory; only the audit chain has DB I/O.

### Can I scale to many users?

**Yes**. Per-tenant key encryption supports multi-tenant. SQLite is fine for one user; for many concurrent users, consider PostgreSQL (planned v1.1).

---

## Security

### Is it safe to use in production?

For **most use cases, yes** (POV validated with 4 adversarial passes).

For **high-stakes production** (healthcare, finance, defense), consider:
- OS-level sandboxing (Docker) — v1.1
- Real Council Bridge (v1.1)
- Hardware Security Module (HSM) for master keys
- Custom audit retention policy

See [SECURITY.md](../SECURITY.md) for the full policy.

### What if an attacker has filesystem access?

CE-Harness defends against **application-level** attacks, not **OS-level**. If an attacker has root, they can:
- Modify `state.db` directly
- Read the master key (if not in HSM)
- Bypass the sandbox (if not in Docker)

Defense: **OS-level isolation** (run the harness in a container, with restricted user).

### Are the audit logs tamper-evident?

**Yes**: the audit log uses `RotatingHMAC` with 24h epoch keys. Tampering with an event invalidates its HMAC, which is detected at verification time.

But: if an attacker has the master key, they can forge. Mitigations: HSM, key rotation, multi-party signing.

### What about GDPR?

CE-Harness has **GDPR Art. 17 (right to erasure)** built in:
- `lib.archive_anonymizer.py:ArchiveAnonymizer.erase_gdpr()` destroys the salt
- After erase, anonymized data is unrecoverable
- `lib.secrets_vault.py:SecretsVault.delete()` removes keys
- `lib/memory_blocks.py:MemoryStore.delete()` removes blocks (with per-tenant ACL)

---

## Testing

### Why 94+ adversarial tests?

Because **functional tests don't catch security bugs**. The 6 critical bugs found during S3-2 (e.g., `self.db_path` vs `self.path`, operator precedence) were all caught by adversarial tests, not functional ones.

See [ADVERSARIAL.md](ADVERSARIAL.md) for the full taxonomy.

### How do I add my own adversarial test?

```python
# tests/adversarial_my_attack.py
def test_my_attack_caught():
    """ATTACK: Description of the attack."""
    from lib.xxx import check_xxx
    attack = "<malicious input>"
    r = check_xxx(attack)
    assert not r.is_valid
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full process.

### Can I use the payload corpus in my own tests?

Yes! `lib.adversarial_corpus` is a public API:

```python
from lib.adversarial_corpus import get_by_target

payloads = get_by_target("subagent_validator")
for p in payloads:
    # ... test p.payload against your defense
```

---

## Development

### How do I contribute?

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full process.

### What's the development roadmap?

- **v1.0** (released 2026-06-09): 14 security modules, 317 tests, zero residual
- **v1.1** (planned Q3 2026): Real Council Bridge, Docker sandbox, PostgreSQL backend
- **v2.0** (planned Q4 2026): Distributed state (Raft), plugin system, web UI

### Can I fork and commercialize?

**Yes** under the MIT license. We'd appreciate if you contribute improvements back, but it's not required.

### Where do I get help?

- **GitHub Discussions**: https://github.com/doz34/context-engineering-harness/discussions
- **GitHub Issues**: https://github.com/doz34/context-engineering-harness/issues
- **Maintainer**: [@doz34](https://github.com/doz34)

---

## Comparisons

### CE-Harness vs swebok-v4-harness-distilled?

- **swebok** = parent project, SDLC enforcement (phases, gates, audit)
- **CE-Harness** = child project, context engineering (tokens, prompts, memory)

They are **complementary**: swebok orchestrates the process, CE-Harness optimizes the content.

[See LESSONS-LEARNED for swebok](../audit/08-LESSONS-LEARNED-FOR-SWEBOK-2026-06-09.md).

### CE-Harness vs Anthropic's "Effective Harnesses" blog?

Anthropic publishes **patterns** in their blog. CE-Harness is a **reference implementation** of those patterns + many more (ACE, MemGPT, Drew Breunig's 4 modes, etc.).

See [corpus/sources/INDEX.md](../corpus/sources/INDEX.md) for the 40+ research sources we synthesized.

### CE-Harness vs LangGraph?

- **LangGraph**: low-level orchestration framework (nodes, edges, state)
- **CE-Harness**: high-level context engineering discipline (4 pillars, 8 invariants)

You can use LangGraph for state machines and CE-Harness for token optimization. They are **complementary**.

### CE-Harness vs ACE (the paper)?

- **ACE** (Anthropic 2025, ICLR 2026): research paper on self-improving contexts
- **CE-Harness**: implements ACE's playbook pattern + 7 other innovations

`lib.ace_compact.py` and `lib.adversarial_corpus.py` reference the ACE paper directly.

---

## Troubleshooting

### Tests are slow (>10s)?

`python3 -m pytest tests/` should take < 5s on a standard laptop. If slower:
- Disable verbose: `pytest tests/ -q`
- Run only unit tests: `pytest tests/test_*.py`
- Run only adversarial: `pytest tests/adversarial_*.py`

### State DB is locked?

`state.db` uses SQLite WAL. Concurrent processes should work. If you get "database is locked":
- Check for zombie processes: `ps aux | grep ctxh`
- Use a different state dir: `ctxh init --path /tmp/ctxh`

### "Token budget exceeded" repeatedly?

Solutions:
- Increase the budget: `ctxh run --phase P3 --soft-cap 12000 --hard-cap 20000`
- Split into smaller phases
- Use a more powerful model (better caching, less retry)
- Optimize your prompts (less verbose)

### Other issues?

See [INSTALLATION.md §6 Troubleshooting](INSTALLATION.md#6-troubleshooting).

---

## See also

- [README.md](../README.md) — Overview
- [QUICKSTART.md](QUICKSTART.md) — 5-minute tutorial
- [INSTALLATION.md](INSTALLATION.md) — Installation
- [ARCHITECTURE.md](ARCHITECTURE.md) — Architecture
- [API.md](API.md) — Python API
- [HOOKS.md](HOOKS.md) — Hooks
- [ADVERSARIAL.md](ADVERSARIAL.md) — Adversarial testing
- [SECURITY.md](../SECURITY.md) — Security
- [CHANGELOG.md](../CHANGELOG.md) — Version history
- [CONTRIBUTING.md](../CONTRIBUTING.md) — Contributing
