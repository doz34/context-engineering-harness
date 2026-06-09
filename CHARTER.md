# CE-Harness — Charter

> **Status**: v1.0 — 2026-06-09
> **Author**: discovery-orchestrator
> **Status**: draft v1 — 2026-06-08
> **Prepared by**: discovery-orchestrator
> **Sources**: Synthesis based on the 2025-2026 state of the art (Anthropic Context Engineering guide, OpenAI Agents SDK, Google ADK, RAG papers, hierarchical memory research). *Note: WebSearch being unavailable API-side at the time of writing, references come from the general knowledge corpus, not real-time search.*

---

## 1. Why this project is critical

The SWEBOK v4 Harness has **three structural properties** that make context engineering non-negotiable:

1. **Multi-agent by design** — multiple Nexus-* agents, one orchestrator, one adversarial gate with Red+Blue+Judge+Council (×4 reviewers). Each agent = one context.
2. **Phase-sequential on long-running project** — a project goes through **10 phases** (canonical model 2026-06-05, 1-par-1 SWEBOK v4 KAs). Each phase may accumulate large artifacts (specs, designs, code, tests, incident logs).
3. **Exhaustive audit chain** — every decision is logged. The replay = potentially infinite volume.

**Consequences without a strategy**:
- 💸 Token cost explodes (the quick test becomes a 4-figure bill)
- 🧠 LLM degradation (lost-in-the-middle, attention dilution, hallucinations)
- 🐌 Growing latency (each turn = compiling an ever-larger context)
- 🔁 Recency bias (the LLM forgets early-phase decisions)

---

## 2. The 4 Laws of context engineering (synthesis)

1. **Put in the context only what will be used** — RAG and just-in-time retrieval > stuffing
2. **Compress early, decompress late** — a compaction checkpoint at 70% of the budget is more efficient than an emergency summarize at 95%
3. **Isolate adversarial contexts** — T1 (producer/breaker), T2 (spec-compliance), T3 (conséquentialiste) must have disjoint contexts otherwise the attack loses its meaning
4. **Context is a finite-lifetime resource** — treat each window as precious, not as a free hard drive

---

## 3. Architecture in 4 layers (L0 → L3)

```
┌────────────────────────────────────────────────────────────┐
│ L0 — Long-term corpus (offline, never injected in bulk)   │
│   • 227 items distilled (principles, antipatterns, etc.) │
│   • 145k concepts corpus_v2                              │
│   • Access: tool call only                               │
├────────────────────────────────────────────────────────────┤
│ L1 — Phase outputs cache (structured, queryable)          │
│   • Each phase writes in a standardized format           │
│   • Cross-phase read = structured query, slice           │
│   • Not "read all P3" → "read me just the contracts"      │
├────────────────────────────────────────────────────────────┤
│ L2 — Phase working memory (volatile, token-budgeted)      │
│   • The context of the active phase                      │
│   • Auto-summarized at each step boundary                │
│   • Compaction checkpoint at 70% of soft cap             │
├────────────────────────────────────────────────────────────┤
│ L3 — Immediate context (what the LLM "sees" right now)   │
│   • Current task (1-2 sentences)                         │
│   • Relevant slice of L2                                 │
│   • Tool results (post-compression)                       │
│   • Last user message                                    │
└────────────────────────────────────────────────────────────┘
```

**Direct application to the project**:
- L0 already exists (`corpus/`, `distilled_corpus_v2/`) — must ensure it is **never** injected in bulk, only via tool calls
- L1 is partially in place (`specs/workflows/by-phase/`, `context/project-state.md`) — need to standardize the output format of each phase
- L2 needs formalization (working memory per phase, with budget)
- L3 is the only "live" context for the LLM

---

## 4. Specific techniques to implement

### 4.1 The Compaction Checkpoint (CC)

At each N tool calls (N=5 currently via ANTI-ROT), a compaction checkpoint:
- Summarizes what happened since the last CC
- Drops large tool results (keep the decision, not the raw data)
- Keeps a pointer to the data if it is re-needed
- Token counter + warning at 70/85/95% of budget

### 4.2 The Consultation Envelope (A1)

When phase X needs phase Y:
```
PHASE_X → CONSULTER(phase=Y, query="REST interface contracts",
                    scope="interfaces/contracts", format="summary")
                ↓
PHASE_Y_CACHE → SCOPE_FILTER → RESPONSE_SLICE
                ↓
PHASE_X receives ONLY the requested slice
```

**Key**: the context of X never contains all of Y. X receives a minimal structured object.

### 4.3 The User Decision Ledger (UDL)

Each user decision is logged with:
- Timestamp
- Phase + current step
- Context snapshot (token count, top-3 elements)
- Options presented (with rationale)
- Decision taken
- Reversibility flag
- Predicted impact (short term)

This ledger is:
- a source of future context (the LLM can consult it)
- a source of audit (replay of decisions)
- a source of improvement (analysis of decision patterns)

### 4.4 The Hot Path Optimization (HPO)

For micro-tasks (typo, config tweak, comment update):
- Skip full pre-tool-use phase check (use --lite)
- Token budget = 2k for the whole task
- No adversarial gate unless explicit
- Auto-compaction on each tool call

The `--lite` flag already exists in `auto-verify.sh`. It needs to be extended systematically.

### 4.5 The Adversarial Context Isolation (ACI)

For T1, T2, T3:
- **T1 (producer vs breaker)**: the breaker receives the artifact + the spec. It does not see the producer's system prompt.
- **T2 (spec-compliance)**: the auditor receives ONLY the spec and the artifact. It does not see T1 deliberations.
- **T3 (conséquentialiste)**: the downstream agent receives the interface contracts from P+1, P+2, not their implementation. It predicts ruptures.

**Key**: each adversarial role has a distinct context, otherwise the "adversaries" are influenced by the shared context.

### 4.6 The Decision Threshold Mechanism (DTM) — model B

Implementation of the user threshold:
- **High-impact / irreversible decision**: mandatory query, ranked options, 5min timeout, after = default decision
- **Reversible low-cost decision**: post-notification (summary log), validation on demand
- **Trivial decision**: silent, no log

