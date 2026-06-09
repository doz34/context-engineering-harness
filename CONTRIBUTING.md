# Contributing to CE-Harness

Thank you for your interest in contributing to **Context Engineering Harness (CE-Harness)**! 🎉

This document explains how to contribute to the project, the development workflow, and the standards we maintain.

---

## 📜 Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

In short: **be respectful, be constructive, be inclusive**.

---

## 🐛 Reporting bugs

We use [GitHub Issues](https://github.com/doz34/context-engineering-harness/issues) for bug reports.

**Before submitting**:
1. Search existing issues to avoid duplicates
2. Verify the bug on the latest `main` branch
3. Collect relevant information (OS, Python version, error trace)

**Bug report template**:
```markdown
## Description
[What happened?]

## Reproduction
[Minimal code to reproduce]

## Expected
[What should happen?]

## Actual
[What actually happens?]

## Environment
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.11.5]
- CE-Harness version: [e.g., 1.0.0]

## Stack trace
```
[Full error]
```
```

---

## 💡 Suggesting features

Open a [GitHub Discussion](https://github.com/doz34/context-engineering-harness/discussions) with:
- Clear use case
- Proposed API
- Alternative approaches considered
- Backwards compatibility impact

---

## 🔒 Security vulnerabilities

**DO NOT** open a public issue. See [`SECURITY.md`](SECURITY.md) for our disclosure policy.

We aim to respond within **48 hours** for critical vulnerabilities.

---

## 🛠 Development setup

### Prerequisites

- **Python 3.10+** (we test on 3.10, 3.11, 3.12)
- **Git**
- **pytest** (installed automatically by test files)
- **make** (optional, for convenience)

### Fork & clone

```bash
# Fork on GitHub first (button on https://github.com/doz34/context-engineering-harness)

# Clone your fork
git clone https://github.com/YOUR_USERNAME/context-engineering-harness
cd context-engineering-harness

# Add upstream remote
git remote add upstream https://github.com/doz34/context-engineering-harness.git

# Create a branch for your work
git checkout -b feature/my-amazing-feature
```

### Run tests

```bash
cd prototype
python3 -m pytest tests/ -v
```

**All PRs must pass the full test suite** (317 tests, including 94+ adversarial). The test suite is the source of truth for "does it work?".

### Lint & style

We follow **PEP 8** with these specifics:
- Max line length: **100 characters** (not 79)
- Use `black` for formatting (if available)
- Use `ruff` for linting (if available)
- Type hints are **encouraged** but not mandatory for POV

If you don't have black/ruff installed, no problem — the CI will check.

---

## 📝 Pull request process

### 1. Before opening a PR

- [ ] **Tests pass locally**: `python3 -m pytest tests/ -v` shows 317+ passing
- [ ] **No new adversarial gaps**: if you add a module, add adversarial tests
- [ ] **No secrets**: never commit API keys, passwords, master keys
- [ ] **No new LOW/MED/HIGH risks** without an audit entry in `audit/`

### 2. PR title format

```
<type>(<scope>): <description>

# Examples:
feat(hooks): add PreToolUse budget check
fix(sandbox): correctly reject `().__class__.__subclasses__()`
docs(readme): clarify installation steps
test(adversarial): add 10 new sandbox escape payloads
refactor(memory): simplify per-tenant key rotation
```

**Types**: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

### 3. PR description

```markdown
## What does this PR do?
[1-3 sentences]

## Why?
[Link to issue or rationale]

## How was it tested?
- [ ] Existing tests pass
- [ ] New tests added
- [ ] Adversarial test added (if security-relevant)

## Adversarial impact
- [ ] No new risk introduced
- [ ] New risk mitigated
- [ ] Documented in audit/

## Checklist
- [ ] Self-reviewed
- [ ] Comments added on hard-to-understand areas
- [ ] Documentation updated (if applicable)
- [ ] No new warnings
```

### 4. Review process

- **CI must pass** (tests + lint)
- **Maintainer review** (doz34) — typically 1-3 days
- **At least 1 approval** required
- **Adversarial review** if security-relevant (look for new attack vectors)

### 5. After merge

- Your contribution is in the next release
- You're added to the contributors list (in CHANGELOG.md)

---

## 🎯 Good first issues

Look for issues tagged [`good first issue`](https://github.com/doz34/context-engineering-harness/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

These are typically:
- Documentation improvements
- New adversarial test cases
- Simple bug fixes
- Adding type hints

---

## 🏗 Project structure

```
prototype/
├── bin/                  # CLI + installer + demo
│   ├── ctxh              # Main CLI
│   ├── ctxh-demo         # Demo script (10.8× economy)
│   ├── ctxh-ledger       # Token ledger viewer
│   └── install.sh        # Zero-deps installer
├── lib/                  # 22 security modules
│   ├── state.py          # SQLite WAL state
│   ├── token_ledger.py   # Live token tracking
│   ├── dsl.py            # KEY:VALUE parser
│   ├── subagent_firewall.py  # Subagent isolation
│   ├── ace_compact.py    # ACE-style compaction
│   ├── hooks.py          # 7 lifecycle hooks
│   ├── pii_tokenizer.py  # 11 PII patterns
│   ├── code_api.py       # AST sandbox
│   ├── security.py       # Encryption + RotatingHMAC
│   ├── subagent_validator.py  # Return contract strict
│   ├── srs_linter.py     # AC mesurability
│   ├── mcp_trust.py      # MCP SHA-256 pinning
│   ├── secrets_vault.py  # Encrypted secrets
│   ├── contract_validator.py  # OpenAPI/AsyncAPI
│   ├── memory_blocks.py  # MemGPT-style ACL
│   ├── mutation_testing.py  # Anti-test-gaming
│   ├── ci_cd_pinning.py  # CI/CD SHA-256
│   ├── image_pin.py      # Container image parsing
│   ├── archive_anonymizer.py  # GDPR Art. 17
│   ├── adversarial_corpus.py  # 50+ attack payloads
│   ├── property_tests.py  # Property-based invariants
│   └── s3_residual.py    # Per-tenant keys + CAB + EOL
├── tests/                # 317 tests (94+ adversarial)
│   ├── test_*.py         # Unit + integration tests
│   └── adversarial_*.py  # Adversarial test suites
└── examples/             # Example workflows
```

---

## 🎓 Code style guide

### Python

```python
# Good
def process_tokens(phase_id: str, ledger: TokenLedger) -> int:
    """Process token events for a phase.

    Args:
        phase_id: Unique phase identifier.
        ledger: Token ledger instance.

    Returns:
        Number of tokens processed.

    Raises:
        ValueError: If phase_id is empty.
    """
    if not phase_id:
        raise ValueError("phase_id cannot be empty")
    return ledger.process(phase_id)


# Bad
def process(x, l):
    return l.process(x)
```

### DSL (KEY:VALUE;;KEY:VALUE)

```python
# Use the DSL parser, never string manipulation
from lib.dsl import parse, emit

dsl = emit({"OBJECT": "find X", "FORMAT": "JSON", "TOOLS": "grep,read", "BOUND": "max 10"})
parsed = parse(dsl)
# parsed == {"OBJECT": "find X", "FORMAT": "JSON", "TOOLS": "grep,read", "BOUND": "max 10"}
```

### Comments

```python
# Good: explain WHY, not WHAT
# Use a 2-3KB SHA-256 to prevent accidental subagent ID collisions
subagent_id = hashlib.sha256(brief.encode()).hexdigest()[:8]

# Bad: restate the code
# Set subagent_id to the hash
subagent_id = hashlib.sha256(brief.encode()).hexdigest()[:8]
```

---

## 🧪 Testing guide

### Test categories

| Category | When to write | File pattern |
|----------|---------------|--------------|
| Unit | For every new function | `test_<module>.py` |
| Integration | For new public APIs | `test_<feature>.py` |
| Adversarial | For new security defenses | `adversarial_<vector>.py` |
| Property-based | For invariants | `test_property_*.py` |

### Test naming

```python
def test_<unit>_<scenario>_<expected>():
    # test_dsl_parse_with_missing_field_returns_empty
    # test_pii_tokenizer_handles_international_phone
    # test_sandbox_blocks_subprocess_run
```

### Adversarial tests

Each adversarial test should:
1. **Name an attack** (e.g., "ATTACK: PII in tool result")
2. **State expected behavior** (e.g., "PII should be tokenized before LLM sees it")
3. **Verify both directions** (positive: payload X is caught, negative: legit Y is not)

---

## 🔄 Release process

We follow **semantic versioning** (SemVer):
- **MAJOR** (X.0.0): breaking changes
- **MINOR** (1.X.0): new features, backwards compatible
- **PATCH** (1.0.X): bug fixes

Releases are tagged (`v1.0.0`) and have GitHub Release notes. See [CHANGELOG.md](CHANGELOG.md) for history.

---

## 📞 Getting help

- **GitHub Discussions**: https://github.com/doz34/context-engineering-harness/discussions
- **GitHub Issues**: https://github.com/doz34/context-engineering-harness/issues
- **Maintainer**: [@doz34](https://github.com/doz34)

---

## 🙏 Thank you

Every contribution matters — bug reports, documentation, code, ideas, or even just spreading the word. Thank you for being part of this project! 🚀
