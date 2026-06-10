# Checklist qualité — Audit Fresh-Eyes v1.0.2

> **Spec Kit phase**: /speckit.checklist
> **Date**: 2026-06-10
> **But**: 12 dimensions qualité pour saturer la surface d'audit

## Méta-référence

Inspiré de :
- **HumanLayer 2026** : 7 patterns pour context engineering (invisible complexity, success-silent failures, etc.)
- **OWASP LLM Top 10** (2025) : LLM01 Prompt Injection, LLM02 Insecure Output, LLM06 Sensitive Info, LLM08 Vector Weakness, LLM10 Model Theft
- **CWE Top 25** : CWE-20 (input validation), CWE-79 (XSS), CWE-89 (SQLi), CWE-200 (info exposure), CWE-502 (deserialization), CWE-787 (OOB write), CWE-862 (missing authz)
- **STRIDE** : Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation
- **CIS Software Supply Chain Guide** : SBOM, signed releases, reproducible builds

## 12 dimensions (avec critères mesurables)

### D1 — Security: bypass PII tokenization
- [ ] 11 patterns regex couvrent-ils les cas réels (emails RFC 5322, NIR FR checksums, IBAN mod-97) ?
- [ ] HMAC-SHA256 déterministe : collision possible avec salt statique ?
- [ ] Round-trip tokenize→detokenize préserve-t-il les caractères Unicode/UTF-8 ?
- [ ] Bypass via concaténation (`j` + `ohn` + `@`) ou zero-width joiners ?
- [ ] Logs / error messages leakent-ils des PII non tokenizées ?

### D2 — Security: bypass subagent firewall & sandbox
- [ ] 25+ noms blacklistés + 54 builtins whitelistés : gaps ?
- [ ] AST `ast.walk` peut-il être trompé par `__class__.__mro__` chains ?
- [ ] `exec()` vs `eval()` vs `compile()` : tous bloqués ?
- [ ] Pickle / marshal / shelve bypass du sandbox ?
- [ ] Récursion infinie DoS via AST trop profond ?

### D3 — Security: state HMAC chain integrity
- [ ] HMAC chain vérifie-t-il l'ordre ou seulement le contenu ?
- [ ] Race conditions sur les writes concurrents (WAL mode) ?
- [ ] Backup/restore preserve-t-il la chaîne ?
- [ ] Migration v0→v1 cassée (pas de version dans la table) ?

### D4 — Code quality: dette technique
- [ ] 23 modules : y a-t-il des doublons (ex: validation YAML dans 3 fichiers) ?
- [ ] 14 modules sécurité : interface cohérente (même conventions, mêmes exceptions) ?
- [ ] Type hints complets ou HACK `# type: ignore` partout ?
- [ ] Docstrings présentes (22 modules CLAIMés) ?
- [ ] Mutation testing (mutation_testing.py existe) : score réel sur le code, pas sur des fixtures ?

### D5 — Code quality: design patterns
- [ ] 8 invariants CLAIMés sont-ils tous enforceés par code (pas juste documentés) ?
- [ ] 5 couches L0-L4 : dépendances circulaires ?
- [ ] DSL KEY:VALUE;;KEY:VALUE : parser récursif ou itératif ? edge cases ?
- [ ] Plugin system / extension points : zéro, comment ajouter un nouveau token pattern ?

### D6 — Operations: install & deps
- [ ] `install.sh` : testé sur 3 OS ? (Debian, Ubuntu, macOS, Windows-WSL)
- [ ] `cryptography` vraiment optionnelle (CLAIM `stdlib-only CI`) ? — test import sans
- [ ] `pyyaml` vraiment optionnelle ? — test import sans
- [ ] Pinned versions vs ranges : risque supply chain ?
- [ ] SBOM (CycloneDX/SPDX) présent ?

### D7 — Operations: runtime & recovery
- [ ] Crash recovery : state DB corrompue, comment recover ?
- [ ] Logs structurés (JSON) ou unstructured ? Rotation ?
- [ ] Health check endpoint / CLI command ? (`ctxh health` ?)
- [ ] Graceful degradation si module désactivé ?
- [ ] Backup/restore story ?

### D8 — Operations: CI/CD
- [ ] GitHub Actions workflow : pinning SHA-256 (dogfooding de `ci_cd_pinning.py`) ?
- [ ] Tests en matrix (Python 3.10, 3.11, 3.12, 3.13) ?
- [ ] Coverage report (pytest-cov) ? actuel ?
- [ ] Lint (ruff/black/mypy) ?
- [ ] Dependabot / Renovate config ?

### D9 — UX: onboarding nouveau contributeur
- [ ] `git clone` → premier test qui passe en <5 min ?
- [ ] `README.md` quickstart copy-paste-able ?
- [ ] Issue templates + PR template présents ? (`.github/`)
- [ ] Premier issue "good first issue" tagué ?
- [ ] Architecture decision records (ADRs) ?

### D10 — UX: end-user (install + use)
- [ ] `bin/ctxh-demo` : vraiment end-to-end ou simulé ?
- [ ] CLI : `--help` complet ? Exit codes documentés ?
- [ ] Error messages actionnables ou cryptic ?
- [ ] Troubleshooting FAQ couvre les 10 erreurs les plus probables ?
- [ ] i18n : FR/EN switch ou EN only assumé ?

### D11 — Performance: claims vs réalité
- [ ] "sub-millisecond P99 added by harness" : mesuré ou aspirational ?
- [ ] "10.8× token economy" : re-mesurable ou one-shot ?
- [ ] "28.6× subagent return compression" : démo reproductible ?
- [ ] SQLite WAL : configuré optimalement (mmap, cache_size) ?
- [ ] Regex compilation : `@lru_cache` ou recompile à chaque appel ?

### D12 — Corpus & research foundation
- [ ] 40+ sources : datées 2025-2026 ? Obsolète ?
- [ ] 30 findings F1-F30 : croisés avec les 8 invariants ?
- [ ] 20 anti-patterns : mitigations encodées dans le code ou juste documentées ?
- [ ] INDEX.md navigable ?
- [ ] Sources PDF/books (Stwebok, ACE paper) citées correctement ?

## Pondération pour scoring final

| Dim | Poids | Justification |
|-----|-------|---------------|
| D1-D3 (Security) | 30% | 14 modules sécu, surface d'attaque critique |
| D4-D5 (Code quality) | 20% | Maintenabilité long-terme |
| D6-D8 (Ops) | 25% | Production-readiness réel |
| D9-D10 (UX) | 10% | Adoption |
| D11 (Perf) | 10% | Crédibilité des claims |
| D12 (Corpus) | 5% | Foundation, faible risque immédiat |

**Score** = Σ (note_dim × poids) où note_dim ∈ [0, 100]
- ≥ 90 : EXCELLENT (aucun fix prioritaire)
- 75-89 : BON (P3-P4 uniquement)
- 60-74 : ACCEPTABLE (P2 possible)
- 40-59 : INSUFFISANT (P1 obligatoire)
- < 40 : BLOQUANT (P0 release blocker)

## Sortie attendue

Chaque dimension produit :
- ✅ / ❌ par sous-critère
- 0-N findings avec severité (CRIT/HIGH/MED/LOW)
- Preuve (fichier:ligne, commande, output)
- Suggestion de fix (snippet ou approche)

→ Total attendu : 15-30 findings sur 12 dimensions (~1-2 par dimension en moyenne).
