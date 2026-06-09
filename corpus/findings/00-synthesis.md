# Synthèse des findings — Corpus context engineering (2025-2026)

> **Date** : 2026-06-08
> **Sources** : 40+ (voir `../sources/INDEX.md`)
> **But** : Liste actionnable des insights qui doivent informer la conception du harness

---

## F1 — Le contexte est la ressource #1 (Cognition Labs, 2025)

> "Context engineering … is effectively the #1 job of engineers building AI agents."

**Implication** : Le harness doit traiter le contexte comme un **budget first-class** (mesure, allocation, plafond, journalisation). Ce n'est pas une optimisation, c'est la base.

## F2 — Plus de contexte ≠ meilleure performance (Chroma, 2025)

**Mesure** : 18/18 modèles frontier se dégradent à chaque incrément de longueur. Pas un seuil, une **dégradation continue**.

**Mécanismes** :
- Lost-in-the-middle : -30% accuracy positions 5-15/20 (Liu et al. Stanford/TACL 2024)
- Attention dilution : 100K tokens = 10B pairwise relationships
- Distractor interference : distracteurs topiquement proches amplifient l'hallucination

**Implication** : Gating par phase **obligatoire**. On ne peut pas "tout charger" même si la fenêtre le permet.

## F3 — 80% de la variance de performance = token usage (Anthropic, 2025-06)

**Mesure** : Sur BrowseComp, l'usage de tokens explique 80% de la variance de performance. 95% avec tool calls + model choice.

**Implication** : Le token budget par phase est un **proxy de qualité**, pas juste un cost-control. Mesurer = piloter.

## F4 — 35 min = mur universel (Morph, 2026-03)

**Mesure** : Au-delà de 35 min de tâche équivalente humaine, taux d'échec explose. Doubler la durée = quadrupler l'échec.

**Implication** : Chaque phase doit avoir un **budget temps dur**. Au-delà, forcer un checkpoint (compaction, fin de phase, escalation user).

## F5 — 60% du 1er tour agent = retrieval (Cognition/Devin, 2025)

**Mesure** : 60%+ du 1er tour passe en retrieval pur, pas en raisonnement.

**Implication** : Le **pre-hydrate** en début de phase est non-négociable. Le harness doit pré-compiler dans `state.db` ce que l'agent va chercher, sinon il perd 60% du budget de phase.

## F6 — Multi-agent = 15× chat, mais 90.2% gain (Anthropic, 2025-06)

**Mesure** : Multi-agent consomme 15× tokens d'un chat mais **+90.2% perf** vs single-agent Opus 4 sur BrowseComp.

**Trade-off** : Le gain n'est pas gratuit, il faut **justifier chaque fan-out**. Single-agent ≥ multi-agent à budget tokens égal (Tran & Kiela, arXiv 2604.02460, avril 2026).

**Implication** : Multi-agent **justifié seulement si** (a) parallèle read-heavy ou (b) disjoint tools. Sinon, single + compaction + sub-agent firewall suffit.

## F7 — Subagent firewall > prompt engineering (HumanLayer, 2026-03)

> "Sub-agents function as a 'context firewall' that ensures discrete tasks can run in isolated context windows so none of the intermediate noise accumulates in your parent thread."

**Implication** : Le sub-agent n'est pas qu'un outil de parallélisation, c'est un **mécanisme d'isolation** du contexte. C'est pourquoi Claude Code, Cursor, Windsurf convergent tous vers ce pattern.

## F8 — Code-as-API : 98.7% économie (Anthropic, 2025-11)

**Mesure** : Présenter les MCP tools comme des APIs de code (au lieu de tool calls directs) : **150K → 2K tokens**, économie 98.7% sur tools.

**Mécanismes** :
- Progressive disclosure : charger tools à la demande via filesystem
- Code filtering : 10K rows → 5 rows avant injection LLM
- Privacy : tokenize PII avant injection
- State persistence : variables, pas transcription

**Implication** : Le harness doit exposer **tous ses tools en code-API** par défaut, pas en tool-calling. Le LLM "navigue" le filesystem au lieu de "consulter" des JSON schemas.

## F9 — ACE : contextes self-improving (ICLR 2026)

**Paper** : arXiv 2510.04618, ACE = Agentic Context Engineering

**Mécanisme** : Le contexte est traité comme un **playbook evolving** au lieu d'un prompt figé. Processus = Generate → Reflect → Curation.

**Résultats** : +10.6% agents, +8.6% finance, **+1% en AppWorld** vs top production agent (avec un plus petit modèle open-source).

**Implication** : Le harness doit intégrer un **playbook engine** qui :
- Capture les succès/échecs
- Déduplique et versionne
- Évite "brevity bias" (résumer tue les détails) et "context collapse" (résumer itérativement efface)

## F10 — Le harness = la moitié du système (Viv Trivedy, 2025)

