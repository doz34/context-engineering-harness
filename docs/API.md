# Python API Reference

> **Complete API reference for CE-Harness v1.0.** All public APIs are stable. For the underlying implementation, browse [prototype/lib/](../prototype/lib/).

---

## Quick reference

| Module | Purpose | Key classes |
|--------|---------|-------------|
| `lib.state` | SQLite state management | `StateDB` |
| `lib.token_ledger` | Live token tracking | `TokenLedger` |
| `lib.dsl` | KEY:VALUE parser | `parse`, `emit`, `validate_brief` |
| `lib.subagent_firewall` | Subagent isolation | `SubagentFirewall`, `SubagentBrief`, `SubagentResult` |
| `lib.ace_compact` | ACE-style compaction | `ACECompact`, `CompactionItem` |
| `lib.hooks` | 7 lifecycle hooks | `HookSystem`, `HookContext`, `HookResult` |
| `lib.pii_tokenizer` | 11 PII patterns | `PIITokenizer` |
| `lib.code_api` | AST code sandbox | `CodeAPISandbox`, `ImagePolicy` |
| `lib.security` | Encryption + RotatingHMAC | `EncryptedDB`, `RotatingHMAC` |
| `lib.subagent_validator` | Return contract strict | `validate`, `safe_subagent_result` |
| `lib.srs_linter` | AC mesurability | `lint_srs`, `find_acceptance_criteria` |
| `lib.mcp_trust` | MCP server pinning | `MCPServerEntry`, `validate_mcp_at_boot` |
| `lib.secrets_vault` | Encrypted secrets | `SecretsVault`, `EnvVarInterceptor` |
| `lib.contract_validator` | OpenAPI/AsyncAPI | `validate_openapi`, `validate_asyncapi` |
| `lib.memory_blocks` | MemGPT-style blocks | `MemoryStore`, `MemoryBlock` |
| `lib.mutation_testing` | Mutation score enforcement | `run_mutation_testing`, `enforce_mutation_testing` |
| `lib.ci_cd_pinning` | CI/CD SHA-256 pinning | `validate_github_action`, `validate_docker_image` |
| `lib.image_pin` | Container image parsing | `parse_image_ref`, `validate_image_ref` |
| `lib.archive_anonymizer` | GDPR Art. 17 | `ArchiveAnonymizer`, `anonymize_archive_snapshot` |
| `lib.adversarial_corpus` | 50+ attack payloads | `CORPUS`, `get_by_vector`, `get_by_target` |
| `lib.property_tests` | Property-based invariants | `run_all_property_tests` |
| `lib.s3_residual` | Per-tenant keys + CAB + EOL | `TenantKeyStore`, `CABRegistry`, `EOLRegistry` |

---

## lib.state

### `StateDB(path='.ctxh/state.db')`

SQLite WAL-based state manager with HMAC-chained audit log.

```python
from lib.state import StateDB

# Open or create
db = StateDB('.ctxh/state.db')

# Start a phase with budget
db.start_phase(
    phase_id="P3_ARCHITECTURE",
    session_id="s1",
    name="Architecture",
    soft_cap=8000,   # tokens
    hard_cap=15000,  # tokens
)

# Record token usage
db.record_token(
    phase_id="P3_ARCHITECTURE",
    component="messages",
    direction="input",
    tokens=1200,
    model="claude-opus-4-8",
    agent="lead",
)

# Query total
total = db.phase_total("P3_ARCHITECTURE")  # → 1200

# Get budget
soft, hard = db.phase_budget("P3_ARCHITECTURE")  # → (8000, 15000)

# Top components by token usage
top = db.top_components("P3_ARCHITECTURE", limit=5)
# → [("messages", 5400), ("tools", 1800), ...]

# End phase
db.end_phase("P3_ARCHITECTURE", status="complete")

# Audit chain (HMAC-signed)
hash = db.append_audit("event_type", {"foo": "bar"})
```

---

## lib.token_ledger

### `TokenLedger(state, verbose=True)`

Live token tracking with 60/70/85/95% triggers.

```python
from lib.token_ledger import TokenLedger

ledger = TokenLedger(verbose=True)

# Start phase with budget
ledger.start_phase("P3", "Architecture", soft_cap=8000, hard_cap=15000)

# Record usage
status = ledger.record(
    phase_id="P3",
    component="messages",
    direction="input",
    tokens=1200,
    model="claude-opus-4-8",
    agent="lead",
)
# Returns: {"action": None|INFO_60|CC_NOW|WARN_85|CRITICAL|ABORT, "level": ..., "tokens": ...}

# End phase
ledger.end_phase("P3", status="complete")

# Top components
top = ledger.top_components("P3", limit=5)

# Dashboard
print(ledger.dashboard("P3"))
```

