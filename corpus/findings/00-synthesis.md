# Synthesis of findings — Context engineering corpus (2025-2026)

> **Date**: 2026-06-08
> **Sources**: 40+ (see `../sources/INDEX.md`)
> **Goal**: Actionable list of insights that must inform the design of the harness

---

## F1 — Context is the #1 resource (Cognition Labs, 2025)

> "Context engineering … is effectively the #1 job of engineers building AI agents."

**Implication**: The harness must treat the context window as a **budget first-class** (measurement, allocation, ceiling, logging). This is not an optimization, it is the foundation.

## F2 — More context ≠ better performance (Chroma, 2025)

**Measurement**: 18/18 frontier models degrade with every length increment. Not a threshold, **continuous degradation**.

**Mechanisms**:
- Lost-in-the-middle: -30% accuracy at positions 5-15 (Liu et al., Stanford/TACL 2024)
- Attention dilution: 100K tokens = 10B pairwise relationships
- Distractor interference: topically similar but irrelevant content amplifies hallucinations

**Implication**: Gating by phase **mandatory**. One cannot "load everything" even if the window allows it.

## F3 — 80% of performance variance = token usage (Anthropic, 2025-06)

**Measurement**: On BrowseComp, token usage explains 80% of performance variance. 95% with tool calls + model choice.

**Implication**: The token budget per phase is a **quality proxy**, not just cost-control. Measure = steer.

## F4 — 35 min = universal wall (Morph, 2026-03)

**Measurement**: Beyond ~35 min of human-equivalent task time, failure rate explodes. Doubling duration = quadrupling failure.

**Implication**: Each phase Nexus must have a **hard time budget**. Beyond, force a checkpoint (compaction, end of phase, escalation user).

## F5 — 60% of first agent turn = retrieval (Cognition/Devin, 2025)

**Measurement**: 60%+ of first turn passes in pure retrieval, not reasoning.

**Implication**: The **pre-hydrate** at phase start is non-negotiable. The harness must pre-compile in `state.db` what the agent will look for, otherwise it loses 60% of the phase budget.

## F6 — Multi-agent = 15× chat, but 90.2% gain (Anthropic, 2025-06)

**Measurement**: Multi-agent consumes 15× tokens of a chat but **+90.2% perf** vs single-agent Opus 4 on BrowseComp.

**Trade-off**: The gain is not free, it must be **justified**. Single-agent ≥ multi-agent at equal token budget (Tran & Kiela, arXiv 2604.02460, April 2026).

**Implication**: Multi-agent **justified only if** (a) read-heavy parallel or (b) disjoint tools. Otherwise, single + compaction + sub-agent firewall suffice.

## F7 — Subagent firewall > prompt engineering (HumanLayer, 2026-03)

> "Sub-agents function as a 'context firewall' that ensures discrete tasks can run in isolated context windows so none of the intermediate noise accumulates in your parent thread which is responsible for orchestration, and you can maintain coherency for much, much longer."

**Implication**: The sub-agent is not just a parallelization tool, it is an **isolation mechanism** of the context. This is why Claude Code, Cursor, Windsurf all converge on this pattern.

## F8 — Code-as-API: 98.7% economy (Anthropic, 2025-11)

**Measurement**: Presenting the MCP tools as code APIs (instead of tool calling JSON): **150K → 2K tokens**, **98.7% economy**.

**Mechanisms**:
- Progressive disclosure: load tools on demand via filesystem
- Code filtering: 10K rows → 5 rows before LLM injection
- Privacy: tokenize PII before injection
- State persistence: variables, not transcription

**Implication**: The harness must expose **all its tools in code-as-API** by default, not in tool-calling. The LLM "navigates" the filesystem instead of "querying" JSON schemas.

## F9 — ACE: self-improving contexts (ICLR 2026)

**Paper**: arXiv 2510.04618, ACE = Agentic Context Engineering

**Mechanism**: The context is treated as an **evolving playbook** instead of a fixed prompt. Process = Generate → Reflect → Curation.

**Results**: +10.6% agents, +8.6% finance, **+1% on AppWorld** vs top production agent (with a smaller open-source model).

**Implication**: The harness must integrate a **playbook engine** that:
- Captures successes/failures
- Deduplicates and versions
- Avoids "brevity bias" (summarizing kills details) and "context collapse" (iterative summarizing erases)

## F10 — The harness = half the system (Viv Trivedy, 2025)