The system must classify the decision at the moment it is presented (before asking).

---

## 5. Token budgets per phase (proposal)

> **Update 2026-06-05**: Structural fix. 10 phases (vs 9 before). P1 added (Concept/Feasibility). P3 and P4 created by split. P5-P10 = cascade rename P4-P9. Budgets updated.

| Phase | Base | Soft cap (CC) | Hard cap (abort) | Justification |
|-------|------|---------------|------------------|---------------|
| phase-0 Discovery | 4k | 7k | 10k | Exhaustive scoping validated 2026-06-04, aligned phase Design (spec v2) |
| **phase-1 Concept/Feasibility** | **3k** | **5k** | **8k** | **Quick go/no-go filter. Tightest phase of the project.** |
| phase-2 Requirements | 4k | 7k | 10k | SRS IEEE 830 validated 2026-06-05 (spec v2), 4 sequential agents + Nexus-Critic + Council NFR, sequential strict so not ×15 |
| **phase-3 Architecture** | **5k** | **8k** | **15k** | **Multi-agent justified (F13): 3-5 parallel sub-agents + Nexus-Critic T1+T2+T3 mandatory. ADRs mandatory, STRIDE threat model if security-sensitive. Hard cap 15k justified by additional Nexus-Critic T1+T2+T3 cost (~4.5k).** |
| phase-4 Design | 5k | 8k | 15k | Detailed design (consumes P3 ADRs, consumes ADRs = no re-architecture decision). 3-5 max agents + Nexus-Critic T1+T2+T3 mandatory (3 systematic invocations, like P3 v2). Differentiated contract format aligned P3 (md+json internal modules, +OpenAPI 3.0 REST APIs, +AsyncAPI 3.0 events option). ADR-to-module mandatory compliance matrix (XG-4.7). |
| phase-5 Implementation | 5k | 10k | 15k | Code, integration, CI/CD. Large budget (activity 1 of the project). |
| **phase-6 Testing** | **5k** | **8k** | **15k** | **Test suites, defects, reports + NFR perf+security + mutation testing. Multi-agent justified (F13): 4 test levels + 2 transverse (perf, security) + mutation in parallel + Nexus-Critic T1+T2+T3 mandatory (3 systematic invocations, like P3/P4/P5, maintainer decision 2026-06-07). Hard cap 15k justified by Nexus-Critic (~4.5k additional). P6 = 2nd most expensive phase of effort (20-40% project) after P5 Implementation. Coverage/mutation switch from P5 to P6 (P5 = unit only, P6 = coverage + mutation + rest).** |
| **phase-7 Deployment** | **5k** | **8k** | **15k** | **Multi-agent justified (F13): 5 sub-agents in parallel (Nexus-DevOps-Lead lead + Nexus-DevOps + Nexus-Backend + Nexus-Frontend + Nexus-SM) + Nexus-Critic T1 breaker plan + T2 go/no-go P6 compliance + NFR P2 + ADRs P3 + T3 P8 prediction downstream MANDATORY (3 systematic invocations, like P3/P4/P5/P6, maintainer decision 2026-06-07). Hard cap 15k justified by Nexus-Critic T1+T2+T3 (~4.5k additional). P6→P7 demarcation explicit (P6=code-will-go-to-prod, P7=prod-runs-after-deploy). Default rollout strategy = big-bang (DTM per project). Hotfix = no bypass. 7+4 deliverables (11). XG-7.1-XG-7.10 (10 exit criteria).** |
| phase-8 Operations | 2k (current) / 5k (P0-P1) | 4k (current) / 8k (P0-P1) | 6k (current) / 15k (P0-P1) | **Adaptive by incident severity** (decision 2026-06-07): current monitoring 1k/2k/3k (single Nexus-SM, no Critic, waste of tokens). Standard P2/P3 incident 2k/4k/6k (single + Nexus-Critic T2 spec-compliance). Critical P0/P1 incident 5k/8k/15k (multi-agent + Nexus-Critic T1+T2+T3 + Council post-incident, consistent P3-P7). Living phase (long duration, not project). Compaction per incident (AP5). |
| **phase-9 Maintenance** | **1k (hotfix) / 3k (standard) / 5k (structuring)** | **2k (hotfix) / 5k (standard) / 8k (structuring)** | **3k (hotfix) / 8k (standard) / 15k (structuring)** | **Adaptive 3-levels by criticality (P8 symmetry)**: hotfix/typo 1k/2k/3k --lite single without Critic; corrective/adaptive/preventive standard 3k/5k/8k single + Nexus-Critic T1+T2+T3; structuring/perfective heavy 5k/8k/15k multi-agent + Nexus-Critic T1+T2+T3 + Council structuring. Nexus-Critic T1 patch breaker + T2 DDS P4 compliance + ADRs P3 + NFR P2 + T3 P10 downstream prediction MANDATORY (3 systematic invocations except --lite, consistency P3-P7). P8↔P9 (Run vs Change) and P9↔P10 (prolong vs prepare death) demarcations explicit. 4 user decisions 5.5 (Q1 type maintenance + Q2 criticality + Q3 CAB + Q4 EOL). |
| **phase-10 Retirement** | **1k (simple) / 3k (GDPR) / 5k (regulated)** | **2k (simple) / 5k (GDPR) / 8k (regulated)** | **3k (simple) / 8k (GDPR) / 15k (regulated)** | **Adaptive 3-levels by compliance criticality (P8/P9 symmetry)**: simple archive 1k/2k/3k (single + T2); GDPR 3k/5k/8k (single + T1 breaker + T2); Finance/Health/Defense 5k/8k/15k (multi + T1+T2+T3 + mandatory Council closure). P10 = last phase of lifecycle (one-shot, not project). Nexus-Critic adaptive (T2 alone / T1+T2 / T1+T2+T3+Council). Demarcation P9↔P10 (prolong vs prepare death, already cut wave 1 P9) AND P10↔P0 (end of life old vs start of new system, cut wave 1 P10) explicit. Conditional Council closure by criticality. Hybrid reversibility by criticality (30j/90j/180j+ read-only). |