---

## lib.dsl

### `parse(line)`, `emit(d)`, `validate_brief(d)`

KEY:VALUE;;KEY:VALUE parser and validator.

```python
from lib.dsl import parse, emit, validate_brief

# Parse
parsed = parse("OBJECT:Find X;;FORMAT:JSON;;TOOLS:grep,read;;BOUND:max 10")
# → {"OBJECT": "Find X", "FORMAT": "JSON", "TOOLS": "grep,read", "BOUND": "max 10"}

# Emit
dsl = emit({"OBJECT": "Find X", "FORMAT": "JSON"})
# → "OBJECT:Find X;;FORMAT:JSON"

# Validate brief (4-champs rule)
valid, errors = validate_brief({
    "OBJECT": "Find X",
    "FORMAT": "JSON",
    "TOOLS": "grep,read",
    "BOUND": "max 10",
})
# → (True, []) or (False, ["Missing required field: ..."])
```

---

## lib.subagent_firewall

### `SubagentFirewall(ledger, phase_id)`

Spawn isolated subagent contexts.

```python
from lib.subagent_firewall import SubagentFirewall, SubagentBrief
from lib.token_ledger import TokenLedger

ledger = TokenLedger()
ledger.start_phase("P3", "Architecture", 8000, 15000)
firewall = SubagentFirewall(ledger, "P3")

brief = SubagentBrief(
    OBJECT="Find all functions named 'parse_query'",
    FORMAT="JSON: {file: str, line: int, code: str}[]",
    TOOLS=["grep", "read"],
    BOUND="max 20 results, no file modifications",
)

result = firewall.spawn(
    brief=brief,
    context_budget=4000,
    model="claude-sonnet-4-5",
    execute_fn=my_executor,  # optional custom executor
)
# Returns SubagentResult with: summary, refs, artifacts, tokens_used, raw_size

# Compression ratio
ratio = result.compression_ratio()  # e.g., 28.6×

# Verify isolation
audit = firewall.verify_isolation("sub_1")
# → {"parent_context_visible": False, ...}
```

---

## lib.hooks

### `HookSystem()`, `HookContext`, `HookResult`, `HookDecision`, `HookEvent`

7 lifecycle hooks with chaining.

```python
from lib.hooks import (
    HookSystem, HookContext, HookEvent, HookDecision,
    pre_tool_use_block_destructive,
    post_tool_use_pii_tokenize,
    post_tool_use_clear_result,
    post_tool_use_summarize_swallowed,
)

hs = HookSystem()

ctx = HookContext(
    event=HookEvent.PRE_TOOL_USE,
    payload={},
    tool_name="Bash",
    tool_args={"command": "rm -rf /etc"},
)

# Fire all hooks for the event
result = hs.fire(ctx)
# result.decision == HookDecision.DENY
# result.reason = "Destructive command blocked: rm -rf at root"

# Audit
print(hs.audit_report())
# "Hook audit: 3 executions - ALLOW: 2, MODIFY: 0, CLEAR: 0, DENY: 1"
```

See [HOOKS.md](HOOKS.md) for the full reference.

---

## lib.pii_tokenizer

### `PIITokenizer(salt=None)`

Detect and tokenize 11 PII patterns with HMAC-SHA256.

```python
from lib.pii_tokenizer import PIITokenizer

t = PIITokenizer(salt="my_session_salt")

# Detect
findings = t.detect("Contact alice@acme.com, phone 01 23 45 67 89")
# → [("EMAIL", "alice@acme.com", 8, 23), ("PHONE_FR", "01 23 45 67 89", 31, 44)]

# Tokenize
tokenized, mappings = t.tokenize("Email alice@acme.com")
# tokenized = "Email [EMAIL_XXXXXXXXXXXX]"
# mappings = [PIIMapping(token="[EMAIL_...]", pii_type="EMAIL", original_hash="...")]

# Singleton
from lib.pii_tokenizer import get_tokenizer
t_global = get_tokenizer()
```

---

## lib.code_api

### `CodeAPISandbox()`, `ImagePolicy()`

AST-based code sandbox + container image policy.

