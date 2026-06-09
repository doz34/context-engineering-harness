# Context Engineering Harness — Charter

> **Vision** : Construire le harness open-source de référence pour l'**ingénierie du contexte** des agents LLM, indispensable à toute équipe qui déploie des agents en production.

## Pourquoi ce projet existe

L'état de l'art 2026 est sans ambiguïté :

1. **Le contexte est la ressource #1** des agents LLM (Cognition Labs : "Context engineering is the #1 job of engineers building AI agents").
2. **Plus de contexte ≠ meilleure performance** : Chroma a testé 18 modèles frontier, TOUS se dégradent à chaque incrément (Context Rot).
3. **80% de la variance de performance** d'un agent = son usage de tokens (Anthropic BrowseComp).
4. **35 minutes** = mur au-delà duquel le taux d'échec explose (×4 si durée ×2).
5. **Le modèle est l'input, le harness est le produit** (Viv Trivedy / Addy Osmani) : "Agent = Model + Harness. If you're not the model, you're the harness."

Pourtant, en juin 2026, **il n'existe pas de harness open-source complet, opinionated, et outillé pour l'ingénierie du contexte**. Les options actuelles :

| Outil | Force | Faiblesse |
|-------|-------|-----------|
| Claude Code | Production-grade, 5-stage progressive disclosure | Propriétaire, pas de hooks arbitrables |
| LangGraph | Flexible, 4-pillars context engineering | Bas-niveau, pas de token ledger natif |
| AORCHESTRA (arXiv 2602.03786) | +16% GAIA/SWE-Bench | Recherche, pas production |
| ACE (arXiv 2510.04618) | Self-improving contexts | Pas de hooks, pas de state machine |
| swebok-v4-harness (interne) | SDLC enforcement | Pas de focus context engineering |

**Notre positionnement** : un harness **opinionated** (qui prend des décisions fortes) + **outillé** (CLI, hooks, dashboards, telemetry) + **agnostique** (fonctionne avec n'importe quel LLM via API standard) + **disruptif** (intègre les patterns récents qui ne sont pas encore mainstream : ACE self-improvement, MemGPT virtual context, code-as-API, FlashCompact).

## Mission

Réduire de **3-5×** le coût en tokens d'un agent en production, **sans dégradation de qualité**, en appliquant systématiquement les 4 piliers de l'ingénierie du contexte (Write/Select/Compress/Isolate) + les 4 failure modes Drew Breunig comme gates de qualité.

## Non-objectifs (volontairement)

- ❌ Construire un orchestrateur agent généraliste (LangGraph, AORCHESTRA le font)
- ❌ Remplacer Claude Code ou Codex (intégrer en tant que plugin, si pertinent)
- ❌ Coder un nouveau modèle (harness = tout SAUF le modèle)
- ❌ Couvrir tous les cas d'usage agent (focus : production, multi-session, long-horizon)

## Principes fondateurs

1. **Le contexte est un budget, pas un disque dur** — chaque token a un coût caché (attention, latence, $).
2. **Mesurer avant d'optimiser** — token ledger obligatoire, dashboards par défaut.
3. **L'isolation vaut mieux que la compaction** — subagent firewall > résumé intelligent.
4. **Le harness encode des hypothèses** — chaque composant répond à "le modèle ne peut pas faire X tout seul".
5. **Self-improving par défaut** — ACE playbook en arrière-plan, jamais statique.
6. **Audit chain obligatoire** — toute décision est loggée, hashée, rejouable.

## Métriques de succès (cible v1.0)

| Métrique | Baseline (sans harness) | Cible v1.0 | Source de vérité |
|----------|-------------------------|------------|------------------|
| Coût par tâche agent | 1× | **0.2-0.3× (3-5× moins)** | Token ledger |
| Latence P50 tâche | 1× | **0.6-0.8×** | Hooks + telemetry |
| Taux de "context rot" (régressions tardives) | ~35% | **<5%** | Benchmark interne |
| Coût d'isolation (overhead subagent) | 15× chat | **2-3×** (code-as-API) | Anthropic MCP pattern |
| Taux d'adversarial leakage (T1/T2/T3 collision) | ~15% | **<1%** | Adversarial gates |
| Mémoire de l'agent (cross-session) | 0% | **100%** (MemGPT blocks) | Playbook ACE |

## Architecture (vue macro)

```
┌─────────────────────────────────────────────────────────────┐
│ L0  Corpus (offline, jamais injecté en bloc)                │
│    → skills/, playbooks/, distilled knowledge               │
├─────────────────────────────────────────────────────────────┤
│ L1  Memory Blocks (MemGPT-style, addressable)               │
│    → episodic / semantic / procedural / scratchpad          │
├─────────────────────────────────────────────────────────────┤
│ L2  Phase / Session State (typed, queryable)                │
│    → SQLite state, JSON-schema-validated                    │
├─────────────────────────────────────────────────────────────┤
│ L3  Working Context (token-budgeted, structured)            │
│    → 4-pillars Write/Select/Compress/Isolate               │
├─────────────────────────────────────────────────────────────┤
│ L4  Immediate LLM view (curated, head/tail-protected)       │
│    → critical elements in head/tail, never middle           │
└─────────────────────────────────────────────────────────────┘
        ↓ enforced by
┌─────────────────────────────────────────────────────────────┐
│ Hooks layer : 5 lifecycle events × 5 archetypes             │
│ Subagent firewall : isolation, summary-only return          │
│ Token ledger : live, per-component, per-phase               │
│ Adversarial gates : T1/T2/T3, Drew Breunig 4-failure-mode  │
│ ACE playbook : self-improving, deduplicated, versioned      │
└─────────────────────────────────────────────────────────────┘
```

## Roadmap

| Phase | Cible | Critère PASS |
|-------|-------|--------------|
| **0 — Discovery** | ✅ Corpus + Charter | Ce document |
| **1 — Strategy** | Stratégie consolidée 2026-06-08 | 4-pillars + 4-failure-modes + token budgets |
| **2 — Design** | Architecture 5-couches + DSL | Spécification validée |
| **3 — POV (Proof of Value)** | Prototype démontrable | Token ledger live + 1 cas d'usage end-to-end |
| **4 — MVP** | Harness installable | 5 hooks + state machine + token ledger |
| **5 — v1.0** | Production-ready | 3-5× économie mesurée + tests adversariaux PASS |

## Liens

- Corpus fondateur : `corpus/sources/` (extraits WebFetch + URLs)
- Stratégie : `strategy/00-strategy-2026-06-08.md`
- Design : `design/00-architecture.md`
- Prototype : `prototype/`

*Charter rédigé 2026-06-08 par discovery-orchestrator. Tout feedback bienvenu.*