**Note**: these figures are orders of magnitude. Tuning must be empirical, based on actual measurement.

---

## 6. Failure modes to prevent

| Mode | Description | Detection | Mitigation |
|------|-------------|-----------|------------|
| **Context drift** | Silent accumulation of noise | CC at 70% of soft cap | Forced compaction |
| **Decision amnesia** | Forgetting earlier user choices | Hash UDL vs expected state | UDL injected in L3 if relevant |
| **Cross-phase contamination** | Phase X reads what Y wrote in secret | Permission manifest | Strict Consultation Envelope |
| **Adversarial leakage** | T1/T2/T3 share too much context | Audit of contexts injected by role | Strict ACI |
| **Token explosion** | Cost runs away without warning | Live token counter | CC + abort at hard cap |
| **Recency bias** | Early-phase decisions forgotten | Dissonance between UDL and behavior | UDL reminder at start of each step |
| **Lost-in-the-middle** | LLM "loses" the middle of the context | Recall metrics (T2 fails on middle elements) | Pyramid structure (decisions at top, bottom, never in middle) |

---

## 7. Anti-patterns to NOT do

- ❌ **Stuffing the corpus**: load all 227 items "just in case" → context death
- ❌ **Full re-read**: re-read all phase output at each step → waste
- ❌ **Over-aggressive summarization**: summarize too early = loss of critical precision
- ❌ **Too-late summarization**: summarize at 95% = cost already exploded
- ❌ **Shared context T1/T2/T3**: kills adversarial dynamics
- ❌ **Global project context** in each phase: violates A1
- ❌ **Audit logs in context**: HMAC chain is replayable, doesn't need to be in L3
- ❌ **Decisions without timestamp**: impossible to rule in case of ambiguity

---

## 8. Implementation roadmap

| Step | What | When | Effort | Impact |
|------|------|------|--------|--------|
| E1 | Live token counter in each phase spec | Sprint 1 | XS | S (visibility) |
| E2 | Compaction checkpoint at 70% of soft cap | Sprint 1 | S | L (economy) |
| E3 | Standardized L1 format (each phase writes in the same schema) | Sprint 1 | M | XL (interop) |
| E4 | Consultation Envelope (A1) implemented | Sprint 2 | L | XL (isolation) |
| E5 | User Decision Ledger (UDL) | Sprint 2 | M | L (audit + traceability) |
| E6 | Decision Threshold Mechanism (DTM) | Sprint 2 | S | L (UX) |
| E7 | Adversarial Context Isolation (ACI) | Sprint 3 | M | L (gates quality) |
| E8 | Dashboards per phase (tokens, decisions, CC) | Sprint 3 | M | M (observability) |
| E9 | Hot Path Optimization extended (--lite everywhere) | Sprint 3 | S | M (micro-tasks) |
| E10 | Memory decay (summarize previous episode at each phase start) | Sprint 4 | M | M (long-term projects) |

---

## 9. Open questions (to be arbitrated by the maintainer)

**🆕 Settled by audit P3 (2026-06-06)**:
- ✅ **P3 token budget**: 5k/8k/15k (vs 5k/8k/12k in v1), justified by Nexus-Critic T1+T2+T3 mandatory. P3 = 2nd widest phase (ex-aequo with P4 and P5).
- ✅ **Nexus-Critic in P3**: T1 breaker + T2 compliance + T3 downstream **ALL MANDATORY** (3 systematic invocations, ~4.5k additional tokens).
- ✅ **P3 contract format**: differentiated by type — md+json for internal modules, md+json+OpenAPI for REST APIs, md+json+AsyncAPI for async events (option).
- ✅ **P4 token budget**: 5k/8k/15k, justified by Nexus-Critic T1+T2+T3 mandatory. P4 = 3rd widest phase.
- ✅ **P5 token budget**: 5k/10k/15k (widest), justified by Nexus-Critic T1+T2+T3 mandatory + effort-report.md (formal deliverable, T-shirt vs real). P5 = most expensive phase in tokens (15× multi-agent vs chat).
- ✅ **Nexus-Critic in P4**: T1 breaker + T2 NFR P2 / ADRs P3 compliance + T3 downstream **ALL MANDATORY** (3 systematic invocations, ~4.5k additional tokens).
- ✅ **Nexus-Critic in P5**: T1 code breaker + T2 DDS P4 / ADRs P3 compliance + T3 P6 prediction downstream **ALL MANDATORY** (3 systematic invocations, ~4.5k additional tokens).

**🆕 Settled by audit P7 (2026-06-07)**:
- ✅ **P7 token budget**: 3k/5k/8k → **5k/8k/15k** (consistency P3/P4/P5/P6, justified by Nexus-Critic T1+T2+T3 mandatory, ~4.5k additional). P7 = 5th widest phase.
- ✅ **Nexus-Critic in P7**: T1 deployment plan breaker + T2 go/no-go P6 compliance + NFR P2 + ADRs P3 + T3 P8 prediction downstream **ALL MANDATORY** (3 systematic invocations, ~4.5k additional). **P7 goes from "Single-agent justified" to "Multi justified"** (consistency P3-P6 beats token economy, maintainer decision 2026-06-07).
- ✅ **P6→P7 demarcation explicit** (decision 2026-06-07): P6 = "code will go to prod without breaking" (staging iso-prod + tests + go/no-go); P7 = "prod runs correctly after deploy" (release + monitoring + handoff). Symmetrical to P5↔P6 demarcation.
- ✅ **Default rollout strategy**: big-bang (DTM per project). Hotfix = no bypass.
- ✅ **7+4 deliverables** (vs 7 v2-renum): 7 standard + 4 additions (changelog + runbook + monitoring dashboard + audit trail). 11 exit criteria XG-7.1-XG-7.10.

