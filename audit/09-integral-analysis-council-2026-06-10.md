# Analyse Intégrale CE-Harness — Conseil Adversarial

**Date** : 2026-06-10
**Projet** : Context Engineering Harness (CE-Harness) — v1.0.3
**Localisation** : `/home/doz/context-engineering-harness/`
**GitHub** : https://github.com/doz34/context-engineering-harness
**Méthodologie** : Conseil de 4 consultants adversariaux (QA Lead, CISO, Architect, DevOps Lead) en parallèle + vérifications indépendantes

---

## 🎯 Production Readiness Score

| Consultant | Score | Tendance |
|------------|------:|----------|
| **QA Lead** | **62 / 100** | Modéré — 324 tests passent mais test theater significatif |
| **CISO** | **18 / 100** | TRÈS sévère — claims crypto non vérifiés, plusieurs dead modules |
| **Architect** | **38 / 100** | Sévère — feature-broad mais architecture thin, v2 infeasible |
| **DevOps Lead** | **42 / 100** | Sévère — démo ≠ prod, pas d'observabilité, pas de packaging |

### **Score global (moyenne) : 40 / 100**

> **Verdict** : Le projet est un **prototype de référence bien documenté et bien testé pour un POV**, mais **n'est PAS production-ready pour données sensibles**. Il est adapté à : recherche, education, intégrateurs qui câblent eux-mêmes les vrais composants de prod. Il n'est PAS adapté à : déploiement SaaS, données RGPD/HIPAA/SOC2, exécution LLM multi-tenant sans isolation OS.

**Fourchette honnête** : 40 (moyenne) à 55 (modèle optimiste si on ignore les findings non-bloquants) à 25 (modèle paranoïaque CISO).

---

## 📦 Features concrètes offertes

### 1. Architecture 5-couches (partiellement implémentée)

| Couche | Module(s) | État | Notes |
|--------|-----------|:----:|-------|
| L0 Corpus | `corpus/` (offline) | ✅ Réel | 40+ sources, 30 findings, 20 anti-patterns |
| L1 Memory Blocks | `lib/memory_blocks.py` (207 LOC) | ✅ Réel | MemGPT-style avec ACL + per-block content hash |
| L2 State / Session | `lib/state.py` (374 LOC) + `lib/token_ledger.py` (160 LOC) | ✅ Réel | SQLite WAL + HMAC chain |
| L3 Working Context | `lib/ace_compact.py` (139 LOC) | ⚠️ Partiel | ACE = filtre statique (TODO embeddings, pas de reflector) |
| L4 LLM View | **Aucun module** | ❌ Aspirational | Documenté dans `design/` mais pas implémenté |

### 2. 4-Pillars Context Engineering (Anthropic 2025-09)

- **Write** — `lib/state.py` (SQLite WAL) + `lib/memory_blocks.py`
- **Select** — `lib/srs_linter.py` (AC mesurabilité, 19 patterns) + `lib/contract_validator.py` (OpenAPI 3.x / AsyncAPI 2-3.x)
- **Compress** — `lib/ace_compact.py` (ACE-style) + `lib/token_ledger.py` (triggers 60/70/85/95%)
- **Isolate** — `lib/subagent_firewall.py` + `lib/subagent_validator.py` (5 fields, 7 anti-smuggling)

### 3. 8 Invariants (3 enforced / 3 partial / 2 aspirational)

1. ✅ **Token budget par phase** (enforced) — triggers 60/70/85/95%
2. ⚠️ **Code-as-API** (aspirational) — `lib/code_api.py` est AST-only, pas Docker
3. ⚠️ **Subagent firewall** (partial) — logger, pas boundary d'isolation réel
4. ⚠️ **Compaction ACE-style** (partial) — filtre statique vs reflector appris
5. ⚠️ **Layout head/tail** (aspirational) — pas de module head/tail
6. ⚠️ **Adversarial gates** (partial) — T1/T2/T3 + Drew 4 modes documentés, pas exécutés en runtime
7. ❌ **Pre-hydrate per phase** (aspirational) — `lib/pre_hydrate.py` n'existe pas (drift README↔code)
8. ❌ **Self-improving playbook (ACE)** (aspirational) — pas d'apprentissage online

### 4. 14 Modules Sécurité / Qualité

