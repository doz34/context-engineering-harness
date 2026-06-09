# Security Policy

> **CE-Harness takes security seriously.** As a harness for LLM agents, it deals with sensitive contexts, secrets, and PII. This document describes how to report security vulnerabilities.

---

## 🚨 Reporting a vulnerability

**DO NOT** open a public GitHub issue for security vulnerabilities.

Instead, please use one of the following channels (in order of preference):

1. **GitHub Security Advisories**: https://github.com/doz34/context-engineering-harness/security/advisories/new
2. **Email**: doz34@users.noreply.github.com (PGP key below if you need confidentiality)
3. **Direct message** to [@doz34](https://github.com/doz34) on GitHub

Please include:
- **Description** of the vulnerability
- **Steps to reproduce** (minimal PoC if possible)
- **Impact assessment** (what an attacker could do)
- **Affected versions** (which versions are vulnerable)

---

## ⏱ Response timeline

We aim to:

| Stage | Target time |
|-------|-------------|
| **Initial response** (acknowledge receipt) | 48 hours |
| **Triage** (confirm + classify severity) | 7 days |
| **Patch** (for HIGH/CRIT) | 30 days |
| **Patch** (for MED/LOW) | 90 days |
| **Public disclosure** (after patch) | 7-14 days post-patch |

We may take longer for complex issues, but we'll keep you updated.

---

## 🔐 Supported versions

| Version | Supported |
|---------|-----------|
| 1.0.x (current) | ✅ Yes |
| < 1.0 | ❌ No |

We strongly recommend always running the latest patch release.

---

## 🏆 Hall of Fame

We thank the following security researchers for responsible disclosure (in chronological order):

*No reports yet — be the first!*

---

## 🛡 Security features in CE-Harness v1.0

CE-Harness is designed with **defense in depth**. Here are the built-in security features:

### Encryption
- **AES-256-GCM at rest** (`lib/security.py:EncryptedDB`) for state.db
- **RotatingHMAC** (`lib/security.py:RotatingHMAC`) for audit chain (forward secrecy per 24h epoch)
- **PBKDF2-HMAC-SHA256** key derivation (200,000 iterations)
- Per-tenant key encryption (`lib/s3_residual.py:TenantKeyStore`)

### Sandboxing
- **AST-based code sandbox** (`lib/code_api.py:CodeAPISandbox`) with 3 layers:
  - AST whitelist (allowed node types)
  - Name blacklist (25+ dangerous functions/attributes)
  - Builtin whitelist (54 safe builtins, dangerous stripped)

### PII Protection
- **11 PII patterns** (`lib/pii_tokenizer.py`) detected and tokenized
- HMAC-SHA256 tokenization (one-way, deterministic per session)
- Originals never reach the LLM context

### Adversarial Defenses
- **Subagent firewall** (`lib/subagent_firewall.py`) with strict return contract
- **Subagent validator** (`lib/subagent_validator.py`) with 7 anti-smuggling patterns
- **MCP trust store** (`lib/mcp_trust.py`) with HMAC signing and SHA-256 pinning
- **CI/CD pinning** (`lib/ci_cd_pinning.py`) — refuses mutable tags like `:latest`
- **Container image pinning** (`lib/image_pin.py`) — SHA-256 digest required
- **Secrets vault** (`lib/secrets_vault.py`) with per-principal ACL

### Audit & Compliance
- **RotatingHMAC audit chain** for tamper-evident logging
- **GDPR Art. 17 compliance** (`lib/archive_anonymizer.py`) — right to erasure
- **CAB approver immutability** (`lib/s3_residual.py:CABRegistry`)
- **EOL decision HMAC** (`lib/s3_residual.py:EOLRegistry`)

### Testing
- **94+ adversarial tests** covering prompt injection, sandbox escape, PII exfiltration, MCP poisoning, state tampering, hook bypass
- **50+ attack payload corpus** (`lib/adversarial_corpus.py`) — known attacks
- **4 property-based tests** for invariants

---

## 🔍 Security advisories

Past advisories are listed in [CHANGELOG.md](CHANGELOG.md) under "Security" sections.

No advisories published yet.

---

## 🛡 Best practices for users

When using CE-Harness in production:

1. **Always run the latest patch version**: `pip install --upgrade ctxh`
2. **Rotate master keys regularly**: see `lib/security.py:RotatingHMAC`
3. **Enable MCP trust store**: validate all MCP servers before use
4. **Pin container images to SHA-256 digests**: never use mutable tags (`:latest`)
5. **Store secrets in the vault, not env vars**: `lib/secrets_vault.py`
6. **Monitor audit chain**: set up alerts on broken HMAC chains
7. **Use per-tenant keys**: don't share encryption keys across tenants
8. **Archive old state with GDPR anonymization**: `lib/archive_anonymizer.py`
9. **Run adversarial tests in CI**: include `adversarial_*.py` in your test suite

---

## 🏗 Security architecture

```
┌─────────────────────────────────────────────────────┐
│            EXTERNAL INTERFACES                        │
│   CLI / Python API / YAML / Hooks SDK / MCP         │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────▼─────────────┐
        │     ENFORCEMENT LAYER     │
        │  ┌──────┐ ┌──────┐ ┌─────┐│
        │  │PreTool│ │PostTool│ │Hooks││  ← AST sandbox, PII tokenizer, clear
        │  └──────┘ └──────┘ └─────┘│
        └────────────┬─────────────┘
                     │
        ┌────────────▼─────────────┐
        │   5-LAYER CONTEXT MODEL    │
        │  L0 → L1 → L2 → L3 → L4  │  ← 4-pillars, head/tail, no flood
        └────────────┬─────────────┘
                     │
        ┌────────────▼─────────────┐
        │    STATE & STORAGE LAYER  │
        │  ┌──────┐ ┌──────┐ ┌─────┐│
        │  │SQLite│ │Vault │ │Memory││  ← Encrypted at rest, per-tenant keys
        │  └──────┘ └──────┘ └─────┘│
        └────────────┬─────────────┘
                     │
        ┌────────────▼─────────────┐
        │       AUDIT LAYER         │
        │  RotatingHMAC chain       │  ← Forward secrecy, tamper-evident
        │  CAB registry             │  ← Immutability
        │  EOL registry             │  ← HMAC-signed decisions
        └────────────────────────────┘
```

---

## 🔗 See also

- [README.md](README.md) — Overview
- [CONTRIBUTING.md](CONTRIBUTING.md) — How to contribute
- [CHANGELOG.md](CHANGELOG.md) — Version history
- [audit/](audit/) — 8 audit reports
- [docs/SECURITY-BEST-PRACTICES.md](docs/SECURITY-BEST-PRACTICES.md) — Detailed security guide
