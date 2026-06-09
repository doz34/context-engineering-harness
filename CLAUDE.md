# CLAUDE.md — CE-Harness v1.0

> **Mini-loader for Claude Code sessions in this project.**
> Compressed: 759 bytes. Under 60 lines (HumanLayer 2026).

## Identity
- **Project**: CE-Harness v1.0 (POV)
- **Type**: Context engineering harness (LLM agent runtime)
- **Stack**: Python 3.10+, SQLite, stdlib
- **Phase**: POV → MVP (S1 of 4 sprints)

## 8 Invariants (enforced)
1. Token budget per phase, 60/70/85/95% triggers
2. Code-as-API (not tool calling)
3. Subagent firewall (isolated contexts)
4. Compaction ACE-style (preserve events)
5. Layout head/tail (lost-in-the-middle)
6. Adversarial gates (T1/T2/T3 + Drew 4-modes)
7. Pre-hydrate per phase (60% retrieval)
8. Self-improving playbook (ACE)

## Files
- `corpus/` — 40+ sources + findings + anti-patterns
- `strategy/00-strategy-2026-06-08.md` — strategic doc
- `design/00-architecture.md` — 5-couches architecture
- `prototype/` — POV code (Sprint S1)

## Hard rules
- **No** > 60 lines in CLAUDE.md (HumanLayer)
- **No** tool result retaining (auto-clear via PostToolUse)
- **No** peer-to-peer subagent channels
- **No** 50+ subagents for simple tasks
- **No** peer writes outside state DB

## Commands
- `cd prototype && bash bin/install.sh` — install
- `cd prototype && bash bin/ctxh-demo` — run demo
- `cd prototype && python3 -m pytest tests/ -v` — 27 tests
- `cd prototype && ./bin/ctxh --help` — CLI

## Status
- ✅ Corpus (40+ sources, 30 findings, 20 anti-patterns)
- ✅ Strategy 2026-06-08 (5-couches + 8 invariants)
- ✅ Architecture (17 sections)
- ✅ POV (5 components, 27 tests, 10.8× économie démo)
- ⏳ MVP (S2) — hooks, layout, gates, Drew modes
- ⏳ v1.0 (S4) — production-ready