| Module | LOC | Production-ready | Notes |
|--------|----:|:----------------:|-------|
| `security.py` (AES-256-GCM + RotatingHMAC) | 290 | ✅ Réel | AESGCM via `cryptography`, fallback SHA256-CTR honnêtement étiqueté (F-002) |
| `security_fallback.py` (SHA256-CTR) | 91 | ⚠️ | Coverage 19%, pas de tests dédiés |
| `pii_tokenizer.py` (11 patterns + HMAC) | 223 | ✅ Réel | EMAIL, PHONE, SSN, IBAN, CC, IPV4, NIR, PASSPORT + NFKC normalizer |
| `code_api.py` (AST sandbox) | 323 | ✅ Réel | Whitelist + dunder deny, résiste aux escapes classiques |
| `subagent_validator.py` | 183 | ✅ Réel | 7 dangerous patterns, length/regex strict |
| `srs_linter.py` (AC mesurabilité) | 213 | ✅ Réel | 18 patterns |
| `mcp_trust.py` (TOFU + signing) | 217 | ⚠️ Dead code | Pas de call site en production |
| `secrets_vault.py` (ACL + 0o600) | 253 | ⚠️ | Wildcard `*` footgun, ACL check non auditée |
| `contract_validator.py` | 230 | ✅ | OpenAPI/AsyncAPI |
| `memory_blocks.py` | 207 | 🐛 | **FK ordering bug** dans `delete()` (bloque la suppression par le owner) |
| `mutation_testing.py` | 218 | 🐛 | **`simulate_test_run` = `random.random()`**, gate 0.7 = coin flip |
| `ci_cd_pinning.py` | 366 | ✅ | SHA-256 patterns, dogfooded dans CI |
| `image_pin.py` (container digest) | 220 | ✅ | 36 tests |
| `archive_anonymizer.py` (GDPR Art.17) | 155 | ⚠️ Dead code | Pas de call site |
| `s3_residual.py` (per-tenant + CAB + EOL) | 205 | ⚠️ | Multi-tenant en théorie = multi-fichier SQLite |

### 5. Adversarial Testing

- **50+ payloads** dans `lib/adversarial_corpus.py` (21 CRIT / 17 HIGH / 8 MED / 4 LOW)
- **6 fichiers adversarial_*.py** (sandbox escape, PII bypass, prompt injection, state corruption, hook bypass, CI/CD pin) = **77 tests**
- **17 tests corpus-driven** dans `test_adversarial_corpus.py` — ⚠️ plusieurs ne font que `print()` au lieu d'`assert()`

### 6. Property-Based Testing

- 4 properties : DSL roundtrip, PII idempotence, subagent strict, SHA-256 format
- ⚠️ 2 properties supplémentaires définies mais non exécutées
- ⚠️ Plusieurs properties sont des tautologies (si PII non détecté, idempotence = trivially true)

### 7. CLI + Demo

- `bin/ctxh {init, measure, ledger, spawn}` — 4 subcommands
- `bin/ctxh-demo` — end-to-end 53,000 → 4,900 tokens (**10.8× mesuré**)
- `bin/install.sh` — 44 lignes, stdlib-only, idempotent
- 🐛 **Bug démo** : `bin/ctxh:173` passe `'sub_1'` au lieu de `f'{phase_id}_sub_{N}'` → `is_valid: False` est affiché, exit 0

### 8. CI/CD

- ✅ Actions SHA-pinned (`actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`)
- ✅ Self-audit dogfooding step (`validate_workflow_file` sur lui-même)
- ✅ Matrix Python 3.10/3.11/3.12/3.13
- ❌ Pas de cache pip (~3-5s/run wasted)
- ❌ Pas d'upload artifacts (junit XML, state DB)
- ❌ Single runner (ubuntu-latest only), no macOS, no ARM
- ❌ No fail-under coverage

### 9. Distribution

- **Git clone + `bash install.sh`** uniquement
- ❌ Pas de PyPI (`pyproject.toml` absent)
- ❌ Pas de Docker image
- ❌ Pas de release tarball signé

---

## 🚨 Risques Critiques / High

### CRIT (bloquants prod avec données sensibles)

1. **`state.db` est en SQLite plaintext** (CWE-311)
   - Le README/CHANGELOG prétendent "AES-256-GCM at rest"
   - `lib/state.py:25` fait `sqlite3.connect(self.path)` direct, **PAS** via `EncryptedDB`
   - `EncryptedDB` n'est utilisé que par `SecretsVault` (lib/secrets_vault.py:50)
   - Tout le audit_event, log_events, adversarial_log → lisibles par n'importe quel process avec accès disque

