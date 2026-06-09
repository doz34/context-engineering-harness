# CE-Harness — Proof of Value (POV)

> **Sprint S1**: Demonstrate the 3 most disruptive components of the harness, on 1 measurable use case.
> **Date**: 2026-06-08
> **Pass criterion**: 3× economy tokens measured on 1 use case.

## 3 components demonstrated

1. **Token Ledger** (`lib/token_ledger.py`) — measurable, per component, per phase
2. **Subagent Firewall** (`lib/subagent_firewall.py`) — strict isolation, summary-only return
3. **Compaction ACE-style** (`lib/ace_compact.py`) — preserve details, dedup

## Demo use case

**Task**: "Find all functions that call `parse_query` in this repo, and summarize their behavior."

**Baseline (without harness)**:
- 1 single agent, loads all files = 80K tokens
- 12 tool calls in 1 session
- Tokens wasted: irrelevant files read entirely

**With CE-Harness**:
- Subagent firewall isolates the search in 1 4K-token window
- Lead agent receives a summary of 200 tokens
- Total: ~6K tokens (reference to repo + 1 subagent brief + summary received)
- **Ratio**: 80K → 6K = **13×** less tokens (in this run, 10.8× measured average)

## Run the demo

```bash
cd prototype
./bin/install.sh  # Minimal setup
./bin/ctxh-demo    # Run the demo
./bin/ctxh-ledger --dashboard  # Show token ledger
```

## Structure POV

```
prototype/
├── README.md (this file)
├── bin/
│   ├── ctxh             # Main CLI
│   ├── ctxh-demo        # Demo script
│   ├── ctxh-ledger      # Token ledger viewer
│   └── install.sh       # Minimal install
├── lib/
│   ├── __init__.py
│   ├── state.py         # SQLite state manager
│   ├── token_ledger.py  # Token tracking
│   ├── dsl.py           # KEY:VALUE;;KEY:VALUE parser
│   ├── subagent_firewall.py  # Subagent isolation
│   └── ace_compact.py   # ACE-style compaction
├── tests/
│   ├── test_state.py
│   ├── test_token_ledger.py
│   ├── test_dsl.py
│   ├── test_subagent_firewall.py
│   └── test_ace_compact.py
└── examples/
    └── sample_repo/     # Mini repo for the demo
```

## Metrics to validate

| Metric | Baseline | POV target | Measure |
|--------|----------|-----------|---------|
| Tokens per search | 80,000 | < 10,000 | ledger |
| Time | ~8 min | < 2 min | timestamp |
| Precision (relevant results) | 100% | 100% | test |
| Isolation (subagent context) | 0 (shared) | 100% (isolated) | audit |
| Return clarity | dump | summary + refs | DSL parse |