**🆕 Settled by audit P8 (2026-06-07)**:
- ✅ **P8 token budget**: **adaptive by incident severity** (vs 2k/4k/6k uniform v2-renum). Current monitoring 1k/2k/3k, standard P2/P3 incident 2k/4k/6k, critical P0/P1 incident 5k/8k/15k. Living phase (long duration, not project), unique specificity.
- ✅ **Nexus-Critic in P8**: **adaptive by incident severity**. Current monitoring = no Nexus-Critic (P8 = execution, not creation, waste of tokens). Standard P2/P3 incident = T2 only (spec-compliance vs runbook P7, 1 invocation). Critical P0/P1 incident = T1+T2+T3 mandatory (3 systematic invocations like P3/P4/P5/P6/P7) + Council post-incident (CISO + DevOps-Lead + SM).
- ✅ **P7↔P8 AND P8↔P9 demarcations explicit** (Setup vs Run vs Change): P7 = release + monitoring SETUP before deploy; P8 = monitoring CONTINUOUS post-release + alerts + escalation + capacity + post-mortems (without code modification); P9 = code CHANGE planned (corrective/adaptive/perfective/preventive). Limit cases settled: "calibrate an alert threshold" = P8 (config monitoring), "configure initial alerts" = P7 (setup), "modify code to reduce alerts" = P9 (fix).
- ✅ **4 user operational decisions (B threshold)**: Q1 calibration SLO/SLI thresholds, Q2 incident P0-P3 prioritization + escalation, Q3 post-mortem depth (1-page vs full RCA), Q4 accept deferred incidents (acceptable risk vs escalate P9).
- ✅ **P8 goes from "Single"** (initial suggestion §12.6) **to "Adaptive by severity"**: Single by default (current monitoring + standard incident), Multi justified for critical P0/P1 incidents. P8 unique specificity (no other phase has this adaptive structure).

**🆕 Settled by audit P10 (2026-06-07)**:
- ✅ **P10 token budget**: **adaptive 3-levels by compliance criticality** (vs 2k/3k/5k uniform v2-renum). Simple archive 1k/2k/3k, GDPR/standard 3k/5k/8k, Finance/Health/Defense 5k/8k/15k. P8/P9 symmetry.
- ✅ **Nexus-Critic in P10**: **ADAPTIVE by compliance criticality** (vs T1+T2+T3 mandatory P3-P7 or adaptive P8/P9). Simple archive = T2 alone (1 invocation ~1.5k, procedural compliance + reversibility check). GDPR/standard = T1 breaker archive (Data Loss Hunter) + T2 regulatory compliance (2 invocations ~3k). Finance/Health/Defense = T1+T2+T3 (3 invocations ~4.5k) + mandatory closure Council (CISO+Legal+PM+DevOps-Lead, 1h examination, ~2k). Additional cost up to 6.5k in regulated mode, justified by 15k hard cap.
- ✅ **P10↔P0 demarcation explicit** (Central question, P9 symmetry): P10 = end of life of EXISTING system (archive, compliance, ownership transfer, notification). P0 = start of NEW system (exploration, intake, JTBD, scoping). Limit cases settled: "reuse archived components for new system" = P0 of new (not P10, we talk about new). "Lessons learned from an EOL" = P10 (post-retirement review, attached to archived system). "Re-activation of archived system (EOL cancellation)" = P10 (re-archiving, traceability of EOL decisions). Triple demarcation P8↔P9↔P10 (Run vs Change vs Retire) + P10↔P0 close all contested phase borders of the project.
- ✅ **Conditional Council closure by criticality** (vs mandatory for Finance/Health/Defense): Simple archive = Nexus-DevOps-Lead signature sufficient. GDPR/standard = Nexus-DevOps-Lead + CISO + Legal signature. Finance/Health/Defense = Council CISO+Legal+PM+DevOps-Lead mandatory (1h examination, collective signature before `PROJECT_RETIRED`). P8/P9 symmetry.
- ✅ **Hybrid reversibility by criticality**: Simple archive = 30j read-only, GDPR/standard = 90j read-only (consistent P9 hotfix window), Finance/Health/Defense = 180j+ read-only. Restorable on stakeholder request, not automatic. Categorical refusal 6: "No definitive deletion before reversibility period (Q3 user 5.5)".
- ✅ **4 user operational decisions (B threshold)**: Q1 type retirement (simple archive / GDPR / Finance-Health-Defense / ownership transfer), Q2 compliance criticality (simple / standard / high), Q3 reversibility (30j / 90j / 180j+ / undefined), Q4 P0 link (none / parallel / lessons learned / after). P8/P9 symmetry.
- ✅ **P10 goes from "Single"** (initial suggestion §12.6) **to "Adaptive by compliance criticality (3-levels, P8/P9 symmetry)"**: single + T2 simple archive, single + T1+T2 GDPR, multi + T1+T2+T3 + Council Finance/Health/Defense. Demarcation P9↔P10 (prolong vs prepare death, already cut wave 1 P9) AND P10↔P0 (end of life old vs start of new) explicit, close all contested phase borders of the project.

**🔴 Still open (to be arbitrated)**:
1. **L1 format**: structured JSON, structured Markdown, or both? (affects all consumers)
2. **P0-P10 token budgets**: are these figures realistic after measurement on real projects? (to adjust empirically, v2.1 target)
3. **T3 by default on P6 Testing**: ✅ **SETTLED for P3, P4, P5, P6** — T1+T2+T3 **MANDATORY** (3 systematic invocations, maintainer decision 2026-06-07). P6 = multi-agent justified (4 levels + 2 transverse + mutation), Nexus-Critic mandatory like P3/P4/P5. Hard cap 15k justified on the 4 multi-agent phases.
4. **DTM timeout**: is 5min acceptable? More? With progressive notification?
5. **UDL privacy**: who can see the ledger? (maintainer only? current phase? post-mortem audit?)
6. **--lite for P5-P7**: where does the hot path stop? What complexity triggers the full check?
7. **🆕 2026-06-06**: **External expert opinion to close section 7 of the grilles**: who? (independent senior architect? consultancy? former colleague?). Estimated cost? Timing (before v2.0? before v1.6.0?).

---

## 10. Success metrics (to measure)

