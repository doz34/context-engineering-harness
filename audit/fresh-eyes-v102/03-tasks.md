# Tasks — Audit Fresh-Eyes v1.0.2

> **Spec Kit phase**: /speckit.tasks
> **Date**: 2026-06-10
> **Source**: 02-plan.md

## Légende

- `[P0]` = bloquant release, fix immédiat
- `[P1]` = fix sous 1 semaine
- `[P2]` = fix sous 1 mois
- `[P3]` = nice-to-have, backlog
- ⬜ = todo, 🟡 = in-progress, ✅ = done

## Phase 0 — Setup

- [x] ⬜ T-001 Créer `audit/fresh-eyes-v102/` ✅
- [x] ⬜ T-002 Vérifier baseline 318/318 tests verts ✅ (318 passed in 6.93s)
- [x] ⬜ T-003 Backup pre-audit : `cp -r prototype /tmp/pre-audit-backup-$(date +%s)`
- [x] ⬜ T-004 Créer `.audit_state.json` (compteurs)

## Phase 1 — Inventory (Explore réel)

- [ ] ⬜ T-101 [P0 setup] Lancer `Explore` : inventaire LOC, imports, fonctions publiques
- [ ] ⬜ T-102 [P0 setup] Catalogue des `subprocess`/`os.system`/`eval`/`exec`/`pickle`
- [ ] ⬜ T-103 [P0 setup] Catalogue des `regex` (PII, validation, parsing)
- [ ] ⬜ T-104 [P0 setup] Catalogue des type hints + docstrings
- [ ] ⬜ T-105 [P0 setup] Coverage pytest par module (si dispo)

## Phase 2 — Passes adversariales

### A1 — Code quality / design (PRIORITÉ HAUTE)
- [ ] ⬜ T-201 [P?] Reviewer `architect` : dette technique (doublons, abstractions, complexité)
- [ ] ⬜ T-202 [P?] Reviewer `qa-lead` : type hints, docstrings, edge cases oubliés
- [ ] ⬜ T-203 [P?] Vérifier les 8 invariants sont enforceés par code (pas juste doc)
- [ ] ⬜ T-204 [P?] Mutation testing réel (pas sur fixtures)

### A2 — Operations / SRE (PRIORITÉ HAUTE)
- [ ] ⬜ T-301 [P?] Reviewer `devops-lead` : `install.sh` testé multi-OS (Debian/Ubuntu/macOS)
- [ ] ⬜ T-302 [P?] Reviewer `devops-lead` : stdlib-only claim (cryptography, pyyaml vraiment optionnels ?)
- [ ] ⬜ T-303 [P?] Reviewer `devops-lead` : crash recovery state DB
- [ ] ⬜ T-304 [P?] Reviewer `devops-lead` : logs structurés, health check, backup story
- [ ] ⬜ T-305 [P?] Reviewer `ciso` (secondary) : supply chain SBOM, pinned versions
- [ ] ⬜ T-306 [P?] GH Actions : SHA-256 pinning (dogfooding de `ci_cd_pinning.py`) ?
- [ ] ⬜ T-307 [P?] Matrix Python 3.10-3.13 ? Coverage report ? Lint ?

### A3 — Security (bypass réels)
- [ ] ⬜ T-401 [P?] Reviewer `ciso` : bypass PII tokenization (concat, zero-width, Unicode)
- [ ] ⬜ T-402 [P?] Reviewer `ciso` : bypass subagent sandbox (mro chain, pickle, exec)
- [ ] ⬜ T-403 [P?] Reviewer `ciso` : state HMAC chain (race, ordering, migration)
- [ ] ⬜ T-404 [P?] Reviewer `devops-lead` (secondary) : MCP trust pinning bypass
- [ ] ⬜ T-405 [P?] Reviewer `ciso` : secrets vault ACL edge cases

### A4 — UX (contributeur + end-user)
- [ ] ⬜ T-501 [P?] Reviewer `qa-lead` : onboarding 5 min (clone → first test)
- [ ] ⬜ T-502 [P?] Reviewer `qa-lead` : README quickstart copy-paste-able
- [ ] ⬜ T-503 [P?] Reviewer `qa-lead` : CLI `--help` + exit codes documentés
- [ ] ⬜ T-504 [P?] Reviewer `architect` (secondary) : ADRs, issue templates

### A5 — Performance
- [ ] ⬜ T-601 [P?] Reviewer `devops-lead` : sub-ms P99 mesuré ou aspirational ?
- [ ] ⬜ T-602 [P?] Reviewer `architect` (secondary) : regex compilation, SQLite config

### A6 — Testing
- [ ] ⬜ T-701 [P?] Reviewer `qa-lead` : mutation score réel
- [ ] ⬜ T-702 [P?] Reviewer `ciso` (secondary) : property-based tests edge cases

### A7 — Corpus & research
- [ ] ⬜ T-801 [P?] Reviewer `architect` : 40+ sources datées 2025-2026
- [ ] ⬜ T-802 [P?] Reviewer `qa-lead` (secondary) : 30 findings F1-F30 croisés avec invariants

## Phase 3 — Synthèse Nexus-Critic

- [ ] ⬜ T-901 Agrégation findings, déduplication, faux positifs
- [ ] ⬜ T-902 Calcul score pondéré
- [ ] ⬜ T-903 Production `06-prioritized-actions.md` (P0/P1/P2/P3)
- [ ] ⬜ T-904 Re-jeu de chaque PoC pour validation

## Phase 4 — Implémentation fixes P0+P1

- [ ] ⬜ T-F01 Fix #1 (à identifier)
- [ ] ⬜ T-F02 Fix #2
- [ ] ⬜ T-F03 Fix #N
- [ ] ⬜ T-F99 Re-run tests, doit rester 100% vert

## Phase 5 — PR + tag

- [ ] ⬜ T-PR1 Commit structuré (1-2 commits max)
- [ ] ⬜ T-PR2 Push origin
- [ ] ⬜ T-PR3 Créer tag v1.0.3
- [ ] ⬜ T-PR4 GitHub release avec notes

## Phase 6 — Documentation

- [ ] ⬜ T-D01 `07-report-final.md` synthèse exécutive
- [ ] ⬜ T-D02 Mémo `~/.claude/projects/-home-doz/memory/ce-harness-v103-audit-2026-06-10.md`
- [ ] ⬜ T-D03 Update `MEMORY.md` index
- [ ] ⬜ T-D04 Update `CHANGELOG.md` v1.0.3
- [ ] ⬜ T-D05 Update `CLAUDE.md` status (si changements)

## Total

- Setup : 4 tasks
- Inventory : 5 tasks
- Audit : 24 tasks
- Synthèse : 4 tasks
- Fixes : N tasks (à définir)
- PR : 4 tasks
- Doc : 5 tasks
- **Total estimé : ~45-50 tasks**

## Checkpoint décision

À T-903 (fin synthèse), point de décision :
- Si score ≥ 90 ET 0 P0 → demander à l'user si on fixe P1 quand même ou si on s'arrête au rapport
- Si 1-3 P0 → on fixe obligatoirement, PR garanti
- Si ≥ 4 P0 → peut indiquer un problème systémique, escalade user
