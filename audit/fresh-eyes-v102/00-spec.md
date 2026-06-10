# Audit Fresh-Eyes CE-Harness v1.0.2 — Spec

> **Spec Kit phase**: /speckit.specify
> **Date**: 2026-06-10
> **Cible**: CE-Harness v1.0.2 (`6b052ea`, 23 modules, 318 tests, 10/10 swebok gates, 0 résidu)
> **Output**: rapport actionnable pour hypothétique v1.0.3

## 1. Vision de l'audit

Adopter le regard d'un **nouvel arrivant** qui découvre le projet sans biais d'auteur :
- Security researcher lisant le code en mode attaque (STRIDE, CWE, OWASP LLM Top 10)
- SRE qui doit déployer et opérer (P50/P99, dépendances, monitoring, recovery)
- Nouveau contributeur qui veut comprendre l'archi et contribuer (docs, onboarding, tests)
- User final qui installe et utilise (UX du `install.sh`, du `ctxh-demo`, du CLI)
- Adversaire qui essaie de bypass les 14 modules de sécurité (PII, sandbox, state HMAC, etc.)

Le but : **trouver ce que les 4 passes adversariales précédentes n'ont pas vu**, pas refaire le même audit.

## 2. Scope précis

### In scope
- **Code** : 23 modules `prototype/lib/*.py` (~5200 LOC)
- **Tests** : 25 fichiers `prototype/tests/*.py` (~318 tests)
- **CLI** : `prototype/bin/ctxh`, `ctxh-demo`, `install.sh`
- **Docs** : README, CHARTER, CLAUDE.md, `docs/*`, `corpus/`, `strategy/`, `design/`
- **CI/Config** : `.github/`, `pyproject.toml` (s'il existe), `bin/install.sh`
- **Security surface** : 14 modules de sécurité vs leurs attack surfaces réels

### Out of scope
- Refonte architecturale (Docker sandbox, multi-tenant PG) → roadmap 1.1.0
- Performance bench P50/P99 (pas de charge réelle) → roadmap 1.1.0
- Real Council Bridge `nexus-*` externes → roadmap 1.1.0
- i18n / traduction (déjà fait en v1.0.1)
- Replication exacte des 4 passes adversariales (déjà documentées audit/00-08)

## 3. Critères de succès

L'audit est **réussi** si on produit un artefact qui :

1. **Identifie ≥ 3 gaps réels** non couverts par les 4 passes précédentes (CRIT ou HIGH)
2. **Quantifie le risque** de chaque gap (CVSS-like : impact × probabilité × exploitabilité)
3. **Priorise** les fixes P0 (bloquant release) / P1 (semaine) / P2 (mois) / P3 (nice-to-have)
4. **Inclut des preuves** (fichier:ligne, PoC, output de commande)
5. **Propose des correctifs actionnables** (snippets de code, approche, tests à ajouter)
6. **Est re-runnable** : un 2ᵉ audit avec les mêmes reviewers + même code doit converger

## 4. Livrables

| # | Fichier | Contenu | Lignes estimées |
|---|---------|---------|------------------|
| 1 | `00-spec.md` (ce fichier) | Cadrage Spec Kit | ~80 |
| 2 | `01-checklist.md` | 8-12 dimensions qualité (HumanLayer 2026 + OWASP) | ~200 |
| 3 | `02-clarify.md` | 5-8 questions de cadrage AskUserQuestion | ~100 |
| 4 | `03-plan.md` | Méthodologie (4-5 angles d'attaque, agents, outils) | ~300 |
| 5 | `04-tasks.md` | Liste ordonnée des passes d'audit (10-15 tâches) | ~150 |
| 6 | `05-findings.md` | Findings bruts par dimension (10-30 findings) | ~500-1000 |
| 7 | `06-prioritized-actions.md` | Plan v1.0.3 priorisé (P0/P1/P2/P3) | ~200 |
| 8 | `07-report-final.md` | Synthèse exécutive + diff vs audit précédent | ~300 |

## 5. Garde-fous méthodologiques

- **Pas de faux positifs** : un finding = un PoC re-jouable. Si je ne peux pas le démontrer, je ne le liste pas.
- **Honnêteté sur les limites** : ce que l'audit ne couvre PAS (performance réelle, scalabilité, etc.)
- **Diff vs audit précédent** : pour chaque finding, dire pourquoi les 4 passes l'ont raté
- **Verdict ≠ auto-suffisant** : je peux trouver 0 CRIT, c'est un signal positif (pas un échec)
- **Adversarial via agents** : utiliser 3-4 subagents en parallèle (ciso/qa/architect/devops) + critic pour la synthèse

## 6. Liens

- Audit précédent final : `audit/05-final-zero-crit-2026-06-09.md` (0 résidu)
- 14 latent bugs : commit `6b052ea`
- Swebok state DB : `.swebok_state.db` (P10_RETIREMENT_ALL_GATES_PASSED)
- Roadmap 1.1.0 : `CHANGELOG.md` section Roadmap