- **Average cost per complete project** (P0→P9) — should drop by X% after implementation
- **% of CC triggered at 70%** (sign of correct tuning)
- **% of hard cap reached** (target: < 2% of phases)
- **% of repeated user decisions** (sign that context forgets)
- **False positive rate of gates** (T2 fails by mistake) — sign of adversarial leakage
- **Average latency per phase** (target: no increase)

---

## 12. Empirical validation 2026 (additional research)

> Section added 2026-06-04 following research `01-context-engineering-research-2026.md` (15 search queries, 5 URLs fetched, 30+ primary sources, 15 findings, 15 benchmarks, 8 anti-patterns).

### 12.1 Key findings validating or refining the strategy

| # | Finding | Source | Strategy implication |
|---|---------|--------|------------------------|
| **F1** | 80% of performance variance = token usage (BrowseComp) | Anthropic multi-agent research (2025-06) | Phase budget is a **quality proxy**, not just cost-control |
| **F2** | Multi-agent = 15× chat tokens; single-agent = 4× | idem | **Justify every Nexus fan-out** as "high-value" |
| **F3** | Subagent brief must carry 4 fields: OBJECT/FORMAT/TOOLS/BOUND | idem | DSL `KEY:VALUE;;KEY:VALUE` maps naturally — audit each spawn |
| **F4** | Context rot: 18/18 models degrade at EVERY increment | Chroma study via Morph (2026-03) | "More context" is not a solution. Gating per phase mandatory |
| **F5** | Lost-in-the-middle = -30% accuracy in position 5-15 (on 20 docs) | Liu et al. Stanford/TACL 2024 | **Critical elements in head/tail**, never in middle |
| **F6** | 35 min wall: failure rate × 4 when duration × 2 | Morph (2026-03) | Budget time per phase; mandatory checkpoint beyond |
| **F7** | 60% of agent first turn = retrieval (Cognition/Devin) | Morph (2026-03) | **Pre-hydrate mandatory** at phase start |
| **F8** | Compaction Claude Code = 95% of window (reference) | Claude Cookbook | Our ANTI-ROT every 5 calls = too aggressive or poorly measured. Aim 60-70% in tokens |
| **F9** | 50% economy: forward worker→user (vs swarm supervisor) | LangChain 2025 via FlowHunt | Bypass Hyperagent when it only relays |
| **F10** | Subagent output → filesystem (persistent artifact), not transcript | Anthropic Appendix | `.swebok_state.db` = this filesystem. Subagent writes, lead receives a pointer |
| **F11** | Prompt caching: stable prefix only at head | Anthropic docs | If Claude API call: system + phase_rules + DSL schema at head, never dynamic tool result before |
| **F12** | RAG embedding = mathematical ceiling for code (DeepMind) | Morph (2026-03) | Prefer grep/AST/keyword + rerank LLM on `distilled_corpus_v2/` |
| **F13** | Single-agent ≥ multi-agent at equal token budget (reasoning) | Tran & Kiela arXiv 2604.02460, April 2026 | For P0, P2, P6 = single Nexus suffices. Multi-agent justified only if (a) read-heavy parallel or (b) disjoint tools |
| **F14** | Adversarial loop Red→Blue→Judge = production pattern | Farzulla 2025 | Validates `adversarial-gate.sh` Red/Blue/Judge + Council Bridge |
| **F15** | Tamper-evident log = HMAC chain | Cossack Labs 2025 | Extends HMAC to ALL DSL events, not just phase transitions |

### 12.2 4 failure modes of Drew Breunig (NEW)

LangChain blog (2025-07) cites Drew Breunig who identifies 4 systemic failure modes:

1. **Poisoning**: hallucination or error contaminates all downstream reasoning
2. **Distraction**: overloaded context makes the LLM's attention diverge
3. **Confusion**: superfluous information dilutes the important signals
4. **Clash**: contradictory information in context blocks the decision

**SWEBOK v4 implication**: each phase grille should audit these 4 modes in its section 6 (Bounds and failure modes). Suggestion: add a sub-section "6.6 Failure modes Drew Breunig" to each grille.

### 12.3 Operational benchmarks integrated

| Metric | Value | SWEBOK budget application |
|--------|-------|------------------------------|
| Multi-agent tokens / chat | ~15× | Baseline P3, P4, P5: budget × 15, justify fan-out |
| Single-agent tokens / chat | ~4× | Baseline P0, P2, P6: one Nexus only |
| Multi-agent gain on single-agent (research) | +90.2% | Validates Hyperagent+Nexus on research/architecture, **not** on code |
| 3-5 subagents parallel | -90% duration | Phase duration budget = single_duration / 3-5 |
| Lost-in-the-middle (5-15/20) | -30% accuracy | Mandatory pyramid structure |
| 35 min wall | ×4 failure rate when duration ×2 | Checkpoint mandatory beyond |
| 1st turn = 60% retrieval | — | Pre-hydrate = × 2.5 gain on 1st turn |
| Variance tokens between equivalent runs | × 10 | Measure tokens per phase to detect drift |
| Compaction trigger Claude Code | 95% window | Reference for our ANTI-ROT; express in % of budget |
| Subagent tokens (Anthropic) | "tens of thousands" per subagent | Return to lead must be 1-2K tokens, not a dump |

### 12.4 Confirmed anti-patterns (8) with SWEBOK mitigation

