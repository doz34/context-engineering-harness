# CE-Harness v1.0.2 — Fresh-Eyes Inventory (FACTUAL)

Audit target: `/home/doz/context-engineering-harness/`
Stated version: v1.0.2
Stated commit: `6b052ea` (`fix(quality): 14 latent bugs from fresh-eyes audit`)
Stated scope: 23 modules Python stdlib-only, 318 tests, 10/10 swebok gates PASS, 0 residual.

## Executive Summary

This is a factual inventory of the CE-Harness v1.0.2 codebase as present on disk. The `prototype/lib/` directory contains 24 Python source files (23 modules + `__init__.py`) totaling **5,200 lines**. The `prototype/tests/` directory contains 29 test files totaling **4,706 lines** and **396 `def test_` functions**. The dependency graph is sparse: only 7 source modules cross-import other source modules via relative imports (`__init__`, `token_ledger`, `state`, `hooks`, `security`, `subagent_firewall`, `secrets_vault`, `property_tests`). No `pyproject.toml`, `setup.py`, `setup.cfg`, `Makefile`, `tox.ini`, `pytest.ini`, `requirements*.txt`, or `conftest.py` exists in the tree. CI is configured via a single GitHub Actions workflow (`tests.yml`). Git state: on `main` branch, clean, head `6b052ea`, 2 tags (`v1.0.1`, `v1.0.2`).

---

## 1. Module Inventory (`prototype/lib/*.py`)

### 1.1 LOC, classes, function/method counts

| Module | LOC | Public top-level `def` | Private top-level `def _` | Classes | Module docstring |
|---|---:|---:|---:|---:|---|
| `__init__.py` | 14 | 0 | 0 | 0 | yes (re-exports) |
| `ace_compact.py` | 139 | 0 | 0 | 2 | yes |
| `adversarial_corpus.py` | 520 | 4 | 0 | 1 | yes |
| `archive_anonymizer.py` | 155 | 1 | 0 | 2 | yes |
| `ci_cd_pinning.py` | 366 | 9 | 0 | 2 | yes |
| `code_api.py` | 323 | 2 | 0 | 4 | yes |
| `contract_validator.py` | 230 | 4 | 0 | 2 | yes |
| `dsl.py` | 63 | 4 | 0 | 0 | yes |
| `hooks.py` | 305 | 7 | 0 | 5 | yes |
| `image_pin.py` | 220 | 5 | 0 | 2 | yes |
| `mcp_trust.py` | 217 | 8 | 0 | 2 | yes |
| `memory_blocks.py` | 207 | 0 | 0 | 2 | yes |
| `mutation_testing.py` | 218 | 7 | 0 | 2 | yes |
| `pii_tokenizer.py` | 223 | 1 | 0 | 2 | yes |
| `property_tests.py` | 174 | 12 | 0 | 1 | yes |
| `s3_residual.py` | 205 | 0 | 0 | 5 | yes |
| `secrets_vault.py` | 253 | 0 | 0 | 4 | yes |
| `security_fallback.py` | 75 | 2 | 1 | 0 | yes |
| `security.py` | 290 | 3 | 1 | 3 | yes |
| `srs_linter.py` | 213 | 3 | 0 | 1 | yes |
| `state.py` | 226 | 0 | 0 | 1 | yes |
| `subagent_firewall.py` | 221 | 0 | 0 | 3 | yes |
| `subagent_validator.py` | 183 | 4 | 0 | 1 | yes |
| `token_ledger.py` | 160 | 0 | 0 | 1 | yes |
| **Total** | **5,200** | **78** | **2** | **51** | **24/24** |

All 24 files start with a module-level docstring (every file shows `"""` within first 5 lines).

Method counts: 124 `def ` lines at indent-4 (methods) of which 50 are private (`def _`). Total `def` occurrences (all indent levels) = 208.

### 1.2 Classes defined (51)

```
adversarial_corpus.py: Payload
ace_compact.py: CompactionItem, ACECompact
archive_anonymizer.py: AnonymizationReport, ArchiveAnonymizer
ci_cd_pinning.py: PinningIssue, PinningResult
code_api.py: SandboxVerdict(str, Enum), SandboxResult, CodeAPISandbox, ServerTool
contract_validator.py: ContractIssue, ContractResult
hooks.py: HookEvent(str, Enum), HookContext, HookDecision(str, Enum), HookResult, HookSystem
image_pin.py: ImageRef, ImagePolicy
mcp_trust.py: MCPServerEntry, MCPBootValidation
memory_blocks.py: MemoryBlock, MemoryStore
mutation_testing.py: Mutant, MutationResult
pii_tokenizer.py: PIIMapping, PIITokenizer
property_tests.py: PropertyResult
s3_residual.py: TenantKeyStore, CABApproval, CABRegistry, EOLDecision, EOLRegistry
secrets_vault.py: SecretEntry, ACLEntry, SecretsVault, EnvVarInterceptor
security.py: EncryptedDB, Epoch, RotatingHMAC
srs_linter.py: ACIssue
state.py: StateDB
subagent_firewall.py: SubagentBrief, SubagentResult, SubagentFirewall
subagent_validator.py: ValidationResult
token_ledger.py: TokenLedger
```