2. **"Forward secrecy" = misleading label** (CWE-330)
   - Toutes les epoch keys sont dérivées du même master via PBKDF2
   - Master compromise = toutes les epochs compromises
   - Relabel en "epoch compartmentalization" ou implémenter vrai ratchet (Signal-style)

3. **Demo e2e FAIL** — `bin/ctxh-demo` affiche `🔒 Isolation: is_valid: False`
   - Bug : `bin/ctxh:173` passe `verify_isolation('sub_1')` au lieu de `f'{phase_id}_sub_{N}'`
   - Le claim "10.8× economy verified" n'est PAS vérifié end-to-end
   - CI vert car exit 0 et `head -50` tronque la ligne fautive

4. **Mutation testing = coin flip** (lib/mutation_testing.py:144-149)
   - `simulate_test_run` utilise `random.random()` pour décider killed/survived
   - Le gate "refuses PASS if mutation score < 0.7" est enforce contre un nombre fictif
   - Commentaire en ligne 139-142 admet : "For POV, we simulate based on heuristics"

5. **Memory blocks delete cassé** (lib/memory_blocks.py:155-161)
   - FK ordering : delete block d'abord, ACL ensuite → IntegrityError
   - Owners ne peuvent pas supprimer leurs blocks
   - Test ne couvre que le path PermissionError, pas le success path

6. **5-layer architecture = documentation theater**
   - Pas de L4 module
   - `lib/pre_hydrate.py` référencé en README:43 mais inexistant
   - Hooks library-only (HOOK_REGISTRY défini, jamais fired en prod)
   - Le "firewall" est un wrapper `execute_fn`, pas une isolation boundary

### HIGH

7. **Hooks system jamais wired** (lib/hooks.py)
   - 7 hooks documentés (PreToolUse/PostToolUse/Subagent*) — aucun ne fire en runtime
   - Le dossier `hooks/` est vide
   - PostToolUse PII tokenization et clear-result ne s'exécutent jamais en session réelle

8. **PII regex bypassable** (lib/pii_tokenizer.py)
   - `'a l i c e @ a c m e . c o m'` (whitespace) → 0 hits
   - `'alice [at] acme [dot] com'` → 0 hits
   - `'alice(at)acme.com'` → 0 hits
   - IBAN pattern misses standard format (whitespace séparateur)
   - NIR pattern requires 15 digits, real NIR = 13 digits

9. **SubagentFirewall = stub mode only**
   - `_stub_execute` est le default path, pas un `execute_fn` réel
   - Le demo runs _stub_execute
   - Pas de boundary d'isolation réelle

10. **verify_audit_chain = dead code** (F-004)
    - Ajouté en v1.0.3 mais jamais appelé hors tests
    - Le README claim "tamper-evident" n'est PAS vérifié en runtime

11. **v2 roadmap infeasible** depuis v1
    - Council Bridge "real" → besoin LLM client (absent)
    - Docker sandbox → casserait le stdlib-only
    - Multi-tenant Postgres → réécriture du schema layer
    - Raft consensus → besoin network stack (absent)

12. **Coverage non-enforced** + security_fallback 19% tested
    - Pas de `fail-under` dans CI
    - `lib/security_fallback.py` = 30/37 statements missed
    - Zero test dans `tests/` n'importe `security_fallback`

13. **Python version requirement contradictory**
    - README/CLAUDE.md : 3.10+
    - bin/install.sh:15 : 3.11+
    - Pas de `from __future__ import annotations` dans hooks.py (utilise `list[X]`)

### MED / LOW (autres)

- `os.popen('date')` dans `bin/ctxh:37` (locale-dépendant)
- Pas de SIGTERM handler dans `bin/ctxh` (state.db dangling on kill -9)
- Pas d'observabilité (logs = `print()`, pas de JSON structuré, pas de /healthz, pas de /metrics)
- PII salt per-process non persisté → tokens différents entre runs
- DSL = key:value parser de 17 lignes, branding excessif

---

## 🔍 Couverture OWASP LLM Top 10

| Risque | État |
|--------|------|
| LLM01 Prompt Injection | partial (10-pattern blocklist) |
| LLM02 Insecure Output | partial (sandbox AST OK, PII bypassable) |
| LLM03 Training Data Poisoning | **missing** |
| LLM04 Model DoS | partial (token budget ok, no tool-call cap) |
| LLM05 Supply Chain | partial (CI pinned ok, stdlib non pinned) |
| LLM06 Sensitive Disclosure | **missing** (state.db plaintext) |
| LLM07 Insecure Plugin | partial (MCP trust = dead code) |
| LLM08 Excessive Agency | partial (firewall = logger) |
| LLM09 Overreliance | **missing** |
| LLM10 Model Theft | N/A |

