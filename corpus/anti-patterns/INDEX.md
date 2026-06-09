# Anti-patterns context engineering (2025-2026)

> 12 anti-patterns confirmed by primary sources, with mitigation applicable to the harness.

## AP1 — "50 subagents for a simple question"

**Source**: Anthropic multi-agent research, 2025-06

**Symptom**: Excessive fan-out, work duplication, infinite exploration, cost × 15 without gain.

**Mitigation**: Explicit effort-scaling rules:
- 1 agent / 3-10 tool calls (fact-finding simple)
- 2-4 subagents (comparison)
- 10+ subagents (complex research ONLY)

**Our implementation**: `effort_scaling` enum in the DSL of subagent brief.

## AP2 — "Vague brief: research X"

**Source**: Anthropic multi-agent research, 2025-06

**Symptom**: Subagents duplicate, gaps, silent failures.

**Mitigation**: Structured brief OBJECT/FORMAT/TOOLS/BOUND mandatory.

**Our implementation**: Validator of brief in `bin/ctxh-validate-brief.sh`.

## AP3 — "Replay the transcript at each wakeup"

**Source**: FlowHunt, 2026-04

**Symptom**: Linear cost in turns × agents, supervisor paraphrasing unnecessarily.

**Mitigation**:
- Structured summary via cheap model
- Cap full-fidelity on sliding window
- Direct forward worker→user (50% economy)

**Our implementation**: Hook of wakeup that injects a digest, never the raw transcript.

## AP4 — "Peer-to-peer between subagents"

**Source**: FlowHunt, 2026-04

**Symptom**: O(n²) edge explosion, coherence drift, "herding" (premature consensus).

**Mitigation**: **No peer channel by default**. Everything via orchestrator or state DB.

**Our implementation**: Validation of the communication channel in the subagent firewall.

## AP5 — "Compaction triggered too late (95%)"

**Source**: Morph, 2026-03

**Symptom**: Compaction cleans the history but does not repair the wrong outputs already produced.

**Mitigation**: Preventive compaction at **60-70%** of the budget, not curative at 95%.

**Our implementation**: Token ledger with triggers at 60/70/85/95%, CC mandatory at 70%.

## AP6 — "Tool result clearing absent"

**Source**: Anthropic effective context engineering, 2025-09

**Symptom**: Results of old tool calls remain in the context, polluting.

**Mitigation**: Clear tool results after consumption. This is the safest compaction.

**Our implementation**: Hook `post-tool-use` that clears tool results after consumption by the next phase.

## AP7 — "Flood context for short tasks"

**Source**: Morph, 2026-03

**Symptom**: Fill the context "because we can" with 1M tokens of window, rot sets in.

**Mitigation**: Only load what serves the current phase. `hot_context` selective.

**Our implementation**: Token budget enforced, hard cap abort.

## AP8 — "Confusing window size with attention capacity"

**Source**: Morph, 2026-03 + Vectara, 2025

**Symptom**: "my model has 1M tokens, I can load everything". Reality: rot at 50K, attention dilution quadratic.

**Mitigation**: Token budget ≠ attention budget. Measure quality by **outcome** (gate), not by volume.

**Our implementation**: Dashboard per outcome (gate PASS/FAIL), not per tokens loaded.

## AP9 — "Auto-generated CLAUDE.md"

**Source**: ETH Zurich study via HumanLayer, 2026-03

**Symptom**: LLM generates a CLAUDE.md → -20% perf, +20% tokens.

**Mitigation**: **Human-curated** only, under 60 lines, each line = a past failure.

**Our implementation**: Linter `ctxh-lint-claudemd.sh` that refuses the >60 lines and the non-traced patterns.

## AP10 — "Tool description = prompt-injection vector"

**Source**: HumanLayer, 2026-03

**Symptom**: MCP server descriptions are injected in the system prompt. A malicious MCP = prompt-injection.

**Mitigation**:
- Allow-list of MCP servers
- Signing of descriptions
- Strict scope

**Our implementation**: `mcp-trust.json` with signatures, refusal by default.

## AP11 — "Subagent return = dump the transcript"

**Source**: Anthropic multi-agent, 2025-06

**Symptom**: Subagent returns everything, "game of telephone", exponential tokens.

**Mitigation**: Return contract strict: ref + summary + artifacts.

**Our implementation**: Validator `<subagent-result>` schema.

## AP12 — "Agent one-shots the app"

**Source**: Anthropic effective harnesses, 2025-11

**Symptom**: Tries to do everything at once, fails mid-stream, leaves feature half-implemented.

**Mitigation**:
- Feature list JSON with passes: false
- 1 feature at a time
- Git commit + log at each end

**Our implementation**: `feature_list.json` template + `init.sh` pattern.

## AP13 — "Lost-in-the-middle (positions 5-15)"

**Source**: Liu et al. Stanford/TACL 2024

**Symptom**: -30% accuracy for information in middle of the context.

**Mitigation**: **Critical elements in head/tail**, never in middle.

**Our implementation**: Structured layout: gate (head) → context → adversarial findings (tail).

## AP14 — "Compaction 'summarization' loses details"

**Source**: ACE paper, ICLR 2026

**Symptom**: "Brevity bias" and "context collapse" — summarizing iteratively erases.

**Mitigation**: Compaction = preserve structure + details. ACE playbook pattern.

**Our implementation**: `ctxh-compact` that preserves discrete events (vs paraphrase).

## AP15 — "Multi-agent without explicit token budget"

**Source**: Tran & Kiela, arXiv 2604.02460

**Symptom**: Multi-agent ≤ single-agent at equal token budget.

**Mitigation**: Justify each fan-out by (a) read-heavy parallel or (b) disjoint tools.

**Our implementation**: `ctxh-justify-fanout` that asks for justification before spawn.

## AP16 — "100% test suite run after each edit"

**Source**: HumanLayer, 2026-03

**Symptom**: 4K lines of passing tests flood the context, agent hallucinates.

**Mitigation**: **Success is silent, failure is verbose**. Surface only errors.

**Our implementation**: Test hook that swallows stdout on PASS, only surface stderr + summary on FAIL.

## AP17 — "MCP servers 'just in case'"

**Source**: HumanLayer, 2026-03

**Symptom**: Tool descriptions pollute the system prompt, "dumb zone" fast.

**Mitigation**: MCP server enabled **only if used**. Otherwise OFF.

**Our implementation**: Toggle MCP on/off based on usage, measure the impact.

## AP18 — "No time budget per phase"

**Source**: Morph, 2026-03 (35min wall)

**Symptom**: Phase that exceeds 35 min = exponential failure.

**Mitigation**: Hard time budget, mandatory checkpoint beyond, user escalation.

**Our implementation**: Timer per phase + soft/hard cap + circuit breaker.

## AP19 — "'Global' context in each phase"

**Source**: A1 (sequential-with-readonly), swebok context engineering

**Symptom**: Phase X contains all Y, violates A1, inflation of tokens.

**Mitigation**: **Consultation envelope strict**. X receives a slice of Y, never Y in its entirety.

**Our implementation**: `<consult phase="Y" query="..."/>` emits a slice token-budgeted.

## AP20 — "Tool definitions = 50% of context"

**Source**: Anthropic code execution, 2025-11

**Symptom**: 50K tokens of tool definitions for 5K of useful task.

**Mitigation**: Code-as-API (Cloudflare/Anthropic pattern), progressive disclosure via filesystem.

**Our implementation**: Tools exposed as code in `servers/` directory, not in system prompt.
