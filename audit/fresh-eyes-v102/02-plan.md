# Plan d'audit — Fresh-Eyes v1.0.2

> **Spec Kit phase**: /speckit.plan
> **Date**: 2026-06-10
> **Inputs**: 00-spec.md, 01-checklist.md, 4 réponses Clarify
> **Output**: méthodologie, agents, outils, séquencement

## 1. Architecture de la review

### Mix reviewers (réponse Clarify Q3)

**4 reviewers simulés rigoureusement** (style swebok Mode 2 S2) :
- `ciso` (RED) — security researcher, mindset attaquant, OWASP LLM Top 10
- `qa-lead` (BLUE) — quality advocate, mutation testing, edge cases
- `architect` (BLUE) — design patterns, invariants, dette technique
- `devops-lead` (RED/BLUE) — SRE, supply chain, ops, recovery

**1 reviewer réel** :
- `Explore` (agent natif Claude Code) — inventaire factuel du code, grep ciblés, recherche de patterns

**1 synthesize critic** (post-passe) :
- Nexus-Critic simulé — agrège les findings, identifie les faux positifs, calcule le score final, propose les correctifs actionnables

### Hypothèses clés

- Reviewers simulés = même méthodologie que S2 du swebok harness (validée, honnête)
- Limitation : pas de `nexus-ciso`/`nexus-qa-lead` externes (subagent_type non enregistrés localement)
- Mitigation : `Explore` réel pour les inventaires factuels qui ne nécessitent pas d'opinion

## 2. 7 angles d'attaque (réponse Clarify Q2 — 2 prioritaires signalés)

| # | Angle | Dimensions checklist | Priorité | Effort |
|---|-------|----------------------|----------|--------|
| A1 | **Code quality / design** | D4, D5 | 🔴 HAUTE | 1.5h |
| A2 | **Operations / SRE** | D6, D7, D8 | 🔴 HAUTE | 1.5h |
| A3 | Security (bypass réels) | D1, D2, D3 | 🟡 STANDARD | 1.5h |
| A4 | UX (contributeur + end-user) | D9, D10 | 🟡 STANDARD | 1h |
| A5 | Performance (claims) | D11 | 🟡 STANDARD | 0.5h |
| A6 | Testing (mutation, edge) | D4 partiel | 🟡 STANDARD | 0.5h |
| A7 | Corpus & research | D12 | 🟢 NICE | 0.5h |
| +A | Inventory (Explore réel) | Prérequis | ⚪ SETUP | 0.5h |

**Effort total estimé** : 7.5h (compatible 1-2 jours en temps réel avec pauses/relectures)

## 3. Séquencement temporel

### Phase 0 — Setup (15 min)
- Créer audit/fresh-eyes-v102/ ✅
- Initialiser `.audit_state.json` (compteur findings, timestamps)
- Vérifier tests passent (baseline 318/318) ✅ déjà vérifié
- Backup pre-audit : `cp -r prototype /tmp/prototype-pre-audit-backup-$(date +%s)`

### Phase 1 — Inventory factuel via Explore (30 min)
**Agent réel** : `Explore` (subagent_type natif)
**Livrable** : `inventory.md` avec :
- LOC par module
- Imports / dépendances inter-modules
- Fonctions publiques par module
- Patterns regex (catégorisation)
- Appels `subprocess`, `os.system`, `eval`, `exec`, `pickle`
- Présence de `type hints`, `docstrings`, `tests`
- Couverture pytest par module (via `coverage` si dispo)

### Phase 2 — Passes adversariales (5h)
**Pour chaque angle A1-A7** :
1. **Reviewer principal** (1 simulé) : 80% findings
2. **Reviewer secondaire** (1 simulé) : 20% findings additionnels
3. **Explore réel** (si nécessaire) : grep ciblés
4. **Output** : section dédiée dans `05-findings.md` avec :
   - Findings par severity (CRIT/HIGH/MED/LOW)
   - Preuve : `fichier:ligne` + PoC si possible
   - Pourquoi les 4 passes précédentes ont raté

