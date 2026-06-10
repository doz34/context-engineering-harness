# Changelog

All notable changes to **Context Engineering Harness (CE-Harness)** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [1.0.3] — 2026-06-10

### 🔒 Security & quality fixes from fresh-eyes audit

Fresh-eyes adversarial audit (`audit/fresh-eyes-v102/`) identified 26 findings across 12 quality dimensions (1 CRIT, 5 HIGH, 7 MED, 13 LOW). This release closes the 1 CRIT + 5 HIGH + 2 easy MED.

### Fixed

- **F-001 [CRIT]** — Dogfooding failure: the project's own CI used `actions/checkout@v4` and `actions/setup-python@v5` (mutable tags) while `lib/ci_cd_pinning.py` is designed to refuse exactly these. Both actions are now pinned to their v4.2.2 and v5.3.0 commit SHAs, and a new CI step runs `validate_workflow_file` on itself (fails CI if anyone re-introduces a mutable tag).
- **F-002 [HIGH]** — `lib/security_fallback.py` docstring claimed "AES-256-CTR + HMAC-SHA256" but the implementation is actually a custom SHA256-CTR (stdlib has no AES). Docstring corrected to reflect the real cipher and warn against use where AES compliance is required.
- **F-003 [HIGH]** — `StateDB.record_token` accepted negative integers, letting a sub-agent or bug call `record_token(-999999)` to silently decrement the phase budget and bypass soft/hard caps. Now raises `ValueError` on negative or non-int `tokens`.
- **F-004 [HIGH]** — Added `StateDB.verify_audit_chain()` method that walks the `audit_event` table and re-verifies each event's HMAC with the epoch-specific derived key, plus checks the `prev_hash` chain integrity. The `RotatingHMAC.verify` method existed but was never called on stored events. The state DB is now actually auditable end-to-end.
- **F-006 [HIGH]** — `post_tool_use_clear_result` sanitized `tool_name` but not `ctx.timestamp`. A caller-controlled timestamp like `../../etc/cron.daily/payload` would escape the `.ctxh/tool_results/` directory. Both fields are now sanitized and any name still containing `..` after regex stripping is replaced with a SHA-256 hash.
- **F-008 [MED]** — `post_tool_use_pii_tokenize` was creating a fresh `PIITokenizer()` per call, generating a new random salt each time. The same email would tokenize to a different token across calls, breaking deterministic tokenization. Now uses the module-level `get_tokenizer()` singleton.
- **F-011 [MED]** — `StateDB.append_audit` had `except (ImportError, AttributeError, Exception)` which silently swallowed ALL errors. Narrowed to `(ImportError, AttributeError)` and added a `logging.warning` so the legacy-SHA-256 fallback is now observable.

### Tests

- 318 → **324 tests** (+6 new: F-003 negative tokens, F-003 non-int tokens, F-004 clean chain verify, F-004 tamper detection, F-006 path-traversal block, F-008 deterministic tokenization). All pass in 7.86s.

### CI

- `actions/checkout` and `actions/setup-python` pinned to commit SHAs.
- Python 3.13 added to the test matrix.
- New "Self-audit" step runs `ci_cd_pinning.validate_workflow_file` on its own workflow (dogfooding enforcement).

### Changed

- `lib/security_fallback.py` — module docstring rewritten to clearly state the cipher is SHA256-CTR (not AES). No code change.
- `lib/state.py` — `record_token` now validates input; `append_audit` narrowed except + log; new `verify_audit_chain` method.
- `lib/hooks.py` — `post_tool_use_clear_result` hardens path sanitization; `post_tool_use_pii_tokenize` uses singleton tokenizer.
- `.github/workflows/tests.yml` — actions SHA-pinned, dogfooding audit step added, Python 3.13 added.

---

## [1.0.2] — 2026-06-10

### 🐛 14 latent bugs from fresh-eyes audit

Closed 14 user-facing bugs that the 4 prior adversarial passes had missed (install/demo/CLI crashes, regex bypasses, fallback paths).

See commit `6b052ea` for the full diff.

---

## [1.0.0] — 2026-06-09

### 🎉 First stable release

This is the first production-ready release of CE-Harness. It represents the culmination of 4 successive adversarial passes and the closure of all 18 quick wins (10 baseline + 8 S3-2 residual).

### Highlights

- **317/317 tests pass** (74 original + 243 new)
- **10/10 swebok Council Bridge gates PASS**
- **Zero residual**: 0 CRIT, 0 MED, 0 LOW after 4 adversarial passes
- **14 security modules** with 0 external runtime dependencies
- **94+ adversarial tests** covering 5 attack vectors
- **50+ attack payload corpus** for continuous testing
- **10.8× token economy** measured on real subagent search use case

### Added

#### Core harness
- `lib/state.py` — SQLite WAL state manager with HMAC chain
- `lib/token_ledger.py` — Live token tracking with 60/70/85/95% triggers
- `lib/dsl.py` — KEY:VALUE;;KEY:VALUE parser
- `lib/subagent_firewall.py` — Subagent isolation with summary-only return
- `lib/ace_compact.py` — ACE-style compaction (preserves events)
- `lib/hooks.py` — 7 lifecycle hooks (PreToolUse, PostToolUse, Subagent*)

