# Anti-patterns context engineering (2025-2026)

> 12 anti-patterns confirmés par les sources primaires, avec mitigation applicable au harness.

## AP1 — "50 subagents pour une question simple"

**Source** : Anthropic multi-agent research, 2025-06

**Symptôme** : Fan-out excessif, work duplication, exploration infinie, coût × 15 sans gain.

**Mitigation** : Règles d'effort-scaling explicites :
- 1 agent / 3-10 tool calls (fact-finding simple)
- 2-4 subagents (comparison)
- 10+ subagents (recherche complexe UNIQUEMENT)

**Notre implémentation** : `effort_scaling` enum dans le DSL de brief subagent.

## AP2 — "Brief vague : research X"

**Source** : Anthropic multi-agent research, 2025-06

**Symptôme** : Subagents dupliquent, gaps, échecs silencieux.

**Mitigation** : Brief structuré OBJECT/FORMAT/TOOLS/BOUND obligatoire.

**Notre implémentation** : Validator de brief dans `bin/ctxh-validate-brief.sh`.

## AP3 — "Replay du transcript à chaque wakeup"

**Source** : FlowHunt, 2026-04

**Symptôme** : Coût linéaire en turns × agents, supervisor paraphrase inutilement.

**Mitigation** :
- Résumé structuré via modèle cheap
- Cap full-fidelity sur sliding window
- Forward worker→user direct (économie 50%)

**Notre implémentation** : Hook de wakeup qui injecte un digest, jamais le transcript brut.

## AP4 — "Peer-to-peer entre subagents"

**Source** : FlowHunt, 2026-04

**Symptôme** : Explosion O(n²) des edges, drift de cohérence, "herding" (consensus prématuré).

**Mitigation** : **Pas de canal peer par défaut**. Tout via orchestrateur ou state DB.

**Notre implémentation** : Validation du canal de communication dans le firewall subagent.

## AP5 — "Compaction déclenchée trop tard (95%)"

**Source** : Morph, 2026-03

**Symptôme** : Compaction nettoie l'historique mais ne répare pas les sorties erronées déjà produites.

**Mitigation** : Compaction préventive à **60-70%** du budget, pas curative à 95%.

**Notre implémentation** : Token ledger avec triggers à 60/70/85/95%, CC obligatoire à 70%.

## AP6 — "Tool result clearing absent"

**Source** : Anthropic effective context engineering, 2025-09

**Symptôme** : Résultats d'anciens tool calls restent dans le contexte, polluent.

**Mitigation** : Effacer tool results après consommation. C'est la compaction la plus sûre.

**Notre implémentation** : Hook `post-tool-use` qui efface les tool results après consumption par la phase suivante.

## AP7 — "Contexte flood pour tâches courtes"

**Source** : Morph, 2026-03

**Symptôme** : Remplir le contexte "parce qu'on peut" avec 1M tokens de fenêtre, rot s'installe.

**Mitigation** : Ne charger que ce qui sert la phase courante. `hot_context` sélectif.

**Notre implémentation** : Token budget enforced, hard cap abort.

## AP8 — "Confondre taille fenêtre et capacité attention"

**Source** : Morph, 2026-03 + Vectara, 2025

**Symptôme** : "Mon modèle a 1M tokens, je peux tout charger". Réalité : rot à 50K, attention dilution quadratique.

**Mitigation** : Budget tokens ≠ budget d'attention. Mesurer la qualité par **outcome** (gate), pas par volume.

**Notre implémentation** : Dashboard par outcome (gate PASS/FAIL), pas par tokens chargés.

## AP9 — "Auto-generated CLAUDE.md"

**Source** : ETH Zurich study via HumanLayer, 2026-03

**Symptôme** : LLM génère un CLAUDE.md → -20% perf, +20% tokens.

**Mitigation** : **Human-curated** uniquement, sous 60 lignes, chaque ligne = un échec passé.

**Notre implémentation** : Linter `ctxh-lint-claudemd.sh` qui refuse les >60 lignes et les patterns non-tracés.

## AP10 — "Tool description = prompt-injection vector"

**Source** : HumanLayer, 2026-03