- **AP1**: "50 subagents for a simple question" — Source: https://www.anthropic.com/engineering/multi-agent-research-system. Symptom: excessive fan-out, work duplication, infinite exploration. Mitigation: explicit effort-scaling rules (1 agent / 3-10 tool calls for fact-finding; 2-4 subagents for comparisons; 10+ for complex research). **SWEBOK**: integrate into `phase_rules.json` subagent budget by task type.
- **AP2**: Vague brief like "research X" — Source: idem. Symptom: subagents duplicate, gaps, silent failures. Mitigation: structured brief OBJECT/FORMAT/TOOLS/BOUND. **SWEBOK**: audit each Nexus spawn against the checklist; the DSL must carry these 4 fields.
- **AP3**: Replay the full transcript at each wakeup — Source: https://www.flowhunt.io/blog/multi-agent-ai-system/. Symptom: linear cost in turns × agents, supervisor paraphrasing unnecessarily. Mitigation: structured summary via cheap model; full-fidelity cap on sliding window; direct forward worker→user. **SWEBOK**: Hyperagent must receive a digest, not the full transcript.
- **AP4**: Peer-to-peer channel between subagents — Source: idem. Symptom: O(n²) edge explosion, coherence drift, "herding" (premature consensus). Mitigation: no peer channel by default. **SWEBOK**: no Nexus↔Nexus communication; everything via Hyperagent or by writing to `.swebok_state.db`.
- **AP5**: Compaction triggered too late (95% = already degraded) — Source: https://www.morphllm.com/context-rot. Symptom: compaction cleans the history but does not repair the wrong outputs already produced. Mitigation: preventive compaction at 60-70% of the budget, not curative at 95%. **SWEBOK**: revise ANTI-ROT — trigger on tokens or % of phase budget, not on number of calls.
- **AP6**: Tool result clearing absent — Source: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents. Symptom: results of old tool calls remain in context, polluting. Mitigation: clear the results of tool calls "deep in history" — this is the safest compaction. **SWEBOK**: empty the tool results after consumption by the next phase.
- **AP7**: "Flood" context for short tasks — Source: https://www.morphllm.com/context-rot. Symptom: fill the context "because we can" with 1M tokens of window, rot sets in. Mitigation: only load what serves the current phase. Selective `hot_context` per phase; NEVER load the entire `distilled_corpus_v2/` into a Nexus.
- **AP8**: Confusing window size with attention capacity — Source: idem + https://www.vectara.com/blog/context-engineering-can-you-trust-long-context. Symptom: "my model has 1M tokens, I can load everything". Reality: rot at 50K, quadratic attention dilution. Mitigation: token budget ≠ attention budget. **SWEBOK**: measure quality by outcome (gate), not by loaded context volume.

### 12.5 Updated roadmap (12 prioritized recommendations)

**P1 — Implement immediately (high value, S/M effort)**:
1. Reformulate ANTI-ROT in relative threshold (tokens or % of phase budget), not call counter. Target trigger: 60-70%.
2. Document the "subagent contract" in `phase_rules.json`: OBJECT/FORMAT/TOOLS/BOUND mandatory for each Nexus spawn. Audit existing Nexus.
3. Place critical elements at head/tail of Nexus context (active gate, phase constraints, adversarial findings).
4. **🆕 2026-06-06**: **Extend the 4 failure modes Drew Breunig audit method to P4-P10** (moved from grille P3 action P3-10). Reference: P0 v2 + P2 v2 + P3 v2. The method is already documented, the extension is mechanical.
5. **🆕 2026-06-06**: **Close section 7 (real utility) of grilles P1, P3, and future P4-P10 by external expert opinion OR by 1-2 real projects** (moved from grilles P1 and P3 actions P1-8 and P3-8). Effort: XS per phase (one test project is enough, or 1 expert opinion per phase).

**P2 — Implement next sprint (high value, M effort)**:
6. Time budget per phase: 35 min target, mandatory checkpoint beyond.
7. Pre-hydrate mandatory at phase start (load hot_context in `.swebok_state.db`).
8. Direct forward worker→user when Hyperagent doesn't synthesize anything (~50% economy).
9. Extend HMAC chain to all DSL events (not just transitions).
10. **🆕 2026-06-06**: **Close section 7 (real utility) of grilles P1, P3, and future P4-P10 by external expert opinion OR by 1-2 real projects** (moved from grilles P1 and P3 actions P1-8 and P3-8). Effort: XS per phase (one test project is enough, or 1 expert opinion per phase).

**P3 — Plan (medium value or L effort)**:
11. Distinguish explicitly "single-agent OK" phases (P0, P2, P6) vs "multi-agent justified" phases (P3, P4, P5). Justification by 15× tokens + narrow domain (Drammeh).
12. Prefer grep/AST/rerank to embedding search on `distilled_corpus_v2/`. Embedding = mathematical ceiling for code (DeepMind/Morph).
13. If Claude API call: structure payload with cache stable prefix (system + phase_rules + DSL schema) at head. NEVER insert dynamic tool result before.
14. Document the 4-failure-mode grid (poisoning, distraction, confusion, clash de Drew Breunig) in the strategy and audit it per phase.
15. Prepare long-running migration: when Anthropic publishes "Effective Harnesses for Long-Running Agents" (referenced January 2026), ingest as V2.1 of the strategy.

### 12.6 Phases "single-agent OK" vs "multi-agent justified" (recommendation P3-8)

> **Update 2026-06-05**: Structural fix. 10 phases model.

