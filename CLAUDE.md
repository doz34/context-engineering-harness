# CLAUDE.md — CE-Harness v1.1

> **Mini-loader for Claude Code sessions in this project.**
> Compressed: under 60 lines (HumanLayer 2026 convention).

## Identity
- **Project**: CE-Harness v1.1
- **Type**: Context engineering harness (LLM agent runtime)
- **Stack**: Python 3.10+, SQLite, stdlib only (cryptography optional)
- **Phase**: Production-ready v1.1 (2026-06-10)
- **Status**: 338/338 tests, 85.77% coverage, 0 residual findings

## New in v1.1
- EncryptedStateDB (AES-256-GCM at rest, `CTXH_ENCRYPTED=1`)
- L4 LLM View Builder (head/middle/tail layout, `ctxh view <phase>`)
- Subprocess isolation (`CTXH_ISOLATED=1` or `isolated=True`)
- Structured logging (`CTXH_LOG_LEVEL`, `CTXH_LOG_FORMAT`)
- Health check (`ctxh health [--json]`)
- pyproject.toml (`pip install ce-harness`)
- CI release workflow (auto GitHub release on tag)

## 8 Invariants (enforced)
1. Token budget per phase (60/70/85/95% triggers)
2. Code-as-API (not tool calling)
3. Subagent firewall (isolated contexts)
4. Compaction ACE-style (preserve events)
5. Layout head/tail (lost-in-the-middle)
6. Adversarial gates (T1/T2/T3 + Drew Breunig 4 modes)
7. Pre-hydrate per phase
8. Self-improving playbook (ACE)

## Files
- `corpus/` — 40+ sources + 30 findings + 20 anti-patterns
- `strategy/` + `design/` — Strategic and architecture documents
- `prototype/lib/` — 27 modules (state, encrypted_state, llm_view, observability, ...)
- `prototype/tests/` — 338 tests (unit + adversarial + property)
- `audit/` — 10 audit reports
- `docs/` — User guides + PRODUCTION.md

## Commands
- `cd prototype && python3 -m pytest tests/ -v` — run 338 tests
- `cd prototype && bash bin/ctxh-demo` — run demo (10.8× economy)
- `cd prototype && python3 bin/ctxh health --json` — health check
- `cd prototype && python3 bin/ctxh view P5` — LLM view for phase
- `pip install -e .[dev]` — dev install with pytest + cryptography

## Hard rules
- **No** > 60 lines in CLAUDE.md
- **No** mutable Docker tags in production
- **No** hardcoded secrets (use vault)
- **No** tool result retaining
- **No** 50+ subagents for simple tasks
- **Coverage gate**: 80% minimum enforced in CI