> "Agent = Model + Harness. If you're not the model, you're the harness."

**Citation Viv via Addy Osmani** : "A harness is every piece of code, configuration, and execution logic that isn't the model itself."

**Implication** : Tout ce qui n'est pas le LLM est le harness. C'est notre **scope**. Le harness n'est pas un wrapper, c'est l'environnement d'exécution.

## F11 — 4 leviers de customisation (Viv Trivedy, 2025)

1. **System prompt** (CLAUDE.md, AGENTS.md)
2. **Tools / MCPs** (et leur description)
3. **Context** (ce qui entre dans la fenêtre)
4. **Sub-agents** (avec leur isolation)

**+ 2 ajoutés par HumanLayer** :
5. **Hooks** (déterminisme, intégration)
6. **Skills** (progressive disclosure de connaissance)

**Implication** : 6 leviers à outiller dans le harness.

## F12 — Subagent brief = OBJECT/FORMAT/TOOLS/BOUND (Anthropic, 2025-06)

**Règle** : Brief vague "research X" = subagents dupliquent. Brief structuré 4 champs = division efficace.

**Implication** : Le harness doit imposer un **DSL de brief** pour chaque spawn. Notre format `KEY:VALUE;;KEY:VALUE` mappe naturellement les 4 champs.

## F13 — Tool result clearing > compaction (Anthropic, 2025-09)

**Pattern** : Les résultats d'anciens tool calls restent dans le contexte, polluent. Les effacer après consommation = compaction la plus sûre.

**Implication** : Le harness doit **effacer les tool results** après consommation par la phase suivante. Pas de rétention aveugle.

## F14 — Compaction trigger 60-70% > 95% (Morph, 2026-03)

**Constat** : Claude Code compacte à 95% (référence). Morph démontre que 95% = trop tard (la dégradation a déjà eu lieu). Cible = 60-70% du budget.

**Implication** : Notre seuil ANTI-ROT à 5 calls est trop agressif OU mal mesuré. Trigger cible = **60-70% du budget phase**, en tokens, pas en calls.

## F15 — LangChain 4 pillars = Write/Select/Compress/Isolate (2025-07)

Taxonomie qui domine l'industrie :

- **Write** : persister hors fenêtre (scratchpads, memories, fichiers)
- **Select** : ramener dans la fenêtre au bon moment (RAG, retrieval)
- **Compress** : réduire (summarization, trimming)
- **Isolate** : séparer (multi-agent, sandbox, state)

**Implication** : Le harness doit **outiller chacun des 4 piliers** avec des primitives natives.

## F16 — Drew Breunig 4 failure modes (2024-2025)

Modes de défaillance systémiques du contexte :

1. **Poisoning** : hallucination contamine le raisonnement aval
2. **Distraction** : surcharge fait diverger l'attention
3. **Confusion** : infos superflues diluent les signaux
4. **Clash** : infos contradictoires bloquent la décision

**Implication** : Le harness doit **auditer chaque phase** contre ces 4 modes (sub-section dans la spec). 4 gates adversariaux.

## F17 — CLAUDE.md doit être COURT (HumanLayer, 2026-03)

**Constat** : Le CLAUDE.md de HumanLayer = **<60 lignes**. ETH Zurich study (138 agentfiles) : human-written +4% seulement, agent-generated -20% (et coûte +20% tokens).

**Implication** : La règle "**pilot's checklist, not style guide**" : chaque ligne doit tracer à un échec passé. Pas de brainstorming, du ratchet.

## F18 — Les skills > system prompt (Anthropic, 2025-2026)

**Mécanisme** : Skills = progressive disclosure. Le `SKILL.md` est chargé à la demande quand le skill est activé, pas au boot.

**Implication** : Le harness doit supporter un **mécanisme de skills** (claude skills standard). Un skill = `SKILL.md` + ressources.

## F19 — MemGPT : virtual context management (arXiv 2310.08560)

**Métaphore** : LLM = CPU, context = RAM. Mémoire hiérarchique : main context (RAM) + external context (disk), avec paging explicite par function calls.

**Implication** : Le harness doit implémenter des **memory blocks addressables** (inspiré de Letta Memory Blocks), pas un blob de strings.

## F20 — Letta Memory Blocks (2024-2026)

**Pattern** : Structurer le contexte en **blocks fonctionnels discrets** (persona, facts, actions, etc.), chacun addressable individuellement.

**Implication** : L'état du harness = ensemble de **memory blocks typés**, modifiables individuellement, auditables.

## F21 — Compaction, pas résumé (Anthropic, 2025-09)

**Distinction** : Compaction = **préserver la structure ET les détails** (≠ summarization = perdre). 2 stratégies :
- **Recursive summarization** : résumer l'historique en arbre
- **Hierarchical summarization** : 2-tiers STM/LTM

**Implication** : Le harness doit supporter la compaction, pas seulement la summarization. Cible = préserver les **événements discrets** (décisions, gates), pas paraphraser.

