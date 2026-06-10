# Findings bruts — Audit Fresh-Eyes v1.0.2

> **Spec Kit phase**: /speckit.implement (étape collecte)
> **Date**: 2026-06-10
> **Source**: Explore agent (inventory.md 720 lignes) + 4 reviewers simulés rigoureux

## Légende sévérité

- **CRIT (P0)** : bloquant release, exploitable, dogfooding failure
- **HIGH (P1)** : fix sous 1 semaine, risque réel
- **MED (P2)** : fix sous 1 mois, qualité/conformité
- **LOW (P3)** : nice-to-have, dette technique

## Inventaire clé (depuis inventory.md)

| Métrique | Valeur | Verdict |
|----------|--------|---------|
| Modules Python | 24 (23 lib + 1 `__init__`) | OK |
| LOC total lib | 5,200 | OK |
| Fonctions top-level | 78 (76 publiques, 2 privées) | OK |
| Classes | 51 | OK |
| Fichiers tests | 29 (4,706 LOC, 396 `def test_`) | OK (>318 claimés) |
| Type hints retour | 143/208 (68.7%) | ⚠️ < 80% |
| Type hints params | 164/208 (78.8%) | ⚠️ < 90% |
| `# type: ignore` | 3 (tous dans security.py) | OK |
| `Any` usages | 4 modules | OK |
| `@pytest.mark.parametrize` | 0 | ❌ Répétitif |
| `hypothesis` | 0 | ❌ Property-based tests manquants |
| `conftest.py` | absent | ⚠️ |
| Python versions testées | 3.10, 3.11, 3.12 (3.13 absent) | ⚠️ |
| `pyproject.toml` | absent | ❌ Standard moderne |
| Lock file | absent | ❌ Supply chain |
| Coverage report en CI | absent | ❌ |
| Lint en CI | absent | ❌ |
| Dependabot | présent (GH Actions only, pas Python) | ⚠️ |
| `corpus/` fichiers | 3 (602 LOC) vs claim 40+ sources | ⚠️ |
| Workflows GH | 1 (`tests.yml`, 6 steps) | OK |

## Findings détaillés

### F-001 [CRIT] Dogfooding failure : le projet n'utilise pas sa propre lib de pinning

**Fichiers** : `.github/workflows/tests.yml:18, 22`
```yaml
- uses: actions/checkout@v4           # ❌ MUTABLE TAG
- uses: actions/setup-python@v5      # ❌ MUTABLE TAG
```

**Pourquoi c'est CRIT** : Le module `lib/ci_cd_pinning.py` (366 LOC) est conçu pour refuser ces tags, mais le projet lui-même les utilise. C'est la preuve la plus visible que le harness n'est pas dogfooded. Si un attaquant compromet `actions/checkout@v4` (par tag hijacking), il contrôle le CI du projet.

**Diff vs audit précédent** : Les 4 passes adversariales ont audité le code en isolation, jamais le `.github/workflows/` du projet lui-même. Le dogfooding est un angle que seul un audit "fresh-eyes" du repo complet peut attraper.

**Fix** : Pinner les 2 actions à leur SHA-256 actuel + ajouter une étape CI qui exécute `ci_cd_pinning.validate_workflow_file` sur le workflow (dogfooding explicite).

---

### F-002 [HIGH] security_fallback.py : cipher claim ≠ cipher impl

**Fichier** : `lib/security_fallback.py:4, 14, 56`
```python
# Docstring ligne 4 :
"AES-256-CTR + HMAC-SHA256 (encrypt-then-MAC)"

# Mais ligne 56 :
def _stream_encrypt(key, nonce, data):
    # "Simple SHA256-CTR stream cipher (POV fallback)"
    keystream = hashlib.sha256(block_input).digest()
```

**Pourquoi c'est HIGH** : Le module documente "AES-256-CTR" mais implémente en réalité un SHA256-CTR (hash-based, pas de chiffrement par blocs). SHA256-CTR n'est **pas** équivalent en sécurité à AES-256-CTR. Si un user lit la docstring et configure son système en conséquence (ex: exigences de conformité RGPD exigeant AES), il fait une confiance mal placée.