### 1.3 Inter-module imports (dependency graph)

Top-level relative imports (`from .X` or `from lib.X`):

```
prototype/lib/__init__.py:2:    from .dsl import parse, parse_multi, emit, validate_brief
prototype/lib/__init__.py:3:    from .state import StateDB
prototype/lib/__init__.py:4:    from .token_ledger import TokenLedger
prototype/lib/__init__.py:5:    from .subagent_firewall import SubagentFirewall, SubagentBrief, SubagentResult
prototype/lib/__init__.py:6:    from .ace_compact import ACECompact, CompactionItem
prototype/lib/hooks.py:214:    from .pii_tokenizer import PIITokenizer           (lazy, inside function)
prototype/lib/property_tests.py:82:    from lib.dsl import parse, emit                 (lazy)
prototype/lib/property_tests.py:94:    from lib.pii_tokenizer import PIITokenizer     (lazy)
prototype/lib/property_tests.py:104:   from lib.subagent_validator import validate    (lazy)
prototype/lib/property_tests.py:112:   from lib.ace_compact import ACECompact, CompactionItem  (lazy)
prototype/lib/secrets_vault.py:15:    from .security import EncryptedDB, load_or_create_master_key
prototype/lib/security.py:41:    from .security_fallback import aes_ctr_hmac_encrypt, aes_ctr_hmac_decrypt   (lazy)
prototype/lib/state.py:174:   from lib.security import RotatingHMAC, load_or_create_master_key   (lazy)
prototype/lib/subagent_firewall.py:10:    from .dsl import validate_brief, parse
prototype/lib/subagent_firewall.py:11:    from .token_ledger import TokenLedger
prototype/lib/token_ledger.py:9:    from .state import StateDB
```

Edges (importer → imported):
- `__init__` → {`dsl`, `state`, `token_ledger`, `subagent_firewall`, `ace_compact`}
- `hooks` → `pii_tokenizer` (lazy)
- `property_tests` → {`dsl`, `pii_tokenizer`, `subagent_validator`, `ace_compact`} (all lazy)
- `secrets_vault` → `security`
- `security` → `security_fallback` (lazy)
- `state` → `security` (lazy)
- `subagent_firewall` → {`dsl`, `token_ledger`}
- `token_ledger` → `state`

All other 16 modules have no `from .X` / `from lib.X` relative imports; they are leaves.

### 1.4 Top-level non-relative imports (stdlib only, by file)

```
ace_compact.py: re, typing.List/Dict/Optional, dataclasses
adversarial_corpus.py: typing, dataclasses
archive_anonymizer.py: os, json, re, hashlib, typing, dataclasses, datetime
ci_cd_pinning.py: re, hashlib, os, json, typing, dataclasses
code_api.py: ast, re, sys, os, io, traceback, contextlib, typing, dataclasses, enum
contract_validator.py: re, json, typing, dataclasses, pathlib.Path
dsl.py: typing, re
hooks.py: json, re, enum, typing, dataclasses, datetime
image_pin.py: re, os, json, hashlib, subprocess, typing, dataclasses
mcp_trust.py: os, json, hashlib, secrets, typing, dataclasses, pathlib.Path
memory_blocks.py: json, time, hashlib, typing, dataclasses, pathlib.Path, sqlite3, os
mutation_testing.py: ast, re, random, typing, dataclasses
pii_tokenizer.py: re, hashlib, html, secrets, unicodedata, urllib.parse, typing, dataclasses
property_tests.py: random, string, typing, dataclasses
s3_residual.py: os, hmac, hashlib, json, time, secrets, typing, dataclasses, datetime
secrets_vault.py: os, json, hashlib, secrets, typing, dataclasses, pathlib.Path
security_fallback.py: hashlib, hmac, os, struct
security.py: os, hashlib, hmac, json, time, secrets, struct, typing, dataclasses, datetime, contextlib
srs_linter.py: re, typing, dataclasses
state.py: sqlite3, json, os, contextlib, typing
subagent_firewall.py: typing, dataclasses
subagent_validator.py: re, typing, dataclasses
token_ledger.py: typing
```

No third-party imports anywhere in `prototype/lib/`.

---

## 2. Dangerous Call Catalog (raw grep hits)

### 2.1 `subprocess`, `os.system`, `os.popen`, `os.exec*`

```
prototype/lib/image_pin.py:12:    import subprocess
prototype/lib/image_pin.py:146:        result = subprocess.run(
prototype/lib/image_pin.py:155:    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
prototype/lib/image_pin.py:160:        result = subprocess.run(
prototype/lib/image_pin.py:168:    except (FileNotFoundError, subprocess.TimeoutExpired):
```
No `os.system`, `os.popen`, `os.exec*`, `os.spawn*` anywhere in `prototype/lib/`.

### 2.2 `eval(`, `exec(`, `compile(`