## F22 — GEPA : prompt optimization par reflection (arXiv 2507.19457)

**Mécanisme** : Au lieu de RL ou grid search, GEPA utilise la **reflection LLM** pour proposer des améliorations Pareto-efficient. **+12% sur AIME-2025**, dépasse MIPROv2 de 10%.

**Implication** : Le harness peut intégrer un **optimiseur de prompts/playbooks** basé sur GEPA. Self-improvement continu.

## F23 — Subagent return = summary, pas transcript (Anthropic, 2025-06)

**Anti-pattern** : Subagent retourne tout son transcript au lead → "game of telephone" + tokens exponentiels.

**Best practice** : Subagent écrit dans un **artefact persistant** (filesystem, DB), passe juste une **référence + summary** au lead.

**Implication** : Le harness doit forcer un **return contract** strict : `<subagent-result ref="..." summary="..." artifacts="..."/>`.

## F24 — Long-running = initializer + coding agent (Anthropic, 2025-11)

**Pattern** : Pour tâches long-running, **deux agents** :
- **Initializer** : pose l'environnement (`init.sh`, `claude-progress.txt`, `feature_list.json` avec 200+ features, git initial commit)
- **Coding agent** : travaille incrémentalement, lit le progress, code 1 feature à la fois, finit par commit + log

**Implication** : Le harness doit supporter ce pattern (initialisation d'environnement) pour les projets long-running.

## F25 — Fail mode = agent "one-shot" l'app (Anthropic, 2025-11)

**Constat** : Sans scaffolding, l'agent tente de tout faire d'un coup → échoue en milieu de stream, laisse feature half-implemented.

**Solution** : Feature list JSON (passes: false initially) + 1 feature à la fois.

**Implication** : Le harness doit **décomposer en features atomiques** vérifiables.

## F26 — Test end-to-end = browser automation (Anthropic, 2025-11)

**Constat** : Sans browser test, l'agent "mark complete" sans vraiment tester.

**Solution** : Hook de vérification (Puppeteer MCP) qui force un test réel avant "passing".

**Implication** : Le harness doit supporter des **back-pressure mechanisms** (test/lint/build auto-run + error inject).

## F27 — Tool description = prompt-injection vector (HumanLayer, 2026-03)

**Risque** : Les descriptions de MCP tools sont injectées dans le system prompt. Un MCP malicieux = prompt-injection.

**Implication** : Le harness doit **auditer les MCP tools** (signing, allow-list, scope).

## F28 — Code execution vs tool calling (Anthropic, 2025-11)

**Comparaison** :
- Tool calling : schema JSON, intermediate results passent par contexte
- Code execution : agent écrit du code, sandbox exécute, résultats restent dans la sandbox

**Avantages code execution** :
- Privacy (PII jamais dans le contexte)
- State (variables, fichiers)
- Skills (l'agent construit sa propre toolbox)
- Performance (10,500 tok/s sur Fast Apply)

**Implication** : Le harness doit exposer **un environnement de code execution** (sandboxé) comme primitive centrale.

## F29 — FlashCompact (Morph, 2026) — prevention > treatment

**Composants** :
- **WarpGrep** : search isolé (0.73 F1, 3.8 steps), RL-trained
- **Fast Apply** : diffs compacts (10,500 tok/s)
- **Morph Compact** : verbatim cleanup (3,300+ tok/s)

**Impact** : +15.6% moins cher, +28% plus rapide, **chaque modèle frontier lifté à #1** sur SWE-Bench Pro.

**Implication** : Notre POV doit intégrer au moins un de ces patterns (WarpGrep-like search isolation).

## F30 — Coût cross-session (Mem0, 2026)

**Mesure** : 3-4× réduction possible via **architectures mémoire modernes** (episodic/semantic/procedural séparés).

**Implication** : Le harness doit supporter une **architecture mémoire multi-tier** (cf. L1 du modèle 5-couches).

---

## Synthèse pour le design

**Les 10 insights les plus structurants pour notre harness** :

1. **F3 (token = quality proxy)** → token ledger obligatoire, live, par composant
2. **F8 (code-as-API)** → primitives de code execution, pas de tool calling direct
3. **F9 (ACE self-improving)** → playbook engine, versioned, dedup
4. **F10 + F11 (harness = la moitié)** → 6 leviers outillés, opinionated
5. **F15 (4 pillars)** → Write/Select/Compress/Isolate comme primitives natives
6. **F16 (4 failure modes)** → 4 gates adversariaux par phase
7. **F19 + F20 (MemGPT + Memory Blocks)** → mémoire hiérarchique typée
8. **F7 + F23 (subagent firewall)** → isolation stricte, summary-only return
9. **F24 + F25 (long-running pattern)** → initializer + atomic features
10. **F4 (35min wall)** → budget temps dur, checkpoint obligatoire