---

## 💡 Recommandations (par priorité)

### Sprint immédiat (1-2 jours)
1. **Fixer le bug demo** (`bin/ctxh:173` → `f'{phase_id}_sub_{N}'`) + ajouter e2e test qui assert `is_valid: True`
2. **Wire `verify_audit_chain`** dans le startup de `bin/ctxh` (F-004 fixé mais inutilisé)
3. **Documenter honnêtement** : relabel "forward secrecy" → "epoch compartmentalization", retirer claim "AES-256-GCM at rest" (le chiffrement réel = SecretsVault only)
4. **Fix `memory_blocks.delete()`** : inverser l'ordre (delete ACL avant block)
5. **Replace `simulate_test_run` random** par real mutation testing (mutmut/courier) OU remove le gate 0.7

### Sprint S2 (1 semaine)
6. **Chiffrer state.db at rest** : wrapper `EncryptedDB` autour de `StateDB`, OU migrer vers SQLCipher
7. **Add coverage gate** : `pytest --cov=lib --cov-fail-under=85` dans CI
8. **PII detection hardening** : ajouter deobfuscation pour `[at]`/`[dot]`/whitespace
9. **Wire hooks** dans `bin/ctxh` et `bin/ctxh-demo` (currently le HOOK_REGISTRY est défini mais jamais fired)
10. **Fix Python version drift** : 3.10+ partout (README, install.sh, CI matrix), `from __future__ import annotations` partout

### Sprint S3 (2-4 semaines) — v1.1 production-honest
11. Observabilité minimale : `logging` module + JSON output + env-controlled log level
12. Packaging : `pyproject.toml` + PyPI release
13. Tests manquants : concurrency, Unicode/homoglyph, ReDoS, cross-module integration
14. Ajouter `is_valid: True` e2e test pour demo (couvre CRIT-3)
15. Relire 8 invariants et marquer `partial`/`aspirational` honnêtement dans README

### Vision v2 (Q4 2026) — Separate codebase
- Council Bridge avec LLM client réel (pas stubbed)
- Docker sandbox (au-dessus du AST)
- Multi-tenant Postgres via Repository pattern
- Raft consensus pour audit chain distribué

**Recommandation stratégique** : v1 est un **excellent POV de référence** et une base de recherche. Pour aller en production, soit (a) accepter le statut "library + référence" et publier en l'état avec des caveats honnêtes, soit (b) allouer 2-3 sprints pour fermer les CRIT/HIGH, soit (c) démarrer v2 sur une nouvelle base.

---

## 📊 Statistiques

- **LOC total lib/** : 5,385 lignes (23 modules)
- **LOC CLI + install** : 294 lignes
- **Tests** : 324 (claimé) / 22 fichiers test_* + 6 fichiers adversarial_*
- **Audit reports** : 8 passes adversariales précédentes (audit/00-08)
- **Coverage mesuré** : 84% lib-only (security_fallback 19%, token_ledger 59%)
- **Demo economy** : 10.8× mesuré (claim) / non-vérifié end-to-end (bug sub_id)
- **Vulnérabilités CRIT ouvertes** : 6 (CISO + Architect + QA)
- **Vulnérabilités HIGH ouvertes** : 7+

---

## 📎 Signatures du Conseil

| Consultant | Score | Voix |
|------------|------:|------|
| **QA Lead** | 62/100 | "324 tests pass mais test theater, le demo est brisé en silence" |
| **CISO** | 18/100 | "Crypto claims false, state.db plaintext, plusieurs modules dead" |
| **Architect** | 38/100 | "Feature-broad mais architecture thin, v2 non-évolutionnaire" |
| **DevOps Lead** | 42/100 | "Demo ≠ prod, zero observability, pas de packaging" |

**Moyenne** : **40/100** — production-readiness en l'état

---

*Lié à :*
- `audit/00-pov-recap-2026-06-08.md` (POV initial)
- `audit/01-02-...-08` (8 passes adversariales précédentes)
- `audit/fresh-eyes-v102/` (audit v1.0.2→v1.0.3 : 26 findings, 8 fixés)
- `CHANGELOG.md` (v1.0.3 release notes)
- `README.md` (claims marketing à recadrer)