**Mapping reviewer ↔ angle** :
- A1 Code quality → `architect` (primary) + `qa-lead` (secondary)
- A2 Operations → `devops-lead` (primary) + `ciso` (secondary, supply chain)
- A3 Security → `ciso` (primary) + `devops-lead` (secondary)
- A4 UX → `qa-lead` (primary) + `architect` (secondary)
- A5 Performance → `devops-lead` (primary) + `architect` (secondary)
- A6 Testing → `qa-lead` (primary) + `ciso` (secondary, mutation = attack)
- A7 Corpus → `architect` (primary) + `qa-lead` (secondary)

### Phase 3 — Synthèse Nexus-Critic (30 min)
- Agrégation findings, déduplication
- Vérification qu'aucun finding n'est un faux positif (re-jouer chaque PoC)
- Calcul du score pondéré (méthode checklist)
- Production `06-prioritized-actions.md` (P0/P1/P2/P3)

### Phase 4 — Implémentation fixes P0+P1 (2-3h)
- Regroupement en batchs logiques (security, ops, code quality)
- Chaque fix = code + test + CHANGELOG
- Tests doivent rester 100% pass

### Phase 5 — PR + tag v1.0.3 (30 min)
- Commit structuré (1 ou 2 commits max)
- Push vers origin
- Créer tag v1.0.3
- Publication GitHub release avec notes

### Phase 6 — Documentation finale (30 min)
- `07-report-final.md` (synthèse exécutive)
- Mémo à `/home/doz/.claude/projects/-home-doz/memory/`
- Update MEMORY.md du projet

## 4. Outils & commandes

### Lecture & analyse
```bash
# Inventory
find prototype/lib -name "*.py" -exec wc -l {} \;
grep -rE "import|from" prototype/lib --include="*.py" | sort -u
grep -rE "subprocess|os\.system|eval|exec|pickle|marshal" prototype/lib --include="*.py"

# Coverage (si pytest-cov dispo)
cd prototype && python3 -m pytest tests/ --cov=lib --cov-report=term-missing

# Mutation testing
cd prototype && python3 -m pytest tests/test_mutation_testing.py -v
```

### Vérification sécurité supply chain
```bash
# Fichiers lockés ?
ls prototype/*.lock prototype/requirements*.txt 2>/dev/null
# Imports stdlib only ?
python3 -c "import sys; sys.path.insert(0, 'prototype'); import lib; print('OK')" 2>&1
```

### Tests
```bash
cd prototype && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

## 5. Garde-fous

1. **Pas de fix pendant l'audit** : on collecte les findings, on score, PUIS on fixe (Phase 4)
2. **Tests verts avant fix** : si un fix casse un test, on documente, on ne commit pas
3. **Preuve pour chaque finding** : pas de finding sans `fichier:ligne` ou commande reproductible
4. **Honnêteté sur les limites** : ce qu'on n'a PAS vérifié est documenté explicitement
5. **Re-runnabilité** : `bash audit/fresh-eyes-v102/run-audit.sh` doit pouvoir re-exécuter l'audit

## 6. Risques du plan

| Risque | Probabilité | Mitigation |
|--------|-------------|------------|
| 0 finding (audit vide) | Faible | Si <5 findings, l'audit est superficiel, on continue à creuser |
| Faux positifs | Moyenne | Re-jouer chaque PoC, Nexus-Critic déduplique |
| Effort déborde (>8h) | Moyenne | P0+P1 seulement, P2/P3 dans rapport pour v1.0.4 |
| Conflit avec roadmap 1.1.0 | Faible | Roadmap = features, audit = qualité de l'existant |
| Tests cassent pendant fix | Moyenne | Rollback immédiat, fix en PR séparé |

## 7. Critères d'arrêt

On s'arrête quand :
- ✅ 7 angles couverts (même superficiellement)
- ✅ ≥ 15 findings collectés OU justification documentée si moins
- ✅ Score final calculé
- ✅ P0+P1 fixés + tests verts + tag v1.0.3
- ✅ Mémo persisté en mémoire long-terme
