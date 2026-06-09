# Corpus — Index des sources primaires (2025-2026)

> **Date de compilation** : 2026-06-08
> **Méthodologie** : WebSearch + WebFetch sur Anthropic, LangChain, Morph, FlowHunt, HumanLayer, Addy Osmani, ICLR/arXiv, LangChain, MemGPT/Letta, Mem0, Cloudflare, etc.
> **Total** : 40+ sources primaires ou secondaires de haute qualité.

## Tier 1 — Sources primaires (papers + blogs officiels)

### Anthropic (5 sources)
1. **Effective Harnesses for Long-Running Agents** (2025-11-26) — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
   - Pattern "initializer + coding agent" + claude-progress.txt + feature_list.json
   - Failure modes long-running + solutions
2. **Code Execution with MCP** (2025-11) — https://www.anthropic.com/engineering/code-execution-with-mcp
   - 98.7% économie de tokens vs tool calling direct
   - 150K → 2K tokens pour tools
3. **Effective Context Engineering for AI Agents** (2025-09) — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
   - 7 principes fondateurs
4. **Building Effective Multi-Agent Research Systems** (2025-06-13) — https://www.anthropic.com/engineering/multi-agent-research-system
   - 4× / 15× tokens, 80% variance = tokens, 90.2% gain multi-agent
5. **Harness Design for Long-Running Application Development** (2026-03-24) — https://www.anthropic.com/engineering/harness-design-long-running-apps
   - Generator/evaluator (GAN-inspired), 3-agent harness
6. **Advanced Tool Use** (2025-11) — https://www.anthropic.com/engineering/advanced-tool-use
   - Tool Calling 2.0, programmatic tool calling
7. **Writing Effective Tools for AI Agents** (2026) — https://www.anthropic.com/engineering/writing-tools-for-agents
   - 25K token cap Claude Code, tool design principles

### arXiv / ICLR 2026 (6 sources)
8. **ACE — Agentic Context Engineering** (arXiv 2510.04618, ICLR 2026) — https://arxiv.org/abs/2510.04618
   - +10.6% agents, +8.6% finance, evolving playbooks
9. **Context Engineering (Specification Engineering)** (arXiv 2603.09619) — https://arxiv.org/pdf/2603.09619
   - IE (Intent Encoding), Specification Engineering concept
10. **Memory in the Age of AI Agents** (arXiv 2512.13564) — https://arxiv.org/abs/2512.13564
    - Survey 2026, agent memory landscape
11. **Memory as Action** (arXiv 2510.12635, ACL 2026) — https://arxiv.org/html/2510.12635v1
    - Memory-as-Action framework, explicit editing operations
12. **GEPA — Reflective Prompt Evolution** (arXiv 2507.19457) — https://arxiv.org/abs/2507.19457
    - +12% sur AIME-2025, dépasse MIPROv2 de 10%
13. **AOrchestra** (arXiv 2602.03786) — https://arxiv.org/html/2602.03786v1
    - +16.28% GAIA/SWE-Bench, sub-agent auto-création

### Mémoire & Mémoire Virtuelle
14. **MemGPT: Towards LLMs as Operating Systems** (arXiv 2310.08560) — https://arxiv.org/abs/2310.08560
    - Virtual context management, hierarchical memory
15. **Letta Memory Blocks** — https://www.letta.com/blog/memory-blocks
    - Memory blocks abstraction, context window management

### Industrie & Pratique
16. **LangChain — Context Engineering for Agents** (2025-07-02) — https://www.langchain.com/blog/context-engineering-for-agents
    - Write/Select/Compress/Isolate, Drew Breunig 4 failure modes
17. **LangChain — State of Agent Engineering 2026** — https://www.langchain.com/state-of-agent-engineering
    - Industry survey, deployment patterns
18. **Morph — Context Rot** (2026-03-13) — https://www.morphllm.com/context-rot
    - Chroma 18/18 study, 30% lost-in-middle, 35min wall, 60% retrieval, FlashCompact
19. **FlowHunt — Multi-Agent AI Systems in 2026** (2026-04-28) — https://www.flowhunt.io/blog/multi-agent-ai-system/
    - Consensus orchestrator+isolated, Tran & Kiela single-agent ≥ multi-agent
20. **Addy Osmani — Agent Harness Engineering** — https://addyosmani.com/blog/agent-harness-engineering/
    - "Agent = Model + Harness" (Viv Trivedy), 4 customization levers
21. **HumanLayer — Skill Issue: Harness Engineering for Coding Agents** (2026-03-12) — https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents
    - Harness as subset of context engineering, ETH Zurich study
22. **Mem0 — 2026 Token Optimization Playbook** (2026) — https://mem0.ai/blog/the-2026-token-optimization-playbook-cut-ai-agent-memory-costs-3%25E2%2580%25934x
    - 3-4× réduction coût mémoire