```python
from lib.code_api import CodeAPISandbox, SandboxVerdict

s = CodeAPISandbox()

# Static check
r = s.static_check("import os\nos.system('rm -rf /')")
assert r.verdict == SandboxVerdict.DENY
assert "import" in r.denied_reasons[0].lower()

# Run safe code
r = s.run("result = 1 + 2")
assert r.verdict == SandboxVerdict.ALLOW
assert r.stdout == "3\n"  # if printed

# Image policy
from lib.code_api import ImagePolicy, validate_image_ref
p = ImagePolicy()
valid, issues = p.check("python:3.12")
assert not valid  # Mutable tag rejected
```

---

## lib.security

### `EncryptedDB()`, `RotatingHMAC()`, `generate_master_key()`

AES-256-GCM at rest + forward-secrecy HMAC.

```python
from lib.security import (
    EncryptedDB, RotatingHMAC, generate_master_key,
    load_or_create_master_key, current_epoch_id,
)

# Generate master key
key = generate_master_key()  # 32 bytes

# Load or create on disk
key = load_or_create_master_key("master.key")  # mode 0600

# Encrypted at rest
edb = EncryptedDB("state.db", passphrase="my_pp")
ct = edb.encrypt("secret data")
pt = edb.decrypt(ct)

# RotatingHMAC (forward secrecy)
rh = RotatingHMAC(key)
event = rh.sign("test payload", prev_hash="")
assert rh.verify(event)

# Epoch derivation
e_now = current_epoch_id()
key_now = rh._derive_epoch_key(e_now)
key_next = rh._derive_epoch_key(e_now + 1)
assert key_now != key_next
```

---

## lib.subagent_validator

### `validate(dsl)`, `safe_subagent_result(...)`

Strict return contract (5 fields, 7 anti-smuggling patterns).

```python
from lib.subagent_validator import validate, safe_subagent_result

# Validate
r = validate("SUMMARY:Found 3;;REFS:src/a.py:42")
assert r.is_valid

# Refuse unknown keys
r = validate("EVIL:payload", strict=True)
assert not r.is_valid

# Refuse external URLs
r = validate("SUMMARY:data at https://attacker.com")
assert not r.is_valid

# Safe builder
dsl = safe_subagent_result(
    summary="Found 3 call sites",
    refs=["src/a.py:42", "src/b.py:88"],
    artifacts=["out.json"],
    tokens=2400,
    raw_size=80000,
)
```

---

## lib.srs_linter

### `lint_srs(text)`, `find_acceptance_criteria(text)`

Validate that AC are measurable.

```python
from lib.srs_linter import lint_srs

# Sample SRS (well-formed)
srs = """
AC-1: System shall respond in < 200ms at p99.
AC-2: System shall support 10000 concurrent users with < 0.1% error rate.
"""

r = lint_srs(srs)
assert r["verdict"] == "PASS"  # 100% measurable

# Vague SRS (FAIL)
bad_srs = """
AC-1: System should be fast and user-friendly.
AC-2: System should probably work well for most users.
"""
r = lint_srs(bad_srs)
assert r["verdict"] == "FAIL"
assert r["measurable_count"] < r["total_acs"]
```

---

## lib.mcp_trust

### `MCPServerEntry()`, `validate_mcp_at_boot(servers, trust_store)`

MCP server pinning with HMAC signing.

```python
from lib.mcp_trust import (
    MCPServerEntry, validate_mcp_at_boot,
    load_trust_store, save_trust_store, sign_entry, verify_entry_signature,
    tofu_pin, generate_master_key,
)

# Build trust store
key = generate_master_key()
entry = MCPServerEntry(
    name="my-mcp",
    publisher="anthropic",
    expected_sha256="abc123...",  # SHA-256 of the MCP file
    version="1.0",
    signed_at="2026-06-09",
    signature="",
)
sign_entry(entry, key)
trust_store = {"my-mcp": entry}

# Validate
result = validate_mcp_at_boot(
    servers={"my-mcp": "/path/to/mcp.py"},
    trust_store=trust_store,
    signing_key=key,
)
assert result.valid
assert "my-mcp" in result.validated_servers

# TOFU bootstrap
store = tofu_pin({"my-mcp": "/path/to/mcp.py"}, publisher="acme")
```

---

## lib.secrets_vault

### `SecretsVault(vault_path, master_key=None)`

Encrypted secrets vault with per-principal ACL.