Real calls:
```
prototype/lib/code_api.py:256:                exec(wrapped, namespace)
```
The other matches are string literals (denylist/whitelist in `code_api.py`, payload corpus in `adversarial_corpus.py`):
```
prototype/lib/code_api.py:61:    "exec", "eval", "compile", "__import__", "open", "input",
prototype/lib/code_api.py:62:    "os.system", "os.popen", "os.exec", "os.spawn",
prototype/lib/code_api.py:67:    "pickle.loads", "marshal.loads", "shelve.open",
prototype/lib/code_api.py:90:    # __import__ is whitelisted but checked at runtime
prototype/lib/code_api.py:91:    "__import__",
prototype/lib/code_api.py:213:        for dangerous in ["exec", "eval", "compile", "__import__", "open",
prototype/lib/adversarial_corpus.py:104:        payload="eval(compile('import os; os.system(\"id\")', '<x>', 'exec'))",
prototype/lib/adversarial_corpus.py:216:        payload="import os\nos.system('rm -rf /')",
prototype/lib/adversarial_corpus.py:225:        payload="import subprocess\nsubprocess.run(['cat', '/etc/passwd'])",
prototype/lib/adversarial_corpus.py:243:        payload="exec('print(1)')",
prototype/lib/adversarial_corpus.py:252:        payload="eval('2+2')",
prototype/lib/adversarial_corpus.py:270:        payload="compile('__import__(\"os\")', '<x>', 'exec')",
```

### 2.3 `pickle`, `marshal`, `shelve`

No direct imports/calls. All references are string literals in denylists / payload corpus:
```
prototype/lib/code_api.py:67:    "pickle.loads", "marshal.loads", "shelve.open",
prototype/lib/adversarial_corpus.py:286:        name="pickle_loads",
prototype/lib/adversarial_corpus.py:288:        payload="import pickle\npickle.loads(b'cos\\nsystem\\n(S\"id\"\\ntR.')",
```

### 2.4 `__import__`, `importlib`

```
prototype/lib/code_api.py:91:    "__import__",                       # string in whitelist list
prototype/lib/code_api.py:213:        for dangerous in ["exec", "eval", "compile", "__import__", "open",   # string in loop
prototype/lib/security.py:47:        import importlib                    # actual import
prototype/lib/security.py:48:        _fallback_mod = importlib.import_module("security_fallback")
```

### 2.5 `open(` with mode

```
prototype/lib/adversarial_corpus.py:261:        payload="open('/etc/passwd', 'w').write('pwned')",   # string
prototype/lib/hooks.py:141:        with open(full_path, "w") as f:
prototype/lib/archive_anonymizer.py:137:        with open(path, "w") as f:
prototype/lib/archive_anonymizer.py:147:    with open(snapshot_path) as f:                       # default r
prototype/lib/archive_anonymizer.py:151:    with open(output_path, "w") as f:
prototype/lib/mcp_trust.py:53:    with open(path, "rb") as f:
prototype/lib/mcp_trust.py:72:    with open(path) as f:                                  # default r
prototype/lib/mcp_trust.py:102:    with open(path, "w") as f:
prototype/lib/ci_cd_pinning.py:326:    with open(path) as f:                                 # default r
prototype/lib/s3_residual.py:36:    with open(self.store_path) as f:                        # default r
prototype/lib/s3_residual.py:45:    with open(self.store_path, "w") as f:
prototype/lib/secrets_vault.py:65:    with open(meta_path) as f:                             # default r
prototype/lib/secrets_vault.py:108:    with open(meta_path, "w") as f:
prototype/lib/security.py:85:    with open(self.salt_path, "rb") as f:
prototype/lib/security.py:89:    with open(self.salt_path, "wb") as f:
prototype/lib/security.py:281:    with open(path, "rb") as f:
prototype/lib/security.py:287:    with open(path, "wb") as f:
```
No mode `'a'`, no mode `'r+b'`, no `os.open`. All `open()` are read `'r'`/`'rb'` or write `'w'`/`'wb'`.

### 2.6 `socket`, `urllib`, `http`, `requests`

Direct: none.
String-literal refs:
```
prototype/lib/code_api.py:68:    "socket.socket", "urllib.request.urlopen",
prototype/lib/code_api.py:69:    "requests.get", "requests.post", "httpx.get", "httpx.post",
prototype/lib/pii_tokenizer.py:16:import urllib.parse
prototype/lib/pii_tokenizer.py:126:        s = urllib.parse.unquote(s)
prototype/lib/adversarial_corpus.py:279:        payload="import urllib.request\nurllib.request.urlopen('http://attacker.com')",
```
Only `urllib.parse` is imported (for URL decoding). No network I/O in lib code.

### 2.7 `hashlib`, `hmac`, `secrets`, `cryptography`