| Phase | Type | Justification |
|-------|------|---------------|
| **P0 Discovery** | Single | Sequential, exploration, little state |
| **P1 Concept/Feasibility** | Single | Quick go/no-go filter, 4 agents in standard (5th Nexus-DevOps if complex infra PoC), tight budget |
| **P2 Requirements** | Single | SRS, IEEE 830, single Nexus-PM sufficient (4 sequential + 1 Nexus-Critic + 4 Council NFR) |
| **P3 Architecture** | **Multi justified** | 3-5 parallel sub-agents (Arch, Sec, Backend, Frontend, DevOps) + **Nexus-Critic T1+T2+T3 mandatory (3 systematic invocations, ~4.5k tokens)**. Read-heavy parallel. Hard cap 15k. |
| **P4 Design** | **Multi justified** | 3-5 parallel sub-agents (Arch, Backend, Frontend, DevOps, Security) + **Nexus-Critic T1+T2+T3 mandatory (3 systematic invocations, like P3 v2)**. Consumes P3 ADRs (no re-architecture decision = mandatory ADR → module matrix XG-4.7). Differentiated contract format aligned P3 (md+json internal modules, +OpenAPI 3.0 REST APIs, +AsyncAPI 3.0 events option). Hard cap 15k justified by Nexus-Critic T1+T2+T3 (~4.5k additional). |
| **P5 Implementation** | **Multi justified** | 3-5 parallel sub-agents (Backend, Frontend, DevOps, Security) + **Nexus-Critic T1 code breaker + T2 DDS P4 / ADRs P3 compliance + T3 P6 prediction downstream MANDATORY (3 systematic invocations, like P3 and P4, maintainer decision 2026-06-07)**. Consumes P4 DDSs (no re-design decision = mandatory DDS → code matrix XG-5.7). `effort-report.md` deliverable fills SWEBOK P4 absent. Hard cap 15k justified by Nexus-Critic T1+T2+T3 (~4.5k additional). |
| **P6 Testing** | **Multi justified** | **4 test levels (integration, system, acceptance, regression) + 2 transverse (perf, security) + mutation in parallel + Nexus-Critic T1 test breaker + T2 acceptance criteria P2 compliance + T3 P7 prediction downstream MANDATORY (3 systematic invocations, like P3/P4/P5, maintainer decision 2026-06-07). Consumes P5 code + P2 acceptance criteria + P2 NFRs (no re-coding decision = escalate P5, no re-NFR definition = escalate P2). Coverage/mutation switch from P5 to P6 (P5 = unit only, P6 = coverage + mutation + rest). 11+1 deliverables (test plan + 4 results per level + defect + TTM + closure + 3 transverse + go/no-go). Hard cap 15k justified by Nexus-Critic T1+T2+T3 (~4.5k additional).** |
| **P7 Deployment** | **Multi justified** | **5 sub-agents in parallel (DevOps-Lead + DevOps + Backend + Frontend + SM) + Nexus-Critic T1 deployment plan breaker + T2 go/no-go P6 compliance + NFR P2 + ADRs P3 + T3 P8 prediction downstream MANDATORY (3 systematic invocations, like P3/P4/P5/P6, maintainer decision 2026-06-07). Consumes P6 go/no-go memo + closure report + validated test plan to bring production-ready code to production-running. Hard cap 15k justified by Nexus-Critic T1+T2+T3 (~4.5k additional). P6→P7 demarcation explicit (P6=code-will-go-to-prod, P7=prod-runs-after-deploy). Default rollout strategy = big-bang (DTM per project).** |
| **P8 Operations** | **Adaptive by incident severity** | **Current monitoring** = single Nexus-SM (without Critic, 1k/2k/3k). **Standard P2/P3 incident** = single Nexus-SM + Nexus-Critic T2 spec-compliance vs runbook (2k/4k/6k, 1 invocation). **Critical P0/P1 incident** = multi-agent (Hyperagent + SM + DevOps + Security + Backend + Frontend) + Nexus-Critic T1+T2+T3 mandatory (3 invocations, consistent P3-P7) + Council post-incident (CISO + DevOps-Lead + SM, 5k/8k/15k). **P8 specificity**: living phase (long duration, not project), budget per incident not per session. Immediate compaction after RCA (AP5). P7↔P8 and P8↔P9 demarcations explicit. 4 user operational decisions (threshold calibration, incident prioritization, post-mortem depth, deferred). |
| **P9 Maintenance** | **Adaptive by criticality (3-levels, P8 symmetry)** | **Hotfix/typo/micro-task** = single --lite without Critic (1k/2k/3k, hot path, waste of tokens avoided). **Corrective/Adaptive/Preventive standard** = single + Nexus-Critic T1+T2+T3 mandatory (3k/5k/8k, 3 systematic invocations, consistency P3-P7). **Structuring/Perfective heavy/Refactoring major** = multi-agent (Hyperagent + Lead + Architect + Security + QA + PM) + Nexus-Critic T1+T2+T3 mandatory (3 invocations) + Council structuring (CISO + DevOps-Lead + Architect, 1h examination before deploy, 5k/8k/15k consistent P3-P7). P9 = patch + regression, not architecture creation, so 3-levels budget adapted to the nature of the task. P8↔P9 (Run vs Change) and P9↔P10 (prolong vs prepare death) demarcations explicit. 4 user decisions 5.5 (type + criticality + CAB + EOL). 11 deliverables (6 standard + 5 additions: diff/patch + decision rationale + ADR + changelog public + post-mortem if incident). UDL 7 elements. P9 specificity: consumption of CRs emitted by P8 + escalation to P10 if EOL approaches. |
| **P10 Retirement** | **Adaptive by compliance criticality (3-levels, P8/P9 symmetry)** | **Simple archive** = single Nexus-DevOps-Lead + T2 alone (1k/2k/3k, no Council). **GDPR/standard** = single + T1 breaker archive (Data Loss Hunter) + T2 regulatory compliance (3k/5k/8k, signature CISO+Legal). **Finance/Health/Defense** = multi + T1+T2+T3 + mandatory closure Council (5k/8k/15k, collective signature CISO+Legal+PM+DevOps-Lead). **P10 specificity**: last phase of lifecycle (one-shot, not project, not living phase). P9↔P10 (prolong vs prepare death, already cut wave 1 P9) AND P10↔P0 (end of life old vs start of new system, cut wave 1 P10) explicit. Immediate compaction after `PROJECT_RETIRED` (one-shot phase). Conditional Council closure by criticality (symmetry P8 Council post-incident P0/P1 and P9 Council structuring). Hybrid reversibility by criticality (30j/90j/180j+ read-only). 9+3 deliverables (9 standard + legal/compliance sign-off + communication-sent-log). UDL 7 elements P10-specific. Nexus-Critic adaptive (T2 alone / T1+T2 / T1+T2+T3+Council). 4 user decisions 5.5 (Q1 type retirement, Q2 criticality, Q3 reversibility, Q4 P0 link). |

**Note**: "Multi-agent justified" does not mean "always multi-agent". The trigger is: (a) read-heavy parallel or (b) disjoint tools. Otherwise, single.

### 12.7 Complementary sources recovered (not covered by sections 1-11)