> "Agent = Model + Harness. If you're not the model, you're the harness."

**Citation Viv via Addy Osmani**: "A harness is every piece of code, configuration, and execution logic that isn't the model itself."

**Implication**: Everything that is not the LLM is the harness. This is our **scope**. The harness is not a wrapper, it is the execution environment.

## F11 — 4 customization levers (Viv Trivedy, 2025)

1. **System prompt** (CLAUDE.md, AGENTS.md)
2. **Tools / MCPs** (and their description)
3. **Context** (what enters the window)
4. **Sub-agents** (with their isolation)

**+ 2 added by HumanLayer**:
5. **Hooks** (determinism, integration)
6. **Skills** (progressive disclosure of knowledge)

**Implication**: 6 levers to tool in the harness.

## F12 — Subagent brief = OBJECT/FORMAT/TOOLS/BOUND (Anthropic, 2025-06)

**Rule**: Vague brief "research X" = subagents duplicate. Structured brief 4 fields = efficient division.

**Implication**: The harness must impose a **brief DSL** for each spawn. Our `KEY:VALUE;;KEY:VALUE` format maps naturally the 4 fields.

## F13 — Tool result clearing > compaction (Anthropic, 2025-09)

**Pattern**: Results of old tool calls remain in the context, polluting. Clearing them after consumption = safest compaction.

**Implication**: The harness must **clear tool results** after consumption by the next phase. No blind retention.

## F14 — Compaction trigger 60-70% > 95% (Morph, 2026-03)

**Finding**: Claude Code compacts at 95% (reference). Morph demonstrates that 95% = too late (degradation has already occurred). Target = 60-70% of the budget.

**Implication**: Our threshold ANTI-ROT at 5 calls is too aggressive OR poorly measured. Trigger target = **60-70% of the budget phase**, in tokens, not in calls.

## F15 — LangChain 4 pillars = Write/Select/Compress/Isolate (2025-07)

Taxonomy that dominates the industry:

- **Write** — persist outside the window (scratchpads, memories, files)
- **Select** — pull only the relevant context into the window at each step
- **Compress** — reduce token count while preserving structure and details
- **Isolate** — separate subagents with disjoint contexts

**Implication**: The harness must **tool each of the 4 pillars** with native primitives.

## F16 — Drew Breunig 4 failure modes (2024-2025)

Systemic failure modes of the context:

1. **Poisoning** — hallucination contaminates downstream reasoning
2. **Distraction** — overload diverts attention
3. **Confusion** — superfluous information dilutes the important signals
4. **Clash** — contradictory information blocks the decision

**Implication**: The harness must **audit each phase** against these 4 modes (sub-section in the spec). 4 adversarial gates.

## F17 — CLAUDE.md must be SHORT (HumanLayer, 2026-03)

**Finding**: The CLAUDE.md of HumanLayer = **< 60 lines**. ETH Zurich study (138 agentfiles): human-written +4% only, agent-generated -20% (and +20% tokens).

**Implication**: The rule "**pilot's checklist, not style guide**": each line must trace to a past failure. No brainstorming, ratchet only.

## F18 — Skills > system prompt (Anthropic, 2025-2026)

**Mechanism**: Skills = progressive disclosure. The `SKILL.md` is loaded on demand when the skill is activated, not at boot.

**Implication**: The harness must support a **skills mechanism** (claude skills standard). A skill = `SKILL.md` + resources.

## F19 — MemGPT: virtual context management (arXiv 2310.08560)

**Metaphor**: LLM = CPU, context = RAM. Hierarchical memory: main context (RAM) + external context (disk), with paging explicit by function calls.

**Implication**: The harness must implement **addressable memory blocks** (inspired by Letta Memory Blocks), not a blob of strings.

## F20 — Letta Memory Blocks (2024-2026)

**Pattern**: Structure the context into **discrete functional blocks** (persona, facts, actions, etc.), each individually addressable.

**Implication**: The state of the harness = set of **typed memory blocks**, individually modifiable, auditable.

## F21 — Compaction, not summarization (Anthropic, 2025-09)

**Distinction**: Compaction = **preserve structure AND details** (≠ summarization = lose). 2 strategies:
- **Recursive summarization**: summarize the history into a tree
- **Hierarchical summarization**: 2-tier STM/LTM

**Implication**: The harness must support compaction, not only summarization. Target = preserve **discrete events** (decisions, gates), not paraphrase.

