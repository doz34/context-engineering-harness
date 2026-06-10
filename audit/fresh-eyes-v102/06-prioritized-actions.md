# Plan d'actions priorisé — Audit Fresh-Eyes v1.0.2

> **Spec Kit phase**: /speckit.implement (synthèse)
> **Date**: 2026-06-10
> **Inputs**: 05-findings.md (26 findings, score 62.65/100)
> **Output**: actions concrètes P0/P1/P2/P3 pour v1.0.3

## Synthèse exécutive

**Verdict** : 🟡 **ACCEPTABLE avec 1 CRIT + 5 HIGH bloquants**

| Sévérité | Count | Décision |
|----------|-------|----------|
| CRIT (P0) | 1 | **FIX OBLIGATOIRE v1.0.3** |
| HIGH (P1) | 5 | **FIX OBLIGATOIRE v1.0.3** |
| MED (P2) | 7 | Fix si temps, sinon v1.0.4 |
| LOW (P3) | 13 | Backlog v1.0.4+ |

**Effort estimé** : 2-3h pour P0+P1 complet, 1h pour P2 faciles.

## Plan v1.0.3 (P0 + P1 obligatoire)

### Batch A — F-001 [CRIT] : Dogfooding CI pinning

**Fix** :
1. Pinner `actions/checkout@v4` → SHA-256 actuel
2. Pinner `actions/setup-python@v5` → SHA-256 actuel
3. Ajouter une étape CI qui exécute `python -c "from lib.ci_cd_pinning import validate_workflow_file; r = validate_workflow_file('.github/workflows/tests.yml'); assert r.is_valid"`

**Effort** : 15 min
**Fichiers touchés** : `.github/workflows/tests.yml`

### Batch B — F-002 [HIGH] : security_fallback docstring

**Fix** : Remplacer la docstring pour refléter SHA256-CTR (pas AES). Ajouter un warning explicite.

**Effort** : 5 min
**Fichiers touchés** : `lib/security_fallback.py:1-6`

### Batch C — F-003 [HIGH] : state.record_token negative validation

**Fix** : Ajouter validation `if not isinstance(tokens, int) or tokens < 0: raise ValueError`. Ajouter un test.

**Effort** : 10 min
**Fichiers touchés** : `lib/state.py:113` + `tests/test_state.py` (nouveau test)

### Batch D — F-004 + F-005 [HIGH] : verify_audit_chain + encryption at-rest

**Fix F-004** : Ajouter `StateDB.verify_audit_chain(master_key_path) -> bool` qui :
1. Charge RotatingHMAC
2. Itère audit_event
3. Re-vérifie chaque hash
4. Vérifie le chain prev_hash → hash

**Fix F-005** : Documenter explicitement pourquoi le payload n'est PAS chiffré at-rest (perf, permet query/verify). Ne pas le chiffrer (over-engineering).

**Effort** : 45 min
**Fichiers touchés** : `lib/state.py` (nouvelle méthode)

### Batch E — F-006 [HIGH] : hooks timestamp sanitization

**Fix** : Sanitize `ctx.timestamp` avec même regex que `safe_name`. Ajouter test.

**Effort** : 10 min
**Fichiers touchés** : `lib/hooks.py:131` + `tests/test_hooks.py`

### Batch F (bonus) — F-008 + F-011 [MED] : tokenizer singleton + narrow except

**Fix F-008** : Utiliser `get_tokenizer()` au lieu de `PIITokenizer()` dans hooks.
**Fix F-011** : Narrow `except (ImportError, AttributeError)` + ajouter log warning.

**Effort** : 15 min
**Fichiers touchés** : `lib/hooks.py:215`, `lib/state.py:178`

## Tests à ajouter (5 nouveaux)

| ID | Module | Test |
|----|--------|------|
| T-001 | state.py | `record_token(-1)` raises ValueError |
| T-002 | state.py | `verify_audit_chain` passes on clean chain |
| T-003 | state.py | `verify_audit_chain` detects tampered row |
| T-004 | hooks.py | `post_tool_use_clear_result` blocks path traversal in timestamp |
| T-005 | hooks.py | `post_tool_use_pii_tokenize` uses singleton (deterministic) |

## v1.0.4 backlog (P2 + P3)

| ID | Sévérité | Effort | Description |
|----|----------|--------|-------------|
| F-007 | MED | 1.5h | pii_tokenizer checksum validation (IBAN/NIR/CC) |
| F-009 | MED | 30min | install.sh élargir validation stdlib |
| F-010 | MED | 15min | Clarifier corpus = bibliographie |
| F-012 | MED | 15min | install.sh Windows warning |
| F-013 | MED | 30min | ci_cd_pinning semver 3-state |
| F-014-F-026 | LOW | 3-4h | Dette technique diverse |

**Effort total v1.0.4** : ~6-7h. Candidat pour un futur sprint.

## Critères de release v1.0.3

- [x] F-001 fixé (CI pinning dogfooded)
- [x] F-002 fixé (docstring corrigée)
- [x] F-003 fixé (validation tokens)
- [x] F-004 fixé (verify_audit_chain)
- [x] F-006 fixé (timestamp sanitization)
- [x] F-008 fixé (PII singleton)
- [x] F-011 fixé (narrow except)
- [x] Tests 100% verts (318 existants + 5 nouveaux = 323)
- [x] CHANGELOG v1.0.3 mis à jour
- [x] PR créé et mergé
- [x] Tag v1.0.3 pushé
- [x] GitHub release avec notes
- [x] Mémo long-terme persisté

## Rollback strategy

Si un fix casse les tests :
1. Identifier le fix coupable (binary search via `git stash`)
2. Documenter dans CHANGELOG
3. Décider : fix le fix ou revert partiel

Si l'effort > 4h : ne livrer que F-001 (CRIT) + F-003 (HIGH) + F-006 (HIGH), reporter le reste à v1.0.3.1.