#### Security modules (14)
- `lib/security.py` — AES-256-GCM encryption + RotatingHMAC (forward secrecy)
- `lib/pii_tokenizer.py` — 11 PII patterns with HMAC-SHA256 tokenization
- `lib/code_api.py` — AST-based code sandbox (3 layers)
- `lib/subagent_validator.py` — Strict return contract (5 fields, 7 anti-smuggling)
- `lib/srs_linter.py` — Acceptance Criteria mesurability (18 patterns)
- `lib/mcp_trust.py` — MCP server SHA-256 pinning with HMAC signing
- `lib/secrets_vault.py` — Encrypted secrets vault with per-principal ACL
- `lib/contract_validator.py` — OpenAPI 3.x + AsyncAPI 2.x/3.x validation
- `lib/memory_blocks.py` — MemGPT-style memory blocks with ACL
- `lib/mutation_testing.py` — Refuses PASS if mutation score < 0.7
- `lib/ci_cd_pinning.py` — CI/CD SHA-256 pinning (GitHub Actions + GitLab CI)
- `lib/image_pin.py` — Container image SHA-256 digest enforcement
- `lib/archive_anonymizer.py` — GDPR Art. 17 anonymization
- `lib/s3_residual.py` — Per-tenant keys, CAB approver, EOL HMAC

#### Adversarial testing
- `lib/adversarial_corpus.py` — 50+ attack payloads (PI/PII/SE/MCP/DB)
- `lib/property_tests.py` — Property-based invariants (4 properties)
- `tests/adversarial_prompt_injection.py` — 8 prompt injection tests
- `tests/adversarial_state_corruption.py` — 8 state DB tampering tests
- `tests/adversarial_hook_bypass.py` — 9 hook bypass tests
- `tests/adversarial_sandbox_escape.py` — 15 sandbox escape tests
- `tests/adversarial_pii_bypass.py` — 15 PII exfiltration tests
- `tests/adversarial_ci_cd_pin.py` — 22 CI/CD image pinning tests

#### CLI & Tooling
- `bin/ctxh` — Main CLI (init, measure, ledger, spawn)
- `bin/ctxh-demo` — End-to-end demo (10.8× economy)
- `bin/install.sh` — Zero-deps installer

#### Documentation
- `README.md` — Comprehensive English overview
- `CHARTER.md` — Mission, scope, success metrics
- `CLAUDE.md` — Mini-loader for Claude Code sessions
- `audit/` — 8 audit reports (adversarial passes)
- `corpus/` — 40+ sources, 30 findings, 20 anti-patterns
- `strategy/` — Strategic document
- `design/` — Architecture spec
- `docs/` — User guides (English)

### Security

- **CVE-PENDING-001**: Fixed 6 critical bugs found during S3-2 by adversarial testing:
  - `state.db` vs `db_path` naming inconsistency (info disclosure risk)
  - Relative vs absolute imports (path traversal risk)
  - Operator precedence in `if ttl_seconds else None` (TTL bypass)
  - Falsy check on `expires_at=0` (expiry bypass)
  - Null bytes in adversarial payloads (test environment DoS)
  - Generic test routing logic (false negative risk)

### Performance

- **Subagent search**: 10.8× fewer tokens (53,000 → 4,900) for equivalent task
- **Subagent return compression**: 28.6× ratio (80,000 → 2,800) for cross-agent channel
- **Zero new P99 latency** added by harness (sub-millisecond)

### Documentation

- All French markdown documents translated to English
- All 22 lib modules have module-level docstrings
- 8 audit reports fully translated and indexed
- Standard GitHub docs (CONTRIBUTING, SECURITY, CHANGELOG, CODE_OF_CONDUCT)
- Comprehensive English README with badges, table of contents, examples

### Validation

- **4 successive adversarial passes**:
  1. Initial: 5 CRIT, 12/12 score max
  2. After 10 QW: 1 CRIT, 7/12
  3. After S3-1+2: 0 CRIT, 4/12 (P7 CI/CD closed)
  4. After S3-2: **0 CRIT, 0 MED, 0 LOW**, ≤2/12

---

## [0.1.0] — 2026-06-08 — POV (Proof of Value)

### Initial POV

- Project scaffold created at `/home/doz/context-engineering-harness/`
- 5 core components: state, token_ledger, dsl, subagent_firewall, ace_compact
- 27/27 tests pass
- 10.8× token economy measured on subagent search use case
- 3 components demonstrated: token ledger, subagent firewall, ACE compaction
- 1 demo script (`bin/ctxh-demo`)
- 5 audit documents (00-pov-recap, 01-validation, 02-100pct, 03-adversarial, 04-passe2)

---

## Versioning

- **MAJOR** (X.0.0): breaking changes
- **MINOR** (1.X.0): new features, backwards compatible
- **PATCH** (1.0.X): bug fixes

---

## Migration guides

### From 0.1.0 to 1.0.0

No breaking changes. v1.0.0 is a superset of v0.1.0 with:
- 9 new security modules
- 6 adversarial test files
- 1 property-based test module
- 1 attack payload corpus
- 8 audit reports
- Comprehensive English documentation

To upgrade:
```bash
git pull origin main
cd prototype
python3 -m pytest tests/ -v  # Should show 317 passing
```

---

## Roadmap

### 1.1.0 (planned Q3 2026)
- Real Council Bridge with `nexus-*` external agents
- Docker sandbox (OS-level isolation in addition to AST)
- Multi-tenant PostgreSQL backend option
- Performance benchmarks (P50/P99 latencies on real workloads)

### 2.0.0 (planned Q4 2026)
- Distributed state (Raft consensus for audit chain)
- Plugin system for custom tokens/patterns
- Web UI for ledger dashboard
- Commercial support tier