## F22 — GEPA: prompt optimization by reflection (arXiv 2507.19457)

**Mechanism**: Instead of RL or grid search, GEPA uses **LLM reflection** to propose improvements Pareto-efficient. **+12% on AIME-2025**, outperforms MIPROv2 by 10%.

**Implication**: The harness can integrate a **prompts/playbooks optimizer** based on GEPA. Continuous self-improvement.

## F23 — Subagent return = summary, not transcript (Anthropic, 2025-06)

**Anti-pattern**: Subagent returns all its transcript to the lead → "game of telephone" + exponential tokens.

**Best practice**: Subagent writes to a **persistent artifact** (filesystem, DB), passes just a **reference + summary** to the lead.

**Implication**: The harness must force a **strict return contract**: `<subagent-result ref="..." summary="..." artifacts="..."/>`.

## F24 — Long-running = initializer + coding agent (Anthropic, 2025-11)

**Pattern**: For long-running tasks, **two agents**:
- **Initializer**: sets up the environment (`init.sh`, `claude-progress.txt`, `feature_list.json` with 200+ features, initial git commit)
- **Coding agent**: works incrementally, reads the progress, codes 1 feature at a time, ends with commit + log

**Implication**: The harness must support this pattern (initialization of environment) for long-running projects.

## F25 — Fail mode = agent "one-shot" the app (Anthropic, 2025-11)

**Finding**: Without scaffolding, the agent tries to do everything at once → fails mid-stream, leaves feature half-implemented.

**Solution**: Feature list JSON (passes: false initially) + 1 feature at a time.

**Implication**: The harness must **decompose into atomic, verifiable features**.

## F26 — Test end-to-end = browser automation (Anthropic, 2025-11)

**Finding**: Without browser test, the agent "marks complete" without really testing.

**Solution**: Verification hook (Puppeteer MCP) that forces a real test before "passing".

**Implication**: The harness must support **back-pressure mechanisms** (test/lint/build auto-run + error inject).

## F27 — Tool description = prompt-injection vector (HumanLayer, 2026-03)

**Risk**: MCP tool descriptions are injected in the system prompt. A malicious MCP = prompt-injection.

**Implication**: The harness must **audit MCP tools** (signing, allow-list, scope).

## F28 — Code execution vs tool calling (Anthropic, 2025-11)

**Comparison**:
- Tool calling: JSON schema, intermediate results pass through context
- Code execution: agent writes code, sandbox executes, results stay in sandbox

**Advantages of code execution**:
- Privacy (PII never in context)
- State (variables, files)
- Skills (agent builds its own toolbox)
- Performance (10,500 tok/s on Fast Apply)

**Implication**: The harness must expose **a code execution environment** (sandboxed) as central primitive.

## F29 — FlashCompact (Morph, 2026) — prevention > treatment

**Components**:
- **WarpGrep**: isolated search (0.73 F1, 3.8 steps), RL-trained
- **Fast Apply**: compact diffs (10,500 tok/s)
- **Morph Compact**: verbatim cleanup (3,300+ tok/s)

**Impact**: +15.6% cheaper, +28% faster, **each frontier model lifted to #1** on SWE-Bench Pro.

**Implication**: Our POV should integrate at least one of these patterns (WarpGrep-like search isolation).

## F30 — Cross-session leak via memory (Vulnerable)

**Issue**: Memory blocks shared cross-session = PII leak or poisoning.

**Implication**: ACL per tenant/principal, key per tenant (defense in depth).

---

## Synthesis for the design

**The 10 most structuring insights for our harness**:

1. **F3 (token = quality proxy)** → token ledger mandatory, live, per component
2. **F8 (code-as-API)** → primitives of code execution, not of tool calling
3. **F9 (ACE self-improving)** → playbook engine, versioned, dedup
4. **F10 + F11 (harness = half)** → 6 levers tooled, opinionated
5. **F15 (4 pillars)** → Write/Select/Compress/Isolate as native primitives
6. **F16 (4 failure modes)** → 4 adversarial gates per phase
7. **F19 + F20 (MemGPT + Memory Blocks)** → hierarchical typed memory
8. **F7 + F23 (subagent firewall)** → strict isolation, summary-only return
9. **F24 + F25 (long-running pattern)** → initializer + atomic features
10. **F4 (35min wall)** → hard time budget, mandatory checkpoint