```python
from lib.secrets_vault import SecretsVault

v = SecretsVault(".ctxh/vault.db")

# Set
v.set("ANTHROPIC_API_KEY", "sk-xxx", owner="user:alice")
v.set("DB_PASSWORD", "secret123", owner="service:backend")

# Get (with ACL check)
value = v.get("ANTHROPIC_API_KEY", principal="user:alice")
# value == "sk-xxx"

# Grant access
v.grant("DB_PASSWORD", "service:frontend", {"read"})

# Rotate
v.rotate("DB_PASSWORD", "new_secret456")

# GDPR delete
v.delete("DB_PASSWORD", principal="user:alice")
```

---

## lib.contract_validator

### `validate_openapi(spec)`, `validate_asyncapi(spec)`

OpenAPI 3.x + AsyncAPI 2.x/3.x validation.

```python
from lib.contract_validator import validate_openapi, load_and_validate

# Validate dict
spec = {
    "openapi": "3.0.0",
    "info": {"title": "API", "version": "1.0"},
    "paths": {
        "/users": {
            "get": {"responses": {"200": {"description": "OK"}}}
        }
    }
}
r = validate_openapi(spec)
assert r.is_valid

# Load from file
r = load_and_validate("openapi.yaml", kind="openapi")
assert r.is_valid
```

---

## lib.memory_blocks

### `MemoryStore(db_path='.ctxh/memory.db')`

MemGPT-style memory blocks with ACL.

```python
from lib.memory_blocks import MemoryStore

store = MemoryStore()

# Create
block_id = store.create(
    type="facts",
    name="user_prefs",
    content="language=fr",
    owner="user:alice",
    acl={"user:bob": {"read"}},
)

# Read (with ACL)
content = store.read(block_id, "user:alice")
content = store.read(block_id, "user:bob")  # granted

# Update
store.update(block_id, "language=en", "user:alice")

# List (filtered by principal)
blocks = store.list_blocks("user:alice")

# Delete
store.delete(block_id, "user:alice")
```

---

## lib.mutation_testing

### `run_mutation_testing(source)`, `enforce_mutation_testing(...)`

Refuses PASS if mutation score < 0.7.

```python
from lib.mutation_testing import run_mutation_testing, enforce_mutation_testing

source = """
def add(a, b):
    return a + b

def is_positive(x):
    return x > 0
"""

r = run_mutation_testing(source)
print(f"Score: {r.score:.2f}, Verdict: {r.verdict}")

# Enforce
ok, msg = enforce_mutation_testing(coverage_pct=0.95, mutation_score=0.85)
# ok=True
```

---

## lib.ci_cd_pinning

### `validate_github_workflow(workflow)`, `validate_gitlab_ci(config)`, `detect_secrets_in_workflow(text)`

CI/CD SHA-256 pinning + secret detection.

```python
from lib.ci_cd_pinning import validate_github_workflow, validate_gitlab_ci, detect_secrets_in_workflow

# GitHub Actions
workflow = {
    "jobs": {
        "build": {
            "container": {"image": "node:20@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"},
            "steps": [
                {"uses": "actions/checkout@b4ffde4f2a3e3b6c8c5e2e3b6c8c5e2e3b6c8c5e"}
            ]
        }
    }
}
r = validate_github_workflow(workflow)
assert r.is_valid

# GitLab CI
config = {
    "image": "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
    "test": {"script": ["pytest"]}
}
r = validate_gitlab_ci(config)
assert r.is_valid

# Secret detection
issues = detect_secrets_in_workflow("""
env:
  AWS_KEY: AKIAIOSFODNN7EXAMPLE
""")
assert len(issues) > 0
```

---

## lib.image_pin

### `parse_image_ref(ref)`, `validate_image_ref(ref)`, `ImagePolicy()`

Container image SHA-256 parsing + policy.

```python
from lib.image_pin import parse_image_ref, validate_image_ref, ImagePolicy

# Parse
img = parse_image_ref("gcr.io/proj/img:1.0@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd")
print(img.registry, img.repo, img.tag, img.digest)
# → "gcr.io" "proj/img" "1.0" "sha256:abc..."

# Validate
valid, issues = validate_image_ref("python:3.12")
assert not valid  # Mutable tag

# Policy
p = ImagePolicy()
ok, _ = p.check("python:3.12@sha256:abc...")
assert ok
```

---

## lib.archive_anonymizer