**Fix** : Corriger la docstring pour refléter la réalité. Soit :
- (a) Renommer en "SHA256-CTR fallback (NOT AES)" et clarifier les limitations
- (b) Implémenter un vrai AES-256-CTR via `cryptography` (mais ça brise le claim stdlib-only)

**Recommandation** : (a) — la transparence est plus importante que le marketing.

---

### F-003 [HIGH] state.py : `record_token` accepte les valeurs négatives

**Fichier** : `lib/state.py:110-130`
```python
def record_token(self, phase_id, component, direction, tokens, ...):
    # Aucun check sur `tokens`
    c.execute("INSERT INTO token_event ... VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (..., tokens, ...))
    c.execute("UPDATE phase SET tokens_used = tokens_used + ? WHERE id = ?",
              (tokens, phase_id))
```

**Pourquoi c'est HIGH** : Si un sous-agent (ou un bug) appelle `record_token(phase_id, comp, dir, -999999)`, le `tokens_used` de la phase est décrémenté. Un attaquant peut recharger son budget à volonté en injectant des `tokens` négatifs. Le `token_ledger` n'a aucune protection contre ça.

**PoC** : `ctxh measure --phase p1 --component foo --direction in --tokens -1000000`

**Fix** : Ajouter `if not isinstance(tokens, int) or tokens < 0: raise ValueError("tokens must be >= 0")` en haut de `record_token`.

---

### F-004 [HIGH] state.py : pas de méthode de vérification du HMAC chain

**Fichier** : `lib/state.py:159-226` (`append_audit`)
**Référence** : `lib/security.py:228-268` (`RotatingHMAC.verify`)

**Pourquoi c'est HIGH** : `append_audit` écrit dans `audit_event` avec un hash HMAC. Mais il n'existe aucune méthode `verify_audit_chain` qui parcourt la table et re-vérifie chaque hash avec la clé d'époque. Le module `RotatingHMAC.verify` existe mais n'est jamais appelé par state.py.