- **LangChain — Context Engineering for Agents** (2025-07-02): taxonomy Write/Select/Compress/Isolate
- **Morph — Context Rot: Why LLMs Degrade as Context Grows** (2026-03-13): Chroma + benchmarks synthesis
- **FlowHunt — Multi-Agent AI Systems in 2026: What the Research Actually Says** (2026-04-28): orchestrator + isolated subagents consensus
- **VILA-Lab — Dive into Claude Code: The Design Space of Today's and Future AI Coding Agents** (arXiv 2604.14228, 2026-04): isolated subagent boundaries + deny-first confirmed
- **Cognition Labs**: pivot single-threaded → coordinator + managed Devins (June 2025 → March 2026)
- **AORCHESTRA** (arXiv 2602.03786): +16.28% on GAIA/SWE-Bench
- **Drammeh** (arXiv 2511.15755): narrow-domain multi-agent = 100% vs 1.7% actionable
- **Tran & Kiela** (arXiv 2604.02460, April 2026): at equal reasoning token budget, single-agent match or beats multi-agent
- **Farzulla 2025**: Autonomous Red Team and Blue Team AI pattern
- **Cossack Labs 2025**: HMAC chain audit logs
- **Towards AI — Long Context Compaction Part 1**: STM + summarization 2-tiers
- **Emotion Machine — Three Memory Architectures**: pre-hydrate + structured note-taking + periodic eviction
- **Zylos Research — AI Agent Context Compression Strategies** (2026-02-28): anchored iterative summarization

### 12.8 Sources not recovered (to be explored in V2)

- **Anthropic — Effective Harnesses for Long-Running Agents** (Jan 2026): referenced in several aggregators (LinkedIn, Medium), not recovered directly due to lack of confirmed URL. Probably a follow-up to the effective-context-engineering post; to be recovered in V2 if specific long-running patterns are needed.
- **Cognition Labs — Don't Build Multi-Agents (Jun 2025)** and **Devin can now Manage Devins (Mar 2026)**: cited in FlowHunt, primary blogs not opened (paywall probable / Cognition blog). FlowHunt synthesis retained as proxy.
- **arXiv 2603.09619 (Context Engineering paper)**: URL cited by web search, verification of arXiv ID to reconfirm (2603 = March 2026, plausible but not verified). Cited in proxy via FlowHunt.
- **arXiv 2604.11978v1 (HORIZON benchmark long-horizon)**: indirect reference, content not recovered due to time; to be opened if the strategy digs into long-horizon.
- **arxiv 2602.03786 (AORCHESTRA)** and **arxiv 2604.02460 (Tran & Kiela)**: cited in FlowHunt, abstracts not recovered directly. Numbers taken as-is with FlowHunt attribution.

---

*Section 12 written by Claude 2026-06-04 from `01-context-engineering-research-2026.md`.*

---

## 11. Reference sources (state of the art 2025-2026)

### Primary sources recovered via WebFetch (2026-06-04)

- **Anthropic — Effective Context Engineering for AI Agents** (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — 7 founder principles recovered:
  1. System prompts at the right altitude (neither too rigid, nor too vague)
  2. Token-efficient tools (self-contained, minimal overlap)
  3. Curated few-shot examples (diverse, canonical)
  4. Just-in-time context retrieval (pointers + tools, not stuffing)
  5. Hybrid retrieval (pre-retrieval + exploration)
  6. 3 long-horizon techniques: **compaction** + structured note-taking + sub-agent architectures
  7. Tool result clearing (raw result rarely re-needed)

- **Anthropic — Building Effective Multi-Agent Research Systems** (https://www.anthropic.com/engineering/multi-agent-research-system) — key insights for SWEBOK v4:
  - **Token cost**: multi-agent = **4× chat, 15× multi-agent vs chat** (per Anthropic BrowseComp eval)
  - **80% of variance** of performance = tokens used
  - **95% with tool calls + model choice**
  - **Multi-agent justified only** if "value of task is high enough"
  - **Effort scaling**: 1 agent 3-10 calls (simple), 2-4 subagents 10-15 calls (comparison), 10+ subagents (complex)
  - **Context isolation** = separate context windows per subagent
  - **Lead agent** = only one with full view; subagents = narrow scopes
  - **Persistent plan in memory** (otherwise truncated to 200k tokens)
  - **Artifact/file output** for big results (subagent → file, lead → light reference)
  - **Anti-pattern**: vague subagent instructions → duplicated work
  - **Anti-pattern**: 50 subagents for nothing
  - **Anti-pattern**: agents that keep searching when they have enough
  - **Current bottleneck**: synchronous execution (lead cannot steer the subagents)

### Complementary sources (general knowledge corpus)

- Anthropic — *Prompt Caching* documentation
- OpenAI — *Agents SDK* context management patterns
- Google — *Agent Development Kit* memory hierarchy
- LangChain — *LangGraph* state management & checkpointing
- MemGPT / Letta — virtual context management
- RAG papers (Lewis et al. original, dense retrieval, hybrid search)
- Hierarchical memory research (SummScreen, multi-level summarization)

### Direct application to SWEBOK v4 (synthesis)

The architecture of the project **is already partially aligned** with these best practices:
- ✅ Hyperagent-Orchestrator + Nexus-* = Lead/Subagent pattern
- ✅ Adversarial-gate (Red/Blue/Judge) = adversarial pattern
- ✅ COUNCIL BRIDGE (4 reviewers) = council pattern
- ✅ .swebok_state (SQLite) = persistent state
- ✅ DSL format `KEY:VALUE;;KEY:VALUE` = structured output
- ⚠️ **To formalize**: consultation envelope (A1) — phases are not explicitly read-only cache
- ⚠️ **To formalize**: context isolation between T1/T2/T3 — not explicit currently
- ⚠️ **To formalize**: live token budget per phase
- ⚠️ **To formalize**: explicit compaction checkpoint
- ⚠️ **To formalize**: user decision ledger (UDL)

*WebSearch remained unavailable during this session (systematic 400 API error). WebFetch allowed recovery of 2 primary Anthropic sources. The secondary sources come from the general knowledge of the model.*

---

*Charter written 2026-06-08 by discovery-orchestrator. Reference document for all CE-Harness work.*
