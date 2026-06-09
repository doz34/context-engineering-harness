# Installation Guide

> **Audience**: anyone who wants to use CE-Harness in their project.
> **Time**: 5 minutes for the standard install.

---

## 1. System requirements

### Required
- **Python 3.10+** (we test on 3.10, 3.11, 3.12)
- **SQLite** (stdlib, no install needed)
- **~10MB disk** for the harness + state DB

### Recommended
- **git** for cloning and updates
- **pytest** for running the test suite (auto-installed by tests)
- A terminal that supports ANSI colors (for the dashboard)

### Operating systems
- ✅ **Linux** (Ubuntu 22.04+, Debian 11+, Fedora 35+, Arch)
- ✅ **macOS** (12 Monterey+)
- ✅ **Windows** (10+ via WSL2 or native Python 3.10+)

### No required external dependencies
CE-Harness is designed to be **zero external runtime dependencies**:
- No `pip install` required
- No Docker required
- No API keys required (unless you integrate with a specific LLM)

The only "dependency" is **pytest** for the test suite, and that's installed via:
```bash
pip install pytest  # only for running tests
```

---

## 2. Standard installation (recommended)

### From GitHub (latest)

```bash
git clone https://github.com/doz34/context-engineering-harness.git
cd context-engineering-harness
./prototype/bin/install.sh
```

### From PyPI (when published)

```bash
pip install ctxh  # coming in v1.1
ctxh init
```

### From a release tarball

```bash
curl -L https://github.com/doz34/context-engineering-harness/releases/download/v1.0.0/v1.0.0.tar.gz | tar xz
cd context-engineering-harness-1.0.0
./prototype/bin/install.sh
```

---

## 3. Verify the installation

```bash
cd prototype
python3 -m pytest tests/ 2>&1 | tail -3
```

Expected output:
```
===================== 317 passed in 4.50s =====================
```

If you see fewer tests, check [§6 Troubleshooting](#6-troubleshooting).

---

## 4. Initialize in a project

To use CE-Harness in your own project:

```bash
cd /path/to/your-project
/path/to/context-engineering-harness/prototype/bin/ctxh init
```

This creates:
```
your-project/
└── .ctxh/
    ├── state.db       # SQLite state
    ├── CLAUDE.md      # Mini-loader for Claude Code
    ├── hooks/         # Hook scripts
    ├── subagents/     # Subagent artifacts
    └── memory/        # Memory blocks (if used)
```

---

## 5. Configuration

CE-Harness works out-of-the-box with sensible defaults. Optional configuration via environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `CTXH_HOME` | `.ctxh/` | Where to store state.db and other artifacts |
| `CTXH_LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CTXH_TOKEN_BUDGET_DEFAULT` | `8000` | Default phase soft cap (tokens) |
| `CTXH_TOKEN_HARD_CAP_DEFAULT` | `15000` | Default phase hard cap (tokens) |
| `CTXH_MASTER_KEY_PATH` | auto | Master key for encryption (auto-generated if missing) |
| `CTXH_LOG_FORMAT` | `text` | `text` or `json` |

Example:
```bash
export CTXH_LOG_LEVEL=DEBUG
export CTXH_TOKEN_BUDGET_DEFAULT=12000
./prototype/bin/ctxh measure
```

---

## 6. Troubleshooting

### "No module named 'lib'"

**Cause**: Python can't find the `lib/` directory.

**Fix**:
```bash
# Make sure you're in the prototype/ directory
cd /path/to/context-engineering-harness/prototype

# Or set PYTHONPATH
export PYTHONPATH=/path/to/context-engineering-harness/prototype:$PYTHONPATH
```

### "Permission denied: ./bin/install.sh"

**Cause**: Script not executable.

**Fix**:
```bash
chmod +x prototype/bin/*.sh
bash prototype/bin/install.sh  # or just call bash directly
```

### "sqlite3.OperationalError: database is locked"

**Cause**: Multiple processes accessing the same state.db.

**Fix**:
```bash
# Check for zombie processes
ps aux | grep ctxh

# Or use a different state directory
ctxh init --path /tmp/ctxh-test
```

### "Token budget exceeded" errors

**Cause**: Phase used more than hard cap.

**Fix**:
- Increase the budget: `ctxh run --phase P3 --soft-cap 12000 --hard-cap 20000`
- Or split into smaller phases
- Or use a more powerful model (better caching)

### "MCP server not in trust store"

**Cause**: Trying to use an MCP server that hasn't been pinned.

**Fix**:
```python
from lib.mcp_trust import tofu_pin

# Pin the MCP server to current hash (TOFU)
tofu_pin({"my-mcp": "/path/to/mcp.py"})
```

### "PII detected in tool result"

**Cause**: The hook detected PII in a tool result.

**This is correct behavior**, not a bug. The PII is automatically tokenized. To disable:
```python
# Disable PII tokenization (NOT RECOMMENDED for production)
from lib.hooks import post_tool_use_pii_tokenize
# Modify HOOK_REGISTRY to remove this hook
```

### Tests fail with "ImportError"

**Cause**: Python path issue.

**Fix**:
```bash
cd prototype
python3 -m pytest tests/ -v
# NOT: python3 tests/test_xxx.py (would fail with import errors)
```

---

## 7. Upgrading

### From 0.1.0 (POV) to 1.0.0

```bash
# Backup your state
cp -r .ctxh .ctxh.backup

# Pull the new version
git pull origin main

# Re-run tests
cd prototype && python3 -m pytest tests/

# Re-initialize (preserves state.db)
./bin/ctxh init
```

### From 1.0.x to 1.1.x

```bash
git pull origin v1.1
pip install --upgrade ctxh
```

No data migration needed (state.db schema is backwards compatible).

---

## 8. Uninstallation

```bash
# Remove the harness
rm -rf .ctxh/

# Or if you want to keep state, just disable hooks
mv .ctxh/hooks /tmp/ctxh-hooks-backup
```

To completely remove the project:
```bash
rm -rf context-engineering-harness
```

---

## 9. Getting help

If you encounter issues not covered here:

1. **Check existing issues**: https://github.com/doz34/context-engineering-harness/issues
2. **Search discussions**: https://github.com/doz34/context-engineering-harness/discussions
3. **Open a new issue** with:
   - OS and Python version
   - Full error trace
   - Steps to reproduce
   - Expected vs actual behavior

4. **For security issues**: see [SECURITY.md](../SECURITY.md)

---

## 10. See also

- [QUICKSTART.md](QUICKSTART.md) — 5-minute tutorial
- [ARCHITECTURE.md](ARCHITECTURE.md) — How the harness works internally
- [FAQ.md](FAQ.md) — Common questions
- [API.md](API.md) — Python API reference
