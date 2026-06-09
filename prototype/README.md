# CE-Harness — Proof of Value (POV)

> **Sprint S1** : Démontrer les 3 composants les plus disruptifs du harness, sur 1 use-case mesurable.
> **Date** : 2026-06-08
> **Critère PASS** : 3× économie tokens mesurée sur 1 cas d'usage réel.

## 3 composants démontrés

1. **Token Ledger** (`lib/token_ledger.py`) — mesurable, par composant, par phase
2. **Subagent Firewall** (`lib/subagent_firewall.py`) — isolation stricte, summary-only return
3. **Compaction ACE-style** (`lib/ace_compact.py`) — préserve les détails, dédup

## Use case de démo

**Tâche** : "Trouve toutes les fonctions qui appellent `parse_query` dans ce repo, et résume leur comportement."

**Baseline (sans harness)** :
- 1 seul agent, charge tous les fichiers = 80K tokens
- 12 tool calls en 1 session
- Tokens gaspillés : fichiers non-pertinents lus entièrement

**Avec CE-Harness** :
- Subagent firewall isole la recherche dans 1 fenêtre de 4K
- Lead agent reçoit un summary de 200 tokens
- Total : ~6K tokens (référence au repo + 1 brief subagent + summary reçu)
- **Ratio économie** : 80K → 6K = **13×**

## Lancer la démo

```bash
cd prototype
./bin/install.sh  # Setup minimal
./bin/ctxh-demo   # Run the demo
./bin/ctxh-ledger --dashboard  # Show token ledger
```

## Structure POV

```
prototype/
├── README.md (ce fichier)
├── bin/
│   ├── ctxh             # CLI principal
│   ├── ctxh-demo        # Script de démo
│   ├── ctxh-ledger      # Token ledger viewer
│   └── install.sh       # Install minimal
├── lib/
│   ├── __init__.py
│   ├── state.py         # SQLite state manager
│   ├── token_ledger.py  # Token tracking
│   ├── dsl.py           # KEY:VALUE;;KEY:VALUE parser
│   ├── subagent_firewall.py  # Subagent isolation
│   └── ace_compact.py   # ACE-style compaction
├── tests/
│   ├── test_state.py
│   ├── test_token_ledger.py
│   ├── test_dsl.py
│   ├── test_subagent_firewall.py
│   └── test_ace_compact.py
└── examples/
    └── sample_repo/     # Mini repo pour la démo
```

## Métriques à valider

| Métrique | Baseline | POV cible | Mesure |
|----------|----------|-----------|--------|
| Tokens par recherche | 80,000 | < 10,000 | ledger |
| Temps | ~8 min | < 2 min | timestamp |
| Précision (résultats pertinents) | 100% | 100% | test |
| Isolation (subagent context) | 0 (partagé) | 100% (isolé) | audit |
| Clarté du retour | dump | summary + refs | DSL parse |