Conséquence : un attaquant avec accès au filesystem peut modifier `state.db` (le chiffrement at-rest via `EncryptedDB` n'est PAS appliqué dans `append_audit` actuel — voir F-005), puis re-calculer tous les hashes s'il a la master key. Sans méthode verify, on ne peut pas détecter la tampering.

**Fix** : Ajouter `StateDB.verify_audit_chain(master_key_path) -> bool` qui :
1. Charge `RotatingHMAC(master_key)`
2. Itère sur `audit_event` ORDER BY id
3. Pour chaque event : recompute hash, `hmac.compare_digest`
4. Vérifie que `prev_hash` correspond au `hash` du row précédent
5. Vérifie que `epoch_id` est dans la fenêtre acceptable

---

### F-005 [HIGH] state.py : `append_audit` n'utilise pas le chiffrement at-rest

**Fichier** : `lib/state.py:159-226`

**Pourquoi c'est HIGH** : `lib/security.py:EncryptedDB` existe (AES-256-GCM). `append_audit` insère du JSON en clair dans `audit_event.payload`. Les payloads contiennent typiquement des events de sécurité (PII tokenize, subagent spawn, etc.) — c'est exactement ce qu'il faut chiffrer at-rest.

**Fix** : Wrapper `append_audit` pour chiffrer le payload via `EncryptedDB` quand disponible. Garder le `prev_hash` et `hash` en clair (sinon verify ne marche pas).

---

### F-006 [HIGH] hooks.py : `post_tool_use_clear_result` — path traversal via `timestamp`

**Fichier** : `lib/hooks.py:131`
```python
full_path = f".ctxh/tool_results/{safe_name}_{ctx.timestamp}.txt"
```

**Pourquoi c'est HIGH** : `safe_name` est sanitizé (line 126) mais `ctx.timestamp` ne l'est pas. Le `HookContext` (line 29-39) permet à l'appelant de setter `timestamp` à n'importe quoi. Un agent malveillant (ou buggé) peut passer `timestamp = "../../../tmp/payload"` et écrire hors de `.ctxh/tool_results/`.

**PoC** : `hooks.fire(HookContext(event=POST_TOOL_USE, payload={...}, tool_name="x", timestamp="../../etc/cron.daily/payload", tool_result="X"*1000))`

**Fix** : Sanitize `ctx.timestamp` avec le même `re.sub(r"[^A-Za-z0-9_.-]", "_", ...)` que pour `safe_name`, ou utiliser un hash du timestamp (déjà fait pour `safe_name` quand vide).

---

### F-007 [MED] pii_tokenizer.py : patterns IBAN/NIR/CC sans validation checksum

**Fichier** : `lib/pii_tokenizer.py:41, 42-44, 47`

```python
("IBAN", re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b')),
("CC_VISA", re.compile(r'\b4\d{3}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')),
("NIR_FR", re.compile(r'\b[12]\d{2}(?:0[1-9]|1[0-2])\d{2}\d{3}\d{3}\d{2}\b')),
```

**Pourquoi c'est MED** :
- **IBAN** : matche "AB12XY" (n'importe quel 2 lettres + 2 chiffres + 1-30 alphanum). Un vrai IBAN a un checksum mod-97 sur les 4 premiers chars. Le pattern actuel a un taux de faux positifs énorme.
- **CC_VISA/MC/AMEX** : pas de validation Luhn. Un numéro `4123-4567-8901-2345` (qui fail Luhn) serait quand même tokenizé.
- **NIR_FR** : pas de validation de la clé (2 derniers chiffres = 97 - (concat 13 premiers) mod 97).

Conséquence : faux positifs = texte légitime tokenizé inutilement (perte info). Mais surtout, un IBAN ou NIR avec checksum invalide ne sera PAS détecté, donnant un faux sentiment de sécurité.

**Fix** : Ajouter une fonction `_validate_iban(iban)`, `_validate_nir(nir)`, `_validate_luhn(cc)` qui return True seulement si le checksum est correct. Appeler après le regex match.

---

### F-008 [MED] hooks.py : `post_tool_use_pii_tokenize` recrée un tokenizer par appel

**Fichier** : `lib/hooks.py:215`
```python
def post_tool_use_pii_tokenize(ctx: HookContext) -> HookResult:
    ...
    tokenizer = PIITokenizer()  # ⚠️ Nouveau salt à chaque appel !
    tokenized, mappings = tokenizer.tokenize(ctx.tool_result)
```

**Pourquoi c'est MED** : `PIITokenizer.__init__` génère un salt aléatoire si `salt=None`. À chaque appel de hook, nouveau salt → le même email sera tokenizé différemment. Le but de la tokenization déterministe (per Anthropic 2025) est justement de **préserver la cohérence** entre appels.

Conséquence : si `alice@acme.com` apparaît dans 5 tool results successifs, on aura 5 tokens différents. Impossible de corréler.

**Fix** : Utiliser le singleton `get_tokenizer()` (line 219 dans pii_tokenizer.py) au lieu d'instancier un nouveau tokenizer.

---

### F-009 [MED] install.sh : validation stdlib trop étroite

**Fichier** : `bin/install.sh:23-28`
```bash
for mod in sqlite3 hashlib hmac json; do
```

**Pourquoi c'est MED** : Le harness utilise au moins 15 modules stdlib (`ast`, `re`, `secrets`, `unicodedata`, `urllib.parse`, `html`, `signal`, `io`, `traceback`, `os`, `sys`, `dataclasses`, `enum`, `contextlib`, `typing`, `subprocess`). Si un Python build a un `python` minimal (ex:某些 Linux distros qui strippent des modules), install.sh dira "OK" mais le harness crashera à l'utilisation.

**Fix** : Élargir la liste à tous les modules utilisés (grep `^import |^from ` dans lib/*.py et générer dynamiquement).

---

### F-010 [MED] corpus : 3 fichiers (602 LOC) vs claim "40+ sources"

**Fichiers** :
- `corpus/anti-patterns/INDEX.md` (215 lignes)
- `corpus/sources/INDEX.md` (121 lignes)
- `corpus/findings/00-synthesis.md` (266 lignes)

**Pourquoi c'est MED** : `corpus/sources/INDEX.md` liste bien 40+ URLs (lignes 9-119 environ), mais le répertoire ne contient pas les sources elles-mêmes. C'est une bibliographie commentée, pas un corpus. La documentation et le CLAUDE.md disent "40+ primary sources" — ambigu entre "listées" et "téléchargées".

**Fix** : Clarifier dans README : "corpus = 40+ URLs cataloguées avec résumé 1-ligne + implications design" (bibliographie), PAS "corpus = 40+ PDFs/papers ingérés". Si c'est le but, fetcher les papers dans `corpus/sources/papers/`.

---

### F-011 [MED] state.py : except clause trop large

**Fichier** : `lib/state.py:173-178`
```python
try:
    from lib.security import RotatingHMAC, load_or_create_master_key
    key = load_or_create_master_key(self.path + ".master")
    rh = RotatingHMAC(key)
except (ImportError, AttributeError, Exception):  # ⚠️ Exception catch tout
    rh = None
```

**Pourquoi c'est MED** : `except Exception` catch absolument tout, rendant les deux clauses précédentes (`ImportError`, `AttributeError`) redondantes. Si `RotatingHMAC` a un bug runtime (ex: `KeyError`), on tombe en fallback SHA-256 simple (legacy) silencieusement. Pas de log, pas d'alerte.

**Fix** : Narrow à `(ImportError, AttributeError)` + ajouter un log warning quand le fallback est activé. Le bug serait détectable en prod.

---

### F-012 [MED] install.sh : pas de warning Windows

**Fichier** : `bin/install.sh` (entier)

**Pourquoi c'est MED** : `lib/code_api.py:232-244` utilise `signal.SIGALRM` pour le timeout sandbox, qui ne fonctionne PAS sur Windows. Un user Windows install + run verra ses sandbox timeout... ne jamais timeout. Faille silencieuse.

**Fix** : Détecter l'OS en haut de install.sh et avertir les Windows users. Soit désactiver le sandbox, soit recommander WSL.

---

### F-013 [MED] ci_cd_pinning.py : semver/date tags marqués "not mutable"

**Fichier** : `lib/ci_cd_pinning.py:60-64`
```python
if re.match(r'^\d{8}$', tag) or re.match(r'^v?\d+\.\d+\.\d+$', tag):
    # Date or semver tags — mutable but acceptable practice
    # We don't block them, just warn
    return False
```

**Pourquoi c'est MED** : `is_mutable_tag` retourne False pour semver/date, donc l'appelant considère ces tags comme safe. Mais un attaquant peut re-publier `python:3.12.0` (c'est déjà arrivé, ex: 2022-12 incident npm). Le commentaire dit "warn" mais aucun code n'émet de warning.

**Fix** : Retourner un 3-state enum (`MUTABLE`, `IMMUTABLE`, `MUTABLE_BUT_TRUSTED`) ou retourner False + drapeau `warn=True`. Ou simplement : retourner True (rejet) avec un override flag `--allow-semver`.

---

### F-014 [LOW] code_api.py : "vars" dans DANGEROUS_NAMES ET SAFE_BUILTINS

**Fichier** : `lib/code_api.py:65, 82`
```python
DANGEROUS_NAMES = {..., "vars", ...}   # line 65
SAFE_BUILTINS = {..., "vars", ...}     # line 82
```

**Pourquoi c'est LOW** : Inconsistance sémantique. Si on lit le code, on se demande pourquoi "vars" est à la fois dangereux et safe. La réponse : le static check refuse `vars()` au niveau AST, mais le runtime ne le ferait pas. C'est documenté, mais c'est un piège à bugs.

**Fix** : Retirer "vars" de SAFE_BUILTINS pour clarifier. Le static check le refusera de toute façon.

---

### F-015 [LOW] security.py : `_epoch_cache` unbounded

**Fichier** : `lib/security.py:178, 199-206`

**Pourquoi c'est LOW** : `RotatingHMAC._epoch_cache` est un dict qui grossit à chaque nouvelle époque (~1 entry / 24h). Pour un process qui tourne 1 an, ~365 entries × ~100 bytes = 36 KB. Pas critique, mais propre = bounded LRU cache (maxsize=100).

**Fix** : Remplacer par `functools.lru_cache` ou ajouter un `if len(self._epoch_cache) > 100: evict oldest`.

---

### F-016 [LOW] pii_tokenizer.py : DRY violation dans `_find_in_original`

**Fichier** : `lib/pii_tokenizer.py:142-156`
```python
if "@" in decoded_value:
    user, _, domain = decoded_value.partition("@")
    encoded = f"{user}%40{domain}"
    pos = original.find(encoded)
    if pos != -1:
        return pos
# Try HTML-entity @ inside the decoded value
if "@" in decoded_value:  # ⚠️ même check
    user, _, domain = decoded_value.partition("@")
    for entity in ("&amp;", "&#64;"):
        ...
```

**Pourquoi c'est LOW** : Le `if "@" in decoded_value:` est dupliqué 2 fois. Le `user, _, domain = decoded_value.partition("@")` aussi. Pure duplication, ~10 lignes sauvées par un seul check + boucle.

**Fix** : Refactor en un seul bloc `if "@" in decoded_value: for variant in [encoded, *html_entities]: try: return original.find(variant) ...`.

---

### F-017 [LOW] hooks.py : regex compilées à chaque appel

**Fichier** : `lib/hooks.py:66-77` (`pre_tool_use_block_destructive`)
**Fichier** : `lib/hooks.py:174-181` (`post_tool_use_summarize_swallowed`)

**Pourquoi c'est LOW** : Les `destructive` et `passing_patterns` sont des listes de strings (pas de `re.compile`). À chaque appel de hook, `re.search(pattern, cmd, ...)` recompile le pattern. Pour un agent qui fait 100 tool calls/sec, c'est 100 recompiles × N patterns par appel.

**Fix** : Module-level `re.compile(...)` pour chaque pattern, ou `re.compile` lazy via `@lru_cache(maxsize=32)`.

---

### F-018 [LOW] hooks.py : `_global_hooks` not thread-safe

**Fichier** : `lib/hooks.py:301-305`

**Pourquoi c'est LOW** : Singleton non protégé par lock. Deux threads qui appellent `get_hooks()` simultanément pourraient créer deux instances. La `HookSystem` elle-même a `self.executed` qui est une `list` (pas thread-safe pour append concurrent).

**Fix** : Ajouter un `threading.Lock` ou utiliser le pattern `functools.cache` (3.9+).

---

### F-019 [LOW] code_api.py : `discover_tools` ne valide pas le contenu

**Fichier** : `lib/code_api.py:295-315`

**Pourquoi c'est LOW** : `discover_tools` retourne la liste des fichiers `.py`/`.ts`/`.js` dans `servers/`. Le code n'est pas lu/validé à la discovery. Si quelqu'un met un fichier malicieux dans `servers/`, l'agent l'exposera et (espérons-le) le sandbox le refusera à l'exec. Mais c'est fail-open au lieu de fail-closed.

**Fix** : À la discovery, `static_check` chaque fichier. Si DENY, retirer de la liste et logger.

---

### F-020 [LOW] Pas de pyproject.toml

**Fichiers** : absent

**Pourquoi c'est LOW** : Le projet n'a pas de `pyproject.toml`, donc pas de metadata PEP 621, pas de dependencies déclarées, pas de `pip install -e .` qui marche. `bin/install.sh` est un workaround.

**Fix** : Ajouter un `pyproject.toml` minimal avec name/version/description. Garder install.sh pour les users qui veulent juste tester sans install.

---

### F-021 [LOW] Pas de lock file

**Fichiers** : absent

**Pourquoi c'est LOW** : Aucune requirement*.txt, poetry.lock, uv.lock. Reproductibilité des installs impossible.

**Fix** : Ajouter `requirements.txt` avec versions pinnées (même si zéro deps externes). Ou `uv.lock`.

---

### F-022 [LOW] CI matrix ne couvre pas Python 3.13

**Fichier** : `.github/workflows/tests.yml:13`
```yaml
python-version: ["3.10", "3.11", "3.12"]
```

**Pourquoi c'est LOW** : Python 3.13 stable depuis oct 2024. Le harness ne teste pas dessus. Si une feature 3.13-only est utilisée (ex: `match` patterns améliorés, `TypeVar` defaults), on ne le saura pas.

**Fix** : Ajouter "3.13" à la matrix.

---

### F-023 [LOW] Pas de coverage report en CI

**Fichier** : `.github/workflows/tests.yml` (entier)

**Pourquoi c'est LOW** : `pytest-cov` n'est pas dans les deps, le CI ne génère pas de rapport de couverture. La claim "317/318 tests pass" n'est pas accompagnée d'un % couverture.

**Fix** : Ajouter `pytest-cov` (dev dep) + step CI `pytest --cov=lib --cov-report=xml`. Optionnel : badge Codecov/Coveralls.

---

### F-024 [LOW] Pas de lint en CI

**Fichier** : `.github/workflows/tests.yml` (entier)

**Pourquoi c'est LOW** : Aucun linter (`ruff`, `black`, `mypy`, `flake8`). Les 8 invariants sont documentés mais pas enforceés par un check automatisé. La dette technique peut s'accumuler.

**Fix** : Ajouter un step CI qui run `ruff check lib/ tests/` (zero-config, stdlib-style).

---

### F-025 [LOW] Pas de property-based tests

**Inventaire** : 0 occurrences de `hypothesis` ou `@given`

**Pourquoi c'est LOW** : `lib/property_tests.py` existe (5.7K) mais ne semble pas utiliser `hypothesis`. Les tests sont des unit tests classiques. Pour les modules avec beaucoup d'invariants (tokenizer, state, hooks), property-based testing attraperait des edge cases manqués.

**Fix** : Ajouter `hypothesis` (dev dep) + 4-6 property tests : idempotence de tokenize/tokenize, monotonicity de budget, etc.

---

### F-026 [LOW] Pas de conftest.py

**Inventaire** : `conftest.py` absent

**Pourquoi c'est LOW** : Les fixtures (state DB tmp, salt path, etc.) sont dupliquées entre fichiers de tests. Une `conftest.py` avec 3-4 fixtures communes réduirait la duplication.

**Fix** : Créer `tests/conftest.py` avec `tmp_state_db`, `tmp_master_key`, `pii_tokenizer_session`.

---

## Récap findings

| Severity | Count | IDs |
|----------|-------|-----|
| CRIT (P0) | 1 | F-001 |
| HIGH (P1) | 5 | F-002, F-003, F-004, F-005, F-006 |
| MED (P2) | 7 | F-007, F-008, F-009, F-010, F-011, F-012, F-013 |
| LOW (P3) | 13 | F-014 → F-026 |
| **Total** | **26** | |

## Score pondéré (méthode checklist)

| Dim | Note | Poids | Contribution |
|-----|------|-------|--------------|
| D1 PII bypass | 65 | 10% | 6.5 (F-007, F-008) |
| D2 Sandbox | 75 | 10% | 7.5 (F-014, F-019) |
| D3 HMAC chain | 50 | 10% | 5.0 (F-004, F-005, F-011) |
| D4 Code quality | 70 | 10% | 7.0 (F-015, F-016, F-017) |
| D5 Design patterns | 70 | 10% | 7.0 (F-018, F-019) |
| D6 Install/deps | 55 | 8% | 4.4 (F-009, F-012, F-020, F-021) |
| D7 Runtime/recovery | 60 | 8% | 4.8 (F-004, F-005) |
| D8 CI/CD | 30 | 9% | 2.7 (F-001 CRIT, F-022, F-023, F-024) |
| D9 Onboarding | 70 | 5% | 3.5 (F-026) |
| D10 End-user UX | 75 | 5% | 3.75 (F-009, F-012) |
| D11 Performance | 80 | 10% | 8.0 (F-017) |
| D12 Corpus | 50 | 5% | 2.5 (F-010) |
| **TOTAL** | | **100%** | **62.65 / 100** |

**Verdict** : 🟡 **62.65/100 — ACCEPTABLE mais avec 1 CRIT + 5 HIGH bloquants**

Le score n'est pas catastrophique (pas < 40), mais le **1 CRIT (F-001) + 5 HIGH** doivent être fixés avant tout tag v1.0.3.
