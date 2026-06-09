# CLAUDE.md — CE-Harness v1.0

> **Mini-loader for Claude Code sessions in this project.**
> Compressed: under 60 lines (HumanLayer 2026 convention).

## Identity
- **Project**: CE-Harness v1.0
- **Type**: Context engineering harness (LLM agent runtime)
- **Stack**: Python 3.10+, SQLite, stdlib only
- **Phase**: Released v1.0 (2026-06-09)
- **Status**: Zero-residual, 10/10 swebok gates, 317/317 tests pass

## 8 Invariants (enforced)
1. Token budget per phase (60/70/85/95% triggers)
2. Code-as-API (not tool calling) — 98.7% economy
3. Subagent firewall (isolated contexts, summary-only return)
4. Compaction ACE-style (preserve events, not summarization)
5. Layout head/tail (lost-in-the-middle mitigation)
6. Adversarial gates (T1/T2/T3 + Drew Breunig 4 modes)
7. Pre-hydrate per phase (60% retrieval cost)
8. Self-improving playbook (ACE)

## Files
- `corpus/` — 40+ sources + 30 findings + 20 anti-patterns (research foundation)
- `strategy/00-strategy-2026-06-08.md` — Strategic document
- `design/00-architecture.md` — 5-layer architecture spec
- `prototype/` — Reference implementation (22 modules, 317 tests)
- `audit/` — 8 audit reports (adversarial passes + lessons learned)
- `docs/` — User guides (English)

## Hard rules
- **No** > 60 lines in CLAUDE.md (HumanLayer 2026)
- **No** tool result retaining (auto-clear via PostToolUse)
- **No** peer-to-peer subagent channels
- **No** 50+ subagents for simple tasks
- **No** peer writes outside state DB
- **No** mutable Docker tags in production (SHA-256 digest required)
- **No** hardcoded secrets (use vault)

## Commands
- `cd prototype && bash bin/install.sh` — install (zero external deps)
- `cd prototype && bash bin/ctxh-demo` — run demo (10.8× economy)
- `cd prototype && python3 -m pytest tests/ -v` — run 317 tests
- `cd prototype && ./bin/ctxh --help` — CLI help
- `cd /home/doz/swebok-v4-harness-distilled && bash swebok-bootstrap.sh` — re-run swebok council

## Status
- ✅ Corpus (40+ sources, 30 findings, 20 anti-patterns)
- ✅ Strategy 2026-06-08 (5 layers + 8 invariants)
- ✅ Architecture (17 sections, 609 lines)
- ✅ POV (22 modules, 317 tests, 10.8× economy, 0 residual)
- ✅ v1.0 tagged + released (https://github.com/doz34/context-engineering-harness/releases/tag/v1.0)

## License
MIT — see LICENSE
