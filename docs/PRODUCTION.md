# Production Deployment Guide

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CTXH_ENCRYPTED` | `0` | Enable state.db encryption at rest |
| `CTXH_PASSPHRASE` | (auto-generated) | Encryption passphrase. If not set, a key is auto-generated in `.ctxh/state.key` |
| `CTXH_ISOLATED` | `0` | Enable subprocess isolation for subagents |
| `CTXH_LOG_LEVEL` | `WARNING` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `CTXH_LOG_FORMAT` | `json` | Log format (`json` for structured, `text` for human-readable) |

## Encryption Setup

### Quick Start

```bash
# Enable encryption for a new project
CTXH_ENCRYPTED=1 CTXH_PASSPHRASE="your-strong-passphrase" ctxh init

# The encrypted state.db.enc will be created on first write
# The passphrase can also be stored in .ctxh/state.key (auto-generated)
```

### Key Management

- **Auto-generated key**: If no passphrase is provided, a 256-bit hex key is generated and stored in `.ctxh/state.key` (mode 0o600). This is the default and recommended for single-user deployments.
- **Explicit passphrase**: Set `CTXH_PASSPHRASE` env var. Key is derived via PBKDF2-HMAC-SHA256 (200,000 iterations).
- **Cipher**: AES-256-GCM (via `cryptography` library) or SHA256-CTR-HMAC fallback (stdlib-only).

### Key Rotation

1. Decrypt the current DB: remove `CTXH_ENCRYPTED`, copy state.db
2. Re-encrypt with new passphrase: `CTXH_ENCRYPTED=1 CTXH_PASSPHRASE=new-passphrase ctxh init`
3. Copy the old decrypted DB back, it will be re-encrypted on next close

## Health Check Integration

### Cron / systemd Timer

```bash
# Run health check every 5 minutes
*/5 * * * * cd /path/to/project && ctxh health --json >> /var/log/ctxh-health.log
```

### JSON Output

```json
{
  "status": "HEALTHY",
  "version": "1.1.0",
  "checks": {
    "state_db_schema": {"ok": true, "tables": 6},
    "state_db_integrity": {"ok": true},
    "audit_chain": {"ok": true, "checked": 42},
    "encryption": {"ok": true, "encrypted": true},
    "pii_salt": {"ok": true, "persisted": true},
    "disk_space_mb": {"ok": true, "free_mb": 45000.0},
    "logging": {"ok": true, "level": "INFO", "format": "json"}
  }
}
```

### Alerting

Parse the JSON output and alert on `status != "HEALTHY"` or any `checks.*.ok == false`.

## Backup Procedures

### Critical Files

| File | Purpose | Encrypted |
|------|---------|-----------|
| `.ctxh/state.db` | Active state database | No (temp file during use) |
| `.ctxh/state.db.enc` | Encrypted state at rest | Yes |
| `.ctxh/state.key` | Encryption key | No (protect!) |
| `.ctxh/pii.salt` | PII tokenization salt | No (protect!) |

### Backup Strategy

```bash
# 1. Ensure state is encrypted (no active plaintext temp)
ctxh health  # Should show "encrypted: true"

# 2. Copy encrypted files
tar czf backup-$(date +%Y%m%d).tar.gz \
  .ctxh/state.db.enc \
  .ctxh/state.key \
  .ctxh/pii.salt

# 3. Store backup securely (encrypted volume, offsite)
```

### Restore

```bash
tar xzf backup-20260610.tar.gz
ctxh health  # Verify integrity
```

## Upgrade Path

### From v1.0.x to v1.1.0

No breaking changes. New features are opt-in:

```bash
git pull origin main
cd prototype
python3 -m pytest tests/ -v  # Verify 338 tests pass

# Enable new features (optional):
export CTXH_ENCRYPTED=1    # Enable encryption
export CTXH_LOG_LEVEL=INFO # Enable structured logging
export CTXH_ISOLATED=1     # Enable subprocess isolation
```

### From v0.x to v1.1.0

```bash
git pull origin main
cd prototype
bash bin/install.sh
python3 -m pytest tests/ -v
```

## Structured Logging

### Integration with Log Aggregators

CE-Harness outputs structured JSON logs compatible with:
- **ELK Stack** (Elasticsearch + Logstash + Kibana)
- **Grafana Loki**
- **Datadog**
- **CloudWatch Logs**

Example log line:
```json
{"level":"INFO","module":"state","msg":"Phase P5 started","ts":"2026-06-10T20:30:00+00:00"}
```

### Log Levels

- `DEBUG`: Detailed state transitions, HMAC computations
- `INFO`: Phase start/end, subagent spawn, health checks
- `WARNING`: Budget threshold triggers, audit chain warnings
- `ERROR`: Encryption failures, DB corruption, isolation breaches
- `CRITICAL`: State tampering detected, key compromise

## Security Hardening Checklist

- [x] State.db encrypted at rest (AES-256-GCM)
- [x] PII salt persisted (deterministic tokens across restarts)
- [x] Audit chain verified on every CLI invocation
- [x] SIGTERM handler for clean shutdown
- [x] Hooks system operational (PreToolUse/PostToolUse)
- [x] Subprocess isolation available for subagents
- [x] Health check for monitoring integration
- [x] Structured logging with JSON output
- [x] Coverage gate enforced in CI (80%)
- [x] CI actions SHA-pinned (dogfooding)
- [ ] Docker sandbox (planned v1.2)
- [ ] Multi-tenant isolation (planned v1.2)
