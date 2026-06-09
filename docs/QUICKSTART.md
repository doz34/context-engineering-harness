# Quickstart — 5 minute tutorial

> **Get productive with CE-Harness in 5 minutes.**

---

## 1. Run the demo (30 seconds)

The fastest way to see CE-Harness in action:

```bash
cd context-engineering-harness
./prototype/bin/ctxh-demo
```

You'll see:
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
```

The demo shows a real subagent search use case: finding all call sites of a function across a codebase.

**Baseline** (1 agent, no harness): **53,000 tokens**
**With CE-Harness** (subagent firewall): **4,900 tokens**
**Economy**: **10.8×**

---

## 2. Initialize in your own project (1 minute)

To use CE-Harness in your project:

```bash
cd /path/to/your-project
/path/to/context-engineering-harness/prototype/bin/ctxh init
```

This creates `.ctxh/` with default config. Your project is now CE-Harness-enabled.

---

## 3. View the token ledger (30 seconds)

```bash
cd /path/to/your-project
/path/to/context-engineering-harness/prototype/bin/ctxh ledger
```

You'll see something like:
```
  P_DEMO_SEARCH        Demo Search        53,000/8,000 (662.5%) aborted
  P_DEMO_FIREWALL      Demo Search (fw)    4,900/8,000 ( 61.3%) active
```

This shows:
- Per-phase token usage
- Soft cap (8,000 tokens)
- Hard cap (15,000 tokens)
- Status (active, complete, aborted)

The demo phase was **aborted** because it used **662% of soft cap** (53K vs 8K). The harness prevented cost explosion.

---

## 4. Run a subagent with strict isolation (1 minute)

Spawn a subagent with the firewall pattern:

```bash
# The brief is a structured 4-field DSL
BRIEF='OBJECT:Find all functions named "parse_query";;FORMAT:JSON: {file: str, line: int, code: str}[];;TOOLS:grep,read;;BOUND:max 20 results, no file modifications'

/path/to/context-engineering-harness/prototype/bin/ctxh spawn --brief "$BRIEF"
```

The subagent:
- Gets ONLY the brief (no parent context)
- Has a 4K-token context budget
- Returns a summary + file references (not a dump)

---

## 5. Run the test suite (2 minutes)

```bash
cd /path/to/context-engineering-harness/prototype
python3 -m pytest tests/ -v
```

You should see **317 tests pass**:
```
===================== 317 passed in 4.50s =====================
```

The tests include:
- 223 unit + integration tests
- 94+ adversarial tests (prompt injection, PII, sandbox escape, etc.)

---

## 6. Next steps

Now that you've seen the basics:

1. **Read the [README](../README.md)** for the full architecture overview
2. **Check the [audit reports](../audit/)** for the security validation
3. **Read the [architecture doc](../design/00-architecture.md)** for the deep dive
4. **Browse the [corpus](../corpus/)** for 40+ research sources
5. **Read the [CONTRIBUTING](../CONTRIBUTING.md)** to start contributing

---

## What's next?

You now understand:
- ✅ How to run the demo (10.8× economy)
- ✅ How to initialize in your project
- ✅ How to view the token ledger
- ✅ How to spawn a subagent
- ✅ How to run the tests

What's still in your toolbox:
- 🔧 Custom hooks (`lib/hooks.py`)
- 🔧 Custom validators (`lib/subagent_validator.py`, `lib/srs_linter.py`, `lib/contract_validator.py`)
- 🔧 Adversarial tests (`tests/adversarial_*.py`)
- 🔧 Security policies (encryption, audit chain, secrets vault)

See [API.md](API.md) for the complete Python reference, or jump to a specific topic:
- [Architecture](ARCHITECTURE.md) — How the harness works internally
- [Adversarial testing](ADVERSARIAL.md) — How to attack the harness
- [FAQ](FAQ.md) — Common questions

Welcome aboard! 🚀