```
prototype/lib/security.py:34:    from cryptography.hazmat.primitives.ciphers.aead import AESGCM   # conditional
prototype/lib/security.py:60:    return hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, 200_000)[:length]
prototype/lib/security.py:88:    self.salt = secrets.token_bytes(16)
prototype/lib/security.py:111:    nonce = secrets.token_bytes(12)
prototype/lib/security.py:186:    return hashlib.pbkdf2_hmac(...
prototype/lib/security.py:224:    h = _hmac.new(epoch.derived_key, content, hashlib.sha256).hexdigest()
prototype/lib/security.py:267:    expected = _hmac.new(epoch.derived_key, content, hashlib.sha256).hexdigest()
prototype/lib/security_fallback.py:24:    enc_key = hashlib.sha256(b"enc" + key).digest()
prototype/lib/security_fallback.py:25:    mac_key = hashlib.sha256(b"mac" + key).digest()
prototype/lib/security_fallback.py:32:    mac = _hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
prototype/lib/security_fallback.py:44:    enc_key = hashlib.sha256(b"enc" + key).digest()
prototype/lib/security_fallback.py:45:    mac_key = hashlib.sha256(b"mac" + key).digest()
prototype/lib/security_fallback.py:48:    expected_mac = _hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
prototype/lib/security_fallback.py:49:    if not _hmac.compare_digest(expected_mac, mac):
prototype/lib/security_fallback.py:68:    keystream = hashlib.sha256(block_input).digest()
prototype/lib/ace_compact.py:100:        return hashlib.md5(normalized.encode()).hexdigest()[:12]
prototype/lib/mcp_trust.py:52:    h = hashlib.sha256()
prototype/lib/mcp_trust.py:61:    return hashlib.sha256(data).hexdigest()
prototype/lib/mcp_trust.py:111:    entry.signature = hmac.new(signing_key, content, hashlib.sha256).hexdigest()
prototype/lib/mcp_trust.py:119:    expected = hmac.new(signing_key, content, hashlib.sha256).hexdigest()
prototype/lib/mcp_trust.py:120:    return hmac.compare_digest(expected, entry.signature)
prototype/lib/memory_blocks.py:207:    return hashlib.sha256(content.encode()).hexdigest()[:16]
prototype/lib/secrets_vault.py:57:    return hashlib.sha256(b"vault-passphrase:" + self._key).hexdigest()
prototype/lib/pii_tokenizer.py:56:    self.salt = salt or secrets.token_hex(8)
prototype/lib/pii_tokenizer.py:61:    h = hashlib.sha256(f"{self.salt}:{value}".encode()).hexdigest()[:8]
prototype/lib/pii_tokenizer.py:66:    return hashlib.sha256(value.encode()).hexdigest()[:16]
prototype/lib/hooks.py:128:    safe_name = "tool_" + hashlib.sha256(...)
prototype/lib/property_tests.py:122:    h = hashlib.sha256(s.encode()).hexdigest()
prototype/lib/property_tests.py:130:    h1 = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
prototype/lib/property_tests.py:131:    h2 = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
prototype/lib/s3_residual.py:52:    self._keys[tenant_id] = secrets.token_bytes(32)
prototype/lib/s3_residual.py:58:    new_key = secrets.token_bytes(32)
prototype/lib/s3_residual.py:101:    return hmac.new(self.master_key, content, hashlib.sha256).hexdigest()
prototype/lib/s3_residual.py:129:    if not hmac.compare_digest(a.signature, expected_sig):
prototype/lib/s3_residual.py:175:    return hmac.new(self.master_key, content, hashlib.sha256).hexdigest()
prototype/lib/s3_residual.py:199:    return hmac.compare_digest(d.signature, expected)
prototype/lib/archive_anonymizer.py:57:    return secrets.token_hex(16)
prototype/lib/archive_anonymizer.py:61:    return hashlib.sha256(f"{self.salt}:{value}".encode()).hexdigest()[:12]
```

`hashlib.md5()` appears once in `ace_compact.py:100` (truncated 12-char cache key).
`hmac.compare_digest` is used for constant-time comparisons in `mcp_trust`, `s3_residual`, `security_fallback`.

### 2.8 `sqlite3`

```
prototype/lib/memory_blocks.py:14:import sqlite3
prototype/lib/memory_blocks.py:54:        c = sqlite3.connect(self.db_path)
prototype/lib/state.py:7:import sqlite3
prototype/lib/state.py:23:    def conn(self) -> Iterator[sqlite3.Connection]:
prototype/lib/state.py:25:        c = sqlite3.connect(self.path, isolation_level=None)
```

Two modules own DB connections. No `psycopg`, `pymysql`, `sqlalchemy`.

---

## 3. Regex Catalog

Format: `fichier:ligne:pattern[:80] | flags`