### `ArchiveAnonymizer(salt=None)`, `anonymize_archive_snapshot(...)`

GDPR Art. 17 anonymization.

```python
from lib.archive_anonymizer import ArchiveAnonymizer, anonymize_archive_snapshot

# Anonymize text
a = ArchiveAnonymizer(salt="my_salt")
anon, count = a.anonymize_text("Email: alice@acme.com")
# anon = "Email: [ANON_EMAIL_XXXXXXXXXXXX]"

# Anonymize a dict
anon_dict, report = a.anonymize_dict({
    "user": "alice@acme.com",
    "phone": "01 23 45 67 89",
})
assert "alice@acme.com" not in str(anon_dict)
assert report.pii_replaced >= 2

# GDPR erasure
a.erase_gdpr()
# a.salt == "" — anonymized data is now unrecoverable

# End-to-end file
report = anonymize_archive_snapshot("snapshot.json", "anon.json", salt="x")
```

---

## lib.adversarial_corpus

### `CORPUS`, `get_by_vector(vector)`, `get_by_target(target)`

50+ attack payloads for continuous testing.

```python
from lib.adversarial_corpus import CORPUS, get_by_vector, get_by_target, stats

# Stats
s = stats()
print(f"Total: {s['total']}, by_vector: {s['by_vector']}")
# → Total: 50, by_vector: {'prompt_injection': 10, 'pii_exfil': 10, ...}

# Filter
pi_payloads = get_by_vector("prompt_injection")
for p in pi_payloads:
    print(f"{p.id}: {p.name} -> {p.target}")
    # → PI-001: ignore_instructions_basic -> subagent_validator
    # → PI-002: system_prompt_override -> subagent_validator
    # → ...

# Iterate all
for p in CORPUS:
    if p.severity == "CRIT":
        print(f"CRITICAL: {p.id} - {p.name}")
```

---

## lib.property_tests

### `run_all_property_tests(num_tests=10)`

Property-based invariants (no external dep).

```python
from lib.property_tests import run_all_property_tests

results = run_all_property_tests(num_tests=50)
for r in results:
    print(f"Property {r['name']}: {r['num_tests']} tests, {r['num_failures']} failures")
# → Property dsl_roundtrip: 50 tests, 0 failures
# → Property pii_idempotent: 50 tests, 0 failures
# → Property subagent_validator_strict: 50 tests, 0 failures
# → Property sha256_format: 50 tests, 0 failures
```

---

## lib.s3_residual

### `TenantKeyStore()`, `CABRegistry(master_key)`, `EOLRegistry(master_key)`

Per-tenant keys, CAB approver, EOL HMAC.

```python
from lib.s3_residual import TenantKeyStore, CABRegistry, EOLRegistry
from lib.security import generate_master_key

# Per-tenant keys
ks = TenantKeyStore(".ctxh/keys.json")
k_alice = ks.get_or_create("tenant:alice")
k_bob = ks.get_or_create("tenant:bob")
assert k_alice != k_bob

# CAB approver
key = generate_master_key()
cab = CABRegistry(key)
cab.add_approval("change_001", ["user:alice", "user:bob"], ttl_seconds=3600)
assert cab.verify("change_001")

# EOL decision
eol = EOLRegistry(key)
eol.record_eol("project:001", "user:alice", "GDPR Art. 17", retention_days=90)
assert eol.verify("project:001")
```

---

## CLI commands

See [README.md](../README.md) §Quick start for the CLI usage.

```bash
ctxh init                 # Initialize in current dir
ctxh measure --demo       # Run the demo
ctxh ledger               # View token ledger
ctxh spawn --brief '...'  # Spawn a subagent
```

---

## Error handling

All modules follow these conventions:

- **`ValueError`** for invalid input
- **`PermissionError`** for ACL violations
- **`FileNotFoundError`** for missing files
- Custom exceptions: `SandboxVerdict.DENY`, `HookDecision.DENY`, `ValidationResult.is_valid=False`

Always check the return value or catch the exception explicitly.

---

## See also

- [README.md](../README.md) — Overview
- [ARCHITECTURE.md](ARCHITECTURE.md) — Architecture deep dive
- [HOOKS.md](HOOKS.md) — Hooks reference
- [QUICKSTART.md](QUICKSTART.md) — 5-minute tutorial
- [INSTALLATION.md](INSTALLATION.md) — Installation guide
- [SECURITY.md](../SECURITY.md) — Security policy