**Symptôme** : MCP server malicieux injecte via description de tool.

**Mitigation** :
- Allow-list de MCP servers
- Signing des descriptions
- Scope strict

**Notre implémentation** : `mcp-trust.json` avec signatures, refus par défaut.

## AP11 — "Subagent return = dump du transcript"

**Source** : Anthropic multi-agent, 2025-06

**Symptôme** : Subagent retourne tout, "game of telephone", tokens exponentiels.

**Mitigation** : Return contract strict : ref + summary + artifacts.

**Notre implémentation** : Validator `<subagent-result>` schema.

## AP12 — "Agent one-shot l'app"

**Source** : Anthropic effective harnesses, 2025-11

**Symptôme** : Tente tout faire d'un coup, échoue en milieu, laisse feature half-implemented.

**Mitigation** :
- Feature list JSON avec passes: false
- 1 feature à la fois
- Git commit + log à chaque fin

**Notre implémentation** : `feature_list.json` template + `init.sh` pattern.

## AP13 — "Lost-in-the-middle (positions 5-15)"

**Source** : Liu et al. Stanford/TACL 2024

**Symptôme** : -30% accuracy pour infos au milieu du contexte.

**Mitigation** : **Éléments critiques en tête/queue**, jamais au milieu.

**Notre implémentation** : Layout structuré : gate actif (tête) → contexte → findings adversariaux (queue).

## AP14 — "Compaction 'summarization' perd les détails"

**Source** : ACE paper, ICLR 2026

**Symptôme** : "Brevity bias" et "context collapse" — résumer itérativement efface.

**Mitigation** : Compaction = préserver structure + détails. ACE playbook pattern.

**Notre implémentation** : `ctxh-compact` qui préserve événements discrets (vs paraphrase).

## AP15 — "Multi-agent sans budget tokens explicite"

**Source** : Tran & Kiela, arXiv 2604.02460

**Symptôme** : Multi-agent ≤ single-agent à budget tokens égal.

**Mitigation** : Justifier chaque fan-out par (a) parallèle read-heavy ou (b) disjoint tools.

**Notre implémentation** : `ctxh-justify-fanout` qui demande la justification avant spawn.

## AP16 — "50% test suite run après chaque edit"

**Source** : HumanLayer, 2026-03

**Symptôme** : 4K lignes de passing tests flood le contexte, agent hallucine.

**Mitigation** : **Success is silent, failure is verbose**. Ne surface que les erreurs.

**Notre implémentation** : Hook de test qui swallow stdout sur PASS, ne surface que stderr + summary sur FAIL.

## AP17 — "MCP servers 'juste au cas où'"

**Source** : HumanLayer, 2026-03

**Symptôme** : Descriptions de tools polluent le system prompt, "dumb zone" rapide.

**Mitigation** : MCP server activé **uniquement si utilisé**. Sinon OFF.

**Notre implémentation** : Toggle MCP on/off selon usage, mesurer l'impact.

## AP18 — "Pas de budget temps par phase"

**Source** : Morph, 2026-03 (35min wall)

**Symptôme** : Phase qui dépasse 35 min = échec exponentiel.

**Mitigation** : Budget temps dur, checkpoint obligatoire au-delà, escalation user.

**Notre implémentation** : Timer par phase + soft/hard cap + circuit breaker.

## AP19 — "Contexte 'global' dans chaque phase"

**Source** : A1 (sequential-with-readonly), swebok context engineering

**Symptôme** : Phase X contient tout Y, viole A1, inflation tokens.

**Mitigation** : **Consultation envelope strict**. X reçoit une slice de Y, jamais Y entière.

**Notre implémentation** : `<consult phase="Y" query="..."/>` émet une slice token-budgeted.

## AP20 — "Tool definitions = 50% du contexte"

**Source** : Anthropic code execution, 2025-11

**Symptôme** : 50K tokens de tool definitions pour 5K de tâche utile.

**Mitigation** : Code-as-API (Cloudflare/Anthropic pattern), progressive disclosure via filesystem.

**Notre implémentation** : Tools exposés comme code dans `servers/` directory, pas dans system prompt.