```
ace_compact.py:99:        normalized = re.sub(r'\s+', ' ', content.lower().strip())     | (no flags)
archive_anonymizer.py:40:  ("EMAIL", re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A- | (no flags)
archive_anonymizer.py:41:  ("PHONE_INTL", re.compile(r'\+\d{1,3}[\s.-]?\d{4,}'),)        | (no flags)
archive_anonymizer.py:42:  ("PHONE_FR", re.compile(r'\b0[1-9](?:[\s.-]?\d{2}){4}\b'),)   | (no flags)
archive_anonymizer.py:43:  ("SSN_US", re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),)            | (no flags)
archive_anonymizer.py:44:  ("IBAN", re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b'),)    | (no flags)
archive_anonymizer.py:45:  ("CC_VISA", re.compile(r'\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-] | (no flags)
archive_anonymizer.py:46:  ("IPV4", re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),)        | (no flags)
ci_cd_pinning.py:25:        SHA256_PATTERN = re.compile(r'^sha256:[a-f0-9]{64}$')        | (no flags)
ci_cd_pinning.py:27:        SHA1_PATTERN = re.compile(r'^[a-f0-9]{40}$')                | (no flags)
ci_cd_pinning.py:30:        IMAGE_REF_PATTERN = re.compile(                             | (no flags)
ci_cd_pinning.py:60:        if re.match(r'^\d{8}$', tag) or re.match(r'^v?\d+\.\d+\.\d+ | (no flags)
ci_cd_pinning.py:90:        match = re.search(r'uses:\s*([^\s]+)', uses_line)            | (no flags)
ci_cd_pinning.py:348:       (re.compile(r'(?i)(api[_-]?key|secret|token|password)\s*[:  | (?i) inline
ci_cd_pinning.py:349:       (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS access key"),         | (no flags)
ci_cd_pinning.py:350:       (re.compile(r'-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRI | (no flags)
ci_cd_pinning.py:351:       (re.compile(r'ghp_[A-Za-z0-9]{36}'), "GitHub personal toke | (no flags)
ci_cd_pinning.py:352:       (re.compile(r'sk-[A-Za-z0-9]{20,}'), "OpenAI/Stripe API ke | (no flags)
ci_cd_pinning.py:353:       (re.compile(r'xox[baprs]-[A-Za-z0-9-]{10,}'), "Slack token"  | (no flags)
contract_validator.py:65:   if not re.match(r"^[\w.+-]+@example\.com$", email):           | (no flags)
hooks.py:80:                if re.search(pattern, cmd, re.IGNORECASE):                 | re.IGNORECASE
hooks.py:126:               safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", ctx.tool_name  | (no flags)
hooks.py:183:               if re.match(pattern, result.strip()):                      | (no flags)
image_pin.py:17:            SHA256_PATTERN = re.compile(r'^sha256:[a-f0-9]{64}$')      | (no flags)
image_pin.py:18:            SHA256_RAW_PATTERN = re.compile(r'^[a-f0-9]{64}$')         | (no flags)
pii_tokenizer.py:37:        ("EMAIL", re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\  | (no flags)
pii_tokenizer.py:38:        ("PHONE_INTL", re.compile(r'\+\d{1,3}[\s.-]?\(?\d{1,4}\)?  | (no flags)
pii_tokenizer.py:39:        ("PHONE_FR", re.compile(r'\b0[1-9](?:[\s.-]?\d{2}){4}\b'),  | (no flags)
pii_tokenizer.py:40:        ("SSN_US", re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),)          | (no flags)
pii_tokenizer.py:41:        ("IBAN", re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b'),)   | (no flags)
pii_tokenizer.py:42:        ("CC_VISA", re.compile(r'\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s | (no flags)
pii_tokenizer.py:43:        ("CC_MC", re.compile(r'\b5[1-5]\d{2}[\s-]?\d{4}[\s-]?\d{4}[ | (no flags)
pii_tokenizer.py:44:        ("CC_AMEX", re.compile(r'\b3[47]\d{2}[\s-]?\d{6}[\s-]?\d{5} | (no flags)
pii_tokenizer.py:45:        ("IPV4", re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),)       | (no flags)
pii_tokenizer.py:47:        ("NIR_FR", re.compile(r'\b[12]\d{2}(?:0[1-9]|1[0-2])\d{2}\  | (no flags)
pii_tokenizer.py:49:        ("PASSPORT", re.compile(r'\b[A-Z]{2}\d{7}\b'),)            | (no flags)
srs_linter.py:84:           gherkin_blocks = re.findall(                               | (no flags)
srs_linter.py:109:          if re.search(pattern, ac_text, re.IGNORECASE):             | re.IGNORECASE
srs_linter.py:118:          if re.search(pattern, ac_text, re.IGNORECASE):             | re.IGNORECASE
srs_linter.py:130:          if not re.search(r'\b(shall|must|will)\b', ac_text, re.IGNO | re.IGNORECASE
subagent_validator.py:21:   "SUMMARY": re.compile(r'^[A-Za-z0-9 .,;:!?()\-/\'"]{0,500} | (no flags)
subagent_validator.py:23:   "REFS": re.compile(r'^[A-Za-z0-9._/:\-,]{0,2000}$'),       | (no flags)
subagent_validator.py:25:   "ARTIFACTS": re.compile(r'^[A-Za-z0-9._/\-,]{0,2000}$'),   | (no flags)
subagent_validator.py:27:   "TOKENS": re.compile(r'^\d{0,10}$'),                       | (no flags)
subagent_validator.py:28:   "RAW_SIZE": re.compile(r'^\d{0,15}$'),                     | (no flags)
subagent_validator.py:34:   re.compile(r'https?://(?!localhost|127\.0\.0\.1)[^\s]+'),  | (no flags)
subagent_validator.py:35:   re.compile(r'<script', re.IGNORECASE),                     | re.IGNORECASE
subagent_validator.py:36:   re.compile(r'javascript:', re.IGNORECASE),                 | re.IGNORECASE
subagent_validator.py:37:   re.compile(r'\$\([^)]*\)'),                                | (no flags)
subagent_validator.py:38:   re.compile(r'`[^`]+`'),                                    | (no flags)
subagent_validator.py:39:   re.compile(r'\b(eval|exec|import|os\.system|subprocess)\b') | (no flags)
subagent_validator.py:40:   re.compile(r'\b(password|api_key|secret|token)\s*[:=]\s*\S+ | re.IGNORECASE
```

Total: 47 regex sites. Flags: `re.IGNORECASE` used 6 times; inline `(?i)` once (`ci_cd_pinning.py:348`).

---

## 4. Type Hints & Docstrings

### 4.1 Module-level docstrings
24/24 modules start with a `"""` block (every file in `prototype/lib/`). `__init__.py` is a re-export.

### 4.2 Type hints (top-level `def`)

| Module | Top-level defs | With `-> ReturnType` | With param annotation |
|---|---:|---:|---:|
| ace_compact.py | 8 | 6 | 7 |
| adversarial_corpus.py | 4 | 4 | 4 |
| archive_anonymizer.py | 11 | 6 | 10 |
| ci_cd_pinning.py | 9 | 9 | 9 |
| code_api.py | 9 | 5 | 8 |
| contract_validator.py | 6 | 4 | 5 |
| dsl.py | 4 | 4 | 4 |
| hooks.py | 10 | 9 | 10 |
| image_pin.py | 10 | 9 | 10 |
| mcp_trust.py | 8 | 6 | 6 |
| memory_blocks.py | 12 | 6 | 11 |
| mutation_testing.py | 7 | 5 | 5 |
| pii_tokenizer.py | 11 | 9 | 10 |
| property_tests.py | 12 | 11 | 11 |
| s3_residual.py | 16 | 8 | 14 |
| secrets_vault.py | 16 | 5 | 15 |
| security_fallback.py | 3 | 3 | 3 |
| security.py | 15 | 11 | 15 |
| srs_linter.py | 3 | 3 | 3 |
| state.py | 11 | 6 | 8 |
| subagent_firewall.py | 9 | 6 | 7 |
| subagent_validator.py | 4 | 3 | 4 |
| token_ledger.py | 10 | 6 | 6 |
| **Total** | **208** | **143** | **164** |

### 4.3 Docstrings on top-level `def` (line immediately after `def`)

| Module | Top-level defs | with `"""` on next line |
|---|---:|---:|
| ace_compact.py | 8 | 0 |
| adversarial_corpus.py | 4 | 4 |
| archive_anonymizer.py | 11 | 0 |
| ci_cd_pinning.py | 9 | 9 |
| code_api.py | 9 | 2 |
| contract_validator.py | 6 | 4 |
| dsl.py | 4 | 4 |
| hooks.py | 10 | 6 |
| image_pin.py | 10 | 4 |
| mcp_trust.py | 8 | 6 |
| memory_blocks.py | 12 | 0 |
| mutation_testing.py | 7 | 5 |
| pii_tokenizer.py | 11 | 0 |
| property_tests.py | 12 | 11 |
| s3_residual.py | 16 | 0 |
| secrets_vault.py | 16 | 0 |
| security_fallback.py | 3 | 3 |
| security.py | 15 | 4 |
| srs_linter.py | 3 | 3 |
| state.py | 11 | 0 |
| subagent_firewall.py | 9 | 0 |
| subagent_validator.py | 4 | 3 |
| token_ledger.py | 10 | 0 |

(Methods with docstring counted separately: 71 across all modules; class `ace_compact.py` has 6, `archive_anonymizer.py` 7, `memory_blocks.py` 6, `pii_tokenizer.py` 7, `s3_residual.py` 7, `secrets_vault.py` 13, `security.py` 8, `state.py` 5, `subagent_firewall.py` 2, `hooks.py` 2, `image_pin.py` 3, `code_api.py` 3, `token_ledger.py` 2.)

### 4.4 `Any` and `# type: ignore`

`Any` import or usage:
```
prototype/lib/subagent_firewall.py:8: from typing import Optional, List, Dict, Any
prototype/lib/security.py:15: from typing import Optional, Tuple, Dict, Any
prototype/lib/code_api.py:23: from typing import Optional, Tuple, List, Dict, Any
prototype/lib/code_api.py:100: return_value: Any = None
prototype/lib/hooks.py:13: from typing import Optional, Callable, Dict, Any
prototype/lib/hooks.py:33: payload: Dict[str, Any]
prototype/lib/hooks.py:54: modified_payload: Optional[Dict[str, Any]] = None
```

`# type: ignore`:
```
prototype/lib/security.py:37:    AESGCM = None  # type: ignore
prototype/lib/security.py:53:    aes_ctr_hmac_encrypt = None  # type: ignore
prototype/lib/security.py:54:    aes_ctr_hmac_decrypt = None  # type: ignore
```
(3 sites, all in `security.py`, all in the optional-cryptography fallback path.)

---

## 5. Tests Inventory (`prototype/tests/*.py`)

### 5.1 Test files (29) and LOC

| File | LOC | `def test_` |
|---|---:|---:|
| test_ace_compact.py | 88 | 5 |
| test_adversarial_corpus.py | 199 | 17 |
| test_archive_anonymizer.py | 168 | 13 |
| test_ci_cd_pinning.py | 353 | 36 |
| test_code_api.py | 177 | 21 |
| test_contract_validator.py | 236 | 19 |
| test_dsl.py | 61 | 7 |
| test_hooks.py | 215 | 13 |
| test_image_pin.py | 222 | 30 |
| test_mcp_trust.py | 268 | 15 |
| test_memory_blocks.py | 187 | 15 |
| test_mutation_testing.py | 115 | 13 |
| test_pii_tokenizer.py | 128 | 13 |
| test_s3_residual.py | 181 | 17 |
| test_secrets_vault.py | 175 | 15 |
| test_security.py | 169 | 12 |
| test_srs_linter.py | 138 | 19 |
| test_state.py | 63 | 3 |
| test_state_audit_hmac.py | 133 | 7 |
| test_subagent_firewall.py | 124 | 6 |
| test_subagent_validator.py | 138 | 17 |
| test_token_ledger.py | 85 | 6 |
| adversarial_ci_cd_pin.py | 278 | 22 |
| adversarial_hook_bypass.py | 161 | 9 |
| adversarial_pii_bypass.py | 189 | 15 |
| adversarial_prompt_injection.py | 137 | 8 |
| adversarial_sandbox_escape.py | 162 | 15 |
| adversarial_state_corruption.py | 156 | 8 |
| **Total** | **4,706** | **396** |

Test:lib LOC ratio = 4,706 : 5,200 = 0.91.

### 5.2 `from lib.XXX` per test file (count of test files importing each lib module)

```
ace_compact            : 1 file (test_ace_compact.py)        + 1 in adversarial_corpus? — only direct: test_ace_compact
adversarial_corpus     : 1 (test_adversarial_corpus.py)
archive_anonymizer     : 1 (test_archive_anonymizer.py)
ci_cd_pinning          : 2 (test_ci_cd_pinning.py, adversarial_ci_cd_pin.py)
code_api               : 2 (test_code_api.py, adversarial_sandbox_escape.py)
contract_validator     : 1 (test_contract_validator.py)
dsl                    : 1 (test_dsl.py)
hooks                  : 3 (test_hooks.py, adversarial_hook_bypass.py, adversarial_prompt_injection.py)
image_pin              : 2 (test_image_pin.py, adversarial_ci_cd_pin.py)
mcp_trust              : 1 (test_mcp_trust.py)
memory_blocks          : 1 (test_memory_blocks.py)
mutation_testing       : 1 (test_mutation_testing.py)
pii_tokenizer          : 3 (test_pii_tokenizer.py, adversarial_pii_bypass.py, adversarial_prompt_injection.py)
property_tests         : 1 (test_adversarial_corpus.py)
s3_residual            : 1 (test_s3_residual.py)
secrets_vault          : 1 (test_secrets_vault.py)
security               : 3 (test_security.py, test_state_audit_hmac.py, test_s3_residual.py)
srs_linter             : 1 (test_srs_linter.py)
state                  : 5 (test_state.py, test_state_audit_hmac.py, test_token_ledger.py, test_subagent_firewall.py, adversarial_state_corruption.py)
subagent_firewall      : 1 (test_subagent_firewall.py)
subagent_validator     : 2 (test_subagent_validator.py, adversarial_prompt_injection.py)
token_ledger           : 2 (test_token_ledger.py, test_subagent_firewall.py)
```
22 distinct lib modules are imported by tests.

### 5.3 `@pytest.mark.parametrize`, `hypothesis`, `property`

`@pytest.mark.parametrize`: **0 occurrences** in `prototype/tests/`.
`hypothesis` / `@given`: **0 occurrences** in `prototype/tests/`.
`@property` / property-based testing: **0 occurrences** in `prototype/tests/`. The module `lib/property_tests.py` exists, but it provides its own in-house property-test runner (no `hypothesis` dep).

### 5.4 `conftest.py`

`find /home/doz/context-engineering-harness -name conftest.py` returns **no result**. No conftest exists.

---

## 6. CI/Config

### 6.1 `.github/workflows/`

Directory: `/home/doz/context-engineering-harness/.github/workflows/`
Files: 1 (`tests.yml`).

`.github/dependabot.yml`: weekly updates for `github-actions` ecosystem.
`.github/ISSUE_TEMPLATE/`: `bug_report.md`, `feature_request.md`.

`tests.yml` content:
```yaml
name: tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest
    - name: Run all tests
      run: |
        cd prototype
        python -m pytest tests/ -v
    - name: Run adversarial tests separately
      run: |
        cd prototype
        python -m pytest tests/adversarial_*.py -v
    - name: Verify install script
      run: |
        bash prototype/bin/install.sh
    - name: Run demo
      run: |
        cd prototype
        bash bin/ctxh-demo 2>&1 | head -50
```

CI steps: 6. Matrix: Python 3.10/3.11/3.12. Single external dep installed: `pytest`. Workflow uses `actions/checkout@v4` and `actions/setup-python@v5` (mutable tags; not pinned by SHA — see `ci_cd_pinning` module).

### 6.2 `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements*.txt`

`find . -name "pyproject.toml" -o -name "setup.py" -o -name "setup.cfg" -o -name "requirements*.txt"` returns **no result**.

### 6.3 `bin/install.sh` content

Path: `/home/doz/context-engineering-harness/prototype/bin/install.sh` (44 lines).

```bash
#!/usr/bin/env bash
# CE-Harness POV minimal installer
# No external dependencies — pure Python stdlib.

set -e

cd "$(dirname "$0")/.."

echo "═══════════════════════════════════════════════════════════════"
echo "  CE-Harness POV — Installation"
echo "═══════════════════════════════════════════════════════════════"

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 not found. Install Python 3.11+ first."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python $PY_VERSION found"

# Check stdlib modules we need
for mod in sqlite3 hashlib hmac json; do
    if ! python3 -c "import $mod" 2>/dev/null; then
        echo "❌ Module $mod not available (should be stdlib)"
        exit 1
    fi
done
echo "✓ All stdlib modules available"

# Make bin/ executable
chmod +x bin/ctxh bin/ctxh-demo 2>/dev/null || true
echo "✓ Binaries made executable"

# Test
echo ""
echo "▶ Testing POV..."
./bin/ctxh --help

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Installation complete"
echo "  Next: ./bin/ctxh-demo"
echo "═══════════════════════════════════════════════════════════════"
```

### 6.4 `Makefile`, `tox.ini`, `pytest.ini`

**None of these files exist** anywhere in the tree.

---

## 7. Doc Structure

### 7.1 `docs/` sizes (bytes)

```
ADVERSARIAL.md       12,923
API.md               18,532
ARCHITECTURE.md      13,130
FAQ.md               11,798
HOOKS.md              9,398
INSTALLATION.md       6,203
QUICKSTART.md         3,906
```

### 7.2 `audit/` files

```
00-pov-recap-2026-06-08.md                    5,631
01-swebok-validation-2026-06-08.md            7,477
02-swebok-100pct-validation-2026-06-08.md    7,606
03-adversarial-analysis-2026-06-08.md       18,237
04-adversarial-passe2-post-qw-2026-06-08.md 17,590
05-final-zero-crit-2026-06-09.md             7,380
06-adversarial-passe3-residual-2026-06-09.md 5,873
07-zero-residual-2026-06-09.md               8,316
08-LESSONS-LEARNED-FOR-SWEBOK-2026-06-09.md 19,433
council-bridge-results.jsonl                 2,871
council-bridge-transitions.log                 211
run_council_gates.sh                         8,023
fresh-eyes-v102/                              (audit-in-progress)
```

### 7.3 `corpus/` structure

```
corpus/
  sources/INDEX.md            121 lines
  findings/00-synthesis.md   266 lines
  anti-patterns/INDEX.md      215 lines
```

Only 3 files total in `corpus/`. Subdirectories `sources/`, `findings/`, `anti-patterns/` exist but are sparsely populated.

### 7.4 `strategy/`, `design/`

```
strategy/00-strategy-2026-06-08.md   33,069 bytes
design/00-architecture.md            22,688 bytes
```

---

## 8. Git State

### 8.1 `git log --oneline | head -20`
```
6b052ea fix(quality): 14 latent bugs from fresh-eyes audit
3bfc282 fix(ci): make tests pass without cryptography/pyyaml (stdlib-only CI)
32c08e4 Translate all docs to English + add comprehensive GitHub documentation
2323875 Add Lessons Learned for swebok-v4-harness-distilled
7153595 CE-Harness v1.0 — Zero-Residual Production-Ready
```
(Only 5 commits; 5 < 20.)

### 8.2 `git tag -l`
```
v1.0.1
v1.0.2
```

### 8.3 `git branch -a`
```
* main
  remotes/origin/main
```

### 8.4 `git status`
```
Sur la branche main
Fichiers non suivis:
  (utilisez "git add <fichier>..." pour inclure dans ce qui sera validé)
	audit/fresh-eyes-v102/

aucune modification ajoutée à la validation mais des fichiers non suivis sont présents (utilisez "git add" pour les suivre)
```
Branch clean. Only untracked content is `audit/fresh-eyes-v102/` (this audit's working dir).