23. **Cloudflare — Code Mode + MCP** (2025) — référencé par Anthropic
    - Pattern code-as-API
24. **Simon Willison — Code execution with MCP** (2025-11-04) — https://simonwillison.net/2025/Nov/4/code-execution-with-mcp/
    - Synthèse critique Anthropic code execution

## Tier 2 — Sources secondaires (analyses, comparatifs, benchmarks)

### Benchmarks & Comparaisons
25. **BenchLM — LLM Context Window Comparison 2026** — https://benchlm.ai/blog/posts/context-window-comparison
    - Gemini 3.1 Pro 500K-1M, GPT-5.5, Claude Opus 4.7
26. **AIMultiple — VELC-Bench** — https://aimultiple.com/ai-context-window
    - 22 modèles, memory performance
27. **WhatLLM — Largest Context Window LLMs 2026** — https://whatllm.org/largest-context-window-llm
28. **Sebastian Raschka — LLM Research Papers 2026 (Jan-May)** — https://magazine.sebastianraschka.com/p/llm-research-papers-2026-part1
29. **Zylos — LLM Context Window Management 2026** (2026-01-19) — https://zylos.ai/research/2026-01-19-llm-context-management/
30. **Zylos — AI Agent Cost Optimization: Token Economics** (2026-02-19) — https://zylos.ai/research/2026-02-19-ai-agent-cost-optimization-token-economics/

### Sécurité
31. **MDPI — Prompt Injection Attacks in LLMs** — https://www.mdpi.com/2078-2489/17/1/54
32. **arXiv 2603.19469 — Framework for Formalizing LLM Agent Security** — https://arxiv.org/html/2603.19469v1
33. **Zylos — Indirect Prompt Injection 2026** (2026-04-12) — https://zylos.ai/zh/research/2026-04-12-indirect-prompt-injection-defenses-agents-untrusted-content
34. **Adversa AI — Top Agentic AI Security Resources April 2026** — https://adversa.ai/blog/top-agentic-ai-security-resources-april-2026/

### Outils & Frameworks
35. **DSPy GEPA Documentation** — https://dspy.ai/tutorials/gepa_ai_program/
36. **GEPA AI GitHub** — https://github.com/gepa-ai/gepa
37. **Google ADK — Architecting Efficient Context-Aware Multi-Agent** — https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/
38. **Inngest — Context Engineering in Practice** — https://www.inngest.com/blog/context-engineering-in-practice
39. **Vellum — Multi-Agent Systems with Context Engineering** — https://www.vellum.ai/blog/multi-agent-systems-building-with-context-engineering
40. **OpenReview — SupervisorAgent (Stop Wasting Your Tokens)** — https://openreview.net/forum?id=pzFhtpkabh

## Tier 3 — Articles/blogs cités en proxy

- **Cognition Labs — Don't Build Multi-Agents (Jun 2025) puis Devin can now Manage Devins (Mar 2026)** — synthèse via FlowHunt
- **Drew Breunig — 4 failure modes** (poisoning, distraction, confusion, clash) — cité dans LangChain
- **Karpathy — "LLM is CPU, context is RAM"** — métaphore OS
- **Anthropic — Prompt Caching documentation** (2025)
- **Anthropic — 2026 Agentic Coding Trends Report** (PDF) — https://resources.anthropic.com/hubfs/2026%2520Agentic%2520Coding%2520Trends%2520Report.pdf

## Résumé de l'évolution 2025 → 2026

| Concept | Émergence | Maturité 2026 |
|---------|-----------|----------------|
| Context Engineering (terme) | 2025 Q1 (Cognition) | Mainstream |
| Multi-agent + context isolation | 2025 Q2 (Anthropic) | Production |
| Compaction + scratchpad | 2025 Q3 (Anthropic cookbook) | Standard |
| RAG vs Long Context debate | 2025 Q4 (LightOn) | Complémentaire |
| **Agentic Context Engineering (ACE)** | **2025 Q4 (paper) → 2026 ICLR** | **Nouveau paradigme** |
| **Harness engineering** (terme) | **2025 Q4 (Viv Trivedy)** | **Standard** |
| **Code-as-API / Code Mode** | **2025 Q4 (Anthropic + Cloudflare)** | **Adoption rapide** |
| **Self-evolving contexts** | **2026 ICLR (ACE)** | **Frontière de recherche** |
| Memory as Action | 2026 ACL | Frontière |

## Findings synthétiques cross-sources

Voir `corpus/findings/00-synthesis.md` (à compléter dans Phase 2).

## Anti-patterns confirmés (8)

Voir `corpus/anti-patterns/INDEX.md` (à compléter dans Phase 2).
