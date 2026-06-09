# Context Engineering Harness

> **Le harness open-source de référence pour optimiser le contexte des agents LLM en production.**

[![Charter](CHARTER.md)](CHARTER.md) [![Corpus](corpus/)](corpus/) [![Strategy](strategy/)](strategy/) [![Design](design/)](design/) [![Prototype](prototype/)](prototype/)

---

## TL;DR

L'ingénierie du contexte est **le job #1** des ingénieurs qui construisent des agents LLM (Cognition Labs, 2025). En juin 2026, **il n'existe pas de harness opinionated, outillé, et open-source** qui résout ce problème de manière systématique. Ce projet comble ce gap.

**Promesse v1.0** : **3-5× réduction du coût tokens** d'un agent en production, sans perte de qualité, par application systématique des 4 piliers (Write/Select/Compress/Isolate) et détection des 4 failure modes Drew Breunig.

## Quickstart

```bash
# Install (en cours de dev — POV v0)
git clone https://github.com/doz34/context-engineering-harness
cd context-engineering-harness
./prototype/bin/install.sh
./prototype/bin/ctxh measure --demo  # Token ledger live
```

## Architecture en 30 secondes

```
L0 Corpus (offline) → L1 Memory Blocks → L2 State → L3 Working Context → L4 LLM view
                                                                              ↓
                                              Hooks × Subagent Firewall × Token Ledger
                                              × Adversarial Gates × ACE Playbook
```

Voir [`design/00-architecture.md`](design/00-architecture.md) pour le détail.

## État d'avancement (2026-06-08)

| Phase | Statut | Livrable |
|-------|--------|----------|
| 0 Discovery | ✅ Validé | `CHARTER.md` + `corpus/` (40+ sources) |
| 1 Strategy | ✅ Validé | `strategy/00-strategy-2026-06-08.md` |
| 2 Design | ✅ Validé | `design/00-architecture.md` |
| 3 POV (Proof of Value) | 🟡 En cours | `prototype/` (token ledger + 1 hook) |
| 4 MVP | ⏸️ À démarrer | Harness installable, 5 hooks |
| 5 v1.0 | ⏸️ À démarrer | Production-ready, tests adversariaux |

## Sources primaires digérées (sélection)

- **Anthropic — Effective Harnesses for Long-Running Agents** (2025-11) — pattern initializer + coding agent
- **Anthropic — Code Execution with MCP** (2025-11) — jusqu'à **98.7% économie de tokens** via code-as-API
- **LangChain — Context Engineering for Agents** (2025-07) — taxonomie Write/Select/Compress/Isolate
- **Morph — Context Rot** (2026-03) — Chroma study, 18/18 modèles dégradés, 35min wall
- **Addy Osmani — Agent Harness Engineering** — "Agent = Model + Harness" (Viv Trivedy)
- **HumanLayer — Skill Issue** — Harness engineering as subset of context engineering
- **ACE — Agentic Context Engineering** (arXiv 2510.04618, ICLR 2026) — self-improving contexts
- **MemGPT / Letta** — virtual context management, memory blocks

Voir [`corpus/sources/INDEX.md`](corpus/sources/INDEX.md) pour les 40+ sources complètes.

## Comparaison

| Projet | Focus | Statut |
|--------|-------|--------|
| Claude Code | Production coding agent | Propriétaire, 5-stage progressive disclosure |
| LangGraph | Orchestration bas-niveau | Pas de token ledger natif |
| AORCHESTRA (arXiv 2602.03786) | Orchestrator search | Recherche, pas production |
| **CE-Harness (ce projet)** | **Context engineering opinionated** | **🟡 POV en dev** |

## Licence

MIT. Voir `LICENSE`.

## Contact

Discovery-orchestrator, 2026-06-08.
