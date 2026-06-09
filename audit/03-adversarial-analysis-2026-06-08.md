# Adversarial Analysis per Phase — 2026-06-08

> **Type**: Red Team (attack mode), not compliance.
> **Target**: CE-Harness POV (post-S2), 11 phases (P0-P10 + POV itself)
> **Methodology**: 4 classes of attackers × 5 cross-phase vectors = 20-attack matrix
> **Goal**: Identify blind spots BEFORE a real attacker finds them

---

## 0. Threat model — 4 classes

| Class | Profile | Goal | Likely tools |
|-------|---------|------|--------------|
| **A1 — External** | Attacker via prompt injection, malicious MCP, supply chain | Data theft, exfiltration, takeover | Indirect prompt injection, tool poisoning, typosquatting |
| **A2 — Internal** | Compromised process, corrupted state, race condition | State corruption, HMAC chain break, DoS | SQL injection (SQLite WAL), state.db race, hash collision |
| **A3 — Logic** | Edge cases of POV, invariants misunderstood, type confusion | Pass fake for true, abuse token budget | DSL ambiguity, vague subagent brief, type confusion |
| **A4 — Temporal** | Long-running, drift, decay, cross-session shared state | Session hijack, replay attack, slow-burn data exfil | Session hijack, audit replay, slow-burn data exfil |

---

## 1. Catalog of 20 cross-phase attack vectors

| ID | Vector | Class | Phase(s) touched |
|----|--------|--------|------------------|
| V01 | Indirect prompt injection via tool_result | A1 | P3, P5, P6 |
| V02 | Malicious MCP server (typosquatting, supply chain) | A1 | P5, P6, P7 |
| V03 | HMAC chain forgery / replay | A2 | P8, P9, P10 |
| V04 | SQLite WAL corruption / lock contention | A2 | All |
| V05 | State.db race condition (TOCTOU) | A2 | P3, P4 |
| V06 | DSL ambiguity (parsing collision) | A3 | All |
| V07 | Vague subagent brief → exfiltration scope | A3 | P3, P4, P5 |
| V08 | Token counter inflation (game the budget) | A3 | All |
| V09 | Type confusion (memory block attack) | A3 | P3, P4 |
| V10 | Lost-in-the-middle exploitation (cache key in middle) | A3 | All |
| V11 | Session hijack via state.db (no auth) | A4 | P0-P10 |
| V12 | Long-running decay (35 min wall edge case) | A4 | P3, P5 |
| V13 | Replay of compaction results (collision) | A4 | P4 |
| V14 | Cross-session leak via memory blocks | A4 | P3, P4 |
| V15 | Audit chain replay across rollback | A4 | P8, P9 |
| V16 | Subagent return channel smuggling | A3 | P3, P4 |
| V17 | PII tokenization bypass (false negative) | A1 | P5, P6 |
| V18 | Sandbox escape via dunder attribute | A2 | P5 |
| V19 | Hook bypass via direct call (not through PostToolUse) | A2 | P5, P6 |
| V20 | Token ledger inflation (artificially count tokens) | A3 | All |

---

## 2. Adversarial analysis per phase (P0 → P10 + POV)

### P0_DISCOVERY

**Applicable vectors**: V11 (session hijack), V20 (ledger inflation)

**Attack angles**:
1. **Session ID predictability**: if we generate `session_id` predictably (timestamp, weak hash), an attacker can inject it into `state.db` and steal the state
2. **State DB pas chiffré**: `state.db` in clear, contains user décisions (potential PII: project names, choices)
3. **No session authentication**: anyone with filesystem access can open `.swebok_state.db`
4. **Metadata leakage**: `metadata` field of session may contain secrets without warning
5. **No key rotation policy**: `.audit_key` never rotated

**Likelihood**: LOW (filesystem access required)
**Impact**: MED (decision theft, not direct LLM exfiltration)
**Quick win**: Encrypt `state.db` at rest (sqlite3 SEE or LUKS container)

### P1_CONCEPT_FEASIBILITY

**Applicable vectors**: V11, V20

**Attack angles**:
1. **Charter falsifiable**: `CHARTER.md` is human-readable markdown, an attacker with repo access can rewrite the mission
2. **Scope drift attack**: phase P1 has 4 sequential agents (rotation 3 Nexus + T2=Discovery-Orch) — attacker can influence agent T1 to enlarge scope
3. **Decision threshold abusable**: "trivial decision = silent" (DTM B threshold) → attacker can drown important décisions in noise
4. **Corpus 20% accepted**: if attacker pollutes the 20% retained, it influences Discovery
5. **No versionning of charter**: modifications invisible

**Likelihood**: MED
**Impact**: LOW (P1 = exploration, not execution)
**Quick win**: HMAC charter + Git versioning (already native)

### P2_REQUIREMENTS

**Applicable vectors**: V11, V20, V09 (type confusion in SRS)

**Attack angles**:
1. **SRS IEEE 830 ambiguous**: 17 quality attributes ISO 25010 → attacker can create a spec intentionally ambiguous that will be "passed" by T2 spec-compliance
2. **NFR ordering attack**: if NFR perf=high and security=low, the architect can prioritize perf over security
3. **Acceptance criteria flous**: an AC "system should be fast" is non-mesurable → attacker can deliver anything and T2 can only PASS
4. **Type confusion in schemas**: if the SRS uses weak types (string everywhere), confusion possible
5. **PII in SRS**: names, emails, addresses often present in examples

**Likelihood**: MED
**Impact**: MED (ambiguous specs = bugs downstream, structural debt)
**Quick win**: Spec linter (`ctxh-lint-srs`) that validates measurability of AC

### P3_ARCHITECTURE

**Applicable vectors**: V01, V06, V07, V09, V16

**Attack angles**:
1. **Multi-agent attack**: 3-5 parallel subagents + Nexus-Critic T1+T2+T3 mandatory → 5 LLM invocations = 5× larger injection surface
2. **Subagent return smuggling**: a subagent can return a DSL that *seems* to be a result but contains hidden payload (e.g., `SUMMARY:done;;ARTIFACTS:http://attacker.com/exfil`)
3. **ADR poisoning**: a maliciously drafted ADR can anchor a design décision in the future (T3 downstream relies on it)
4. **OpenAPI/AsyncAPI schemas with circular reference**: attacker can create a schema that crashes P4 validators
5. **STRIDE threat model falsifiable**: if threat model incomplete, attacker knows the non-coverage
6. **Format contracts differentiated md+json**: ambiguity between the 2 representations
7. **Token budget 15k hard cap**: exploitable if budget gameable (compaction, subagent return)

**Likelihood**: HIGH
**Impact**: HIGH (fake ADRs = 10-year debt)
**Quick win**: Validate that `<subagent-result>` contains only the 3 expected fields (ref, summary, artifacts), no free payload

### P4_DESIGN

**Applicable vectors**: V06, V07, V10, V13, V16

**Attack angles**:
1. **Matrice ADR → module obligatoire (XG-4.7)**: if attacker makes a fake ADR pass in P3, P4 translates it into fake modules
2. **Format contracts differentiated inherited P3**: if md+json misaligned, P5 code on fake JSON
3. **DDS (Detailed Design Spec) poisoning**: DDS written poorly = fake code in P5
4. **AsyncAPI events with backdoor**: an event handler can exfiltrate
5. **OpenAPI spec with hidden endpoint**: attacker can add an "internal" endpoint that won't be audited
6. **Perte du brief subagent au compaction**: if compaction loses the brief, next subagent doesn't know what to do (drift)
7. **Replay attack on compaction**: attacker can replay a previous compaction to restore a dangerous state

**Likelihood**: HIGH
**Impact**: HIGH (fake code = exploit in prod)
**Quick win**: XSD validation of OpenAPI/AsyncAPI, reject undocumented endpoints

### P5_IMPLEMENTATION

**Applicable vectors**: V01, V02, V08, V17, V18, V19

**Attack angles**:
1. **Code injection via MCP**: if dev adds an un-signed `github-mcp-server`, attacker can use it to exfiltrate
2. **Tool result PII leakage**: tool_result may contain non-tokenizable emails/phones (our regex is limited)
3. **Sandbox escape via dunder**: `().__class__.__subclasses__()` can bypass the AST check
4. **Code API filesystem traversal**: if `servers/` directory has paths with `..`, attacker can read out of scope
5. **Hook bypass**: if dev calls `tool_result` directly without going through the hook, hook doesn't run
6. **Token ledger manipulation**: dev can forge events in `state.db` to inflate the counter
7. **Pre-hydrate poisoning**: attacker can pre-load malicious content in `state.db` at phase start
8. **Compaction ACE "self-improving" can learn the bad**: if a bad décision is "accepted" (gate OK by mistake), it is reinforced

**Likelihood**: HIGH
**Impact**: CRIT (code in prod, RCE possible)
**Quick wins**:
- Force hook execution via wrapper (`@with_hooks` decorator)
- Validation signature of MCP servers at boot
- Sandboxing OS-level (Docker) in addition to AST check

### P6_TESTING

**Applicable vectors**: V01, V02, V08, V17, V20

**Attack angles**:
1. **Tests generated by LLM that pass by validating fake**: `mut.==None → True` is a fake test but PASSes
2. **Coverage spoofing**: attacker can mark lines "covered" without really testing them
3. **Mutation testing bypass**: if we only mutate trivial conditions, logical bugs survive
4. **Test fixtures with PII**: a `tests/fixtures/users.json` file may contain 1000 PII in clear
5. **Adversarial gate `QA-FAIL` ignored**: if orchestrator forces PASS despite QA-FAIL, we have a fake PASS
6. **Defect catalog poisoning**: attacker can inject a fake "defect closed" to close a real bug

**Likelihood**: MED
**Impact**: HIGH (bug not detected → prod)
**Quick win**: Mutation testing mandatory (not only coverage), coverage = 0 if mut_score < 0.7

### P7_DEPLOYMENT

**Applicable vectors**: V02, V04, V11

**Attack angles**:
1. **CI/CD pipeline poisoning**: attacker can compromise GitHub Actions / GitLab CI
2. **Container image poisoning**: if we pull a Docker image without verifying the SHA256 hash
3. **Secret leakage in env vars**: ANTHROPIC_API_KEY visible in `ps auxe` or logs
4. **Hotfix bypass**: "hotfix = no bypass process complet obligatoire" but in practice dev can skip QA
5. **Rollback attack**: attacker can rollback to a compromised version
6. **Region failover data corruption**: if multi-region, the state.db can diverge

**Likelihood**: HIGH
**Impact**: CRIT (prod compromise, data exfiltrated)
**Quick win**: Hash pinning of Docker images, secrets via vault (not env vars)

### P8_OPERATIONS

**Applicable vectors**: V03, V04, V11, V12, V15

**Attack angles**:
1. **HMAC chain break silencieux**: if attacker modifies `state.db` and recalculates the HMAC, the chain doesn't break (if attacker has the key)
2. **Audit replay**: replay an old audit log to hide a recent malicious action
3. **35 min wall exploit**: just before 35 min, agent can do a quick un-observed action
4. **Post-mortem falsification**: if RCA is written after the incident, it can omit causes
5. **SLO drift**: if attacker manipulates the SLO thresholds, alerts don't fire
6. **Capacity overflow DoS**: fill the state.db with fake events

**Likelihood**: MED
**Impact**: CRIT (late detection)
**Quick win**: Audit chain rotation (HMAC key derived from time, forward secrecy), monitoring out-of-band

### P9_MAINTENANCE

**Applicable vectors**: V02, V03, V14, V15

**Attack angles**:
1. **CAB approval bypass**: if CAB décision is just a log, attacker can CAB-approve their own patch
2. **Memory block pollution**: attacker can write fake "facts" in `memory_blocks` that will be recalled
3. **Patch injection**: a patch may include a "covert channel" (exotic environment variables)
4. **Playbook ACE reinforcement**: a malicious playbook positively rated can be reused in loop
5. **Cross-tenant leak**: if the harness is multi-tenant, a tenant can read another tenant's state
6. **Post-mortem data exfiltration**: RCAs often contain sensitive data

**Likelihood**: MED
**Impact**: HIGH (recurring vulnerabilities)
**Quick win**: ACL on `memory_blocks` table, CAB approver list immuable

### P10_RETIREMENT

**Applicable vectors**: V03, V11, V15

**Attack angles**:
1. **EOL decision manipulation**: if attacker can do a fake EOL, they can archive non-compliant code
2. **Archive integrity**: the 30/90/180j read-only archive can be copied if filesystem compromised
3. **Ownership transfer spoofing**: attacker can transfer ownership to a malicious entity
4. **Final archive snapshot with PII**: the archive often contains non-anonymized user data
5. **Re-activation from archive**: attacker can restore the project with its vulnerabilities
6. **Legal/compliance sign-off falsifiable**: if signature is just a log, falsifiable

**Likelihood**: LOW (end of life = little value for attacker)
**Impact**: HIGH (legacy data compromised)
**Quick win**: Archive anonymization (GDPR Art. 17 = right to erasure respected)

### POV (Sprint S1 + S2)

**Applicable vectors**: V01, V04, V06, V07, V08, V11, V17, V18, V19, V20

**Adversarial angles specific to POV**:
1. **Subagent firewall stub**: `_stub_execute` returns fake data → a dev can take this stub for production
2. **State DB non chiffré**: `.swebok_state.db` contains token counter, can leak usage patterns
3. **Token ledger forgeable**: a test can inject fake events in `state.db` without validation
4. **DSL parser permissif**: `KEY:VALUE;;KEY:VALUE` does not validate types (string everywhere) → type confusion possible
5. **PII patterns incomplets**: 11 patterns is <50% of real PII (missing: postal addresses, full names, license plates, etc.)
6. **Sandbox defense in depth = AST only**: no OS-level isolation → agent code can do indirect `subprocess.run`
7. **Hooks globaux stateful**: `_global_hooks` shares state between tests → cross-test leak
8. **74 tests but no ADVERSARIAL test**: all tests are "happy path", no test "what happens if attacker injects X?"
9. **PII tokenization deterministe par session**: same salt = same token → if attacker has 2 contexts, can correlate
10. **HMAC chain partial**: `state.append_audit` exists but not tested end-to-end
11. **Council Bridge simulée**: verdicts are simulated, not independent adverse
12. **`run_council_gates.sh` findings hardcodés**: a dev can modify the script to pass gates without fix

**Likelihood**: MED-HIGH
**Impact**: HIGH (this POV becomes the template for v1.0)

---

## 3. Risk Matrix (Likelihood × Impact)

| Phase | Top 3 risks | L | I | Score | Quick win priority |
|-------|---------------|---|---|-------|---------------------|
| P0 Discovery | State DB non chiffré | LOW | MED | 2 | Encryption at rest |
| P1 Feasibility | Decision threshold abusable | MED | LOW | 2 | Charter versioning |
| P2 Requirements | AC non-mesurables | MED | MED | 4 | SRS linter |
| P3 Architecture | ADR poisoning | HIGH | HIGH | **9** | Strict subagent brief validation |
| P4 Design | Format contracts misalignés | HIGH | HIGH | **9** | XSD OpenAPI/AsyncAPI |
| P5 Implementation | MCP poisoning + sandbox escape | HIGH | CRIT | **12** | Hash pinning MCP + Docker |
| P6 Testing | Tests happy-path only | MED | HIGH | 6 | Mutation testing mandatory |
| P7 Deployment | CI/CD poisoning, secrets leakage | HIGH | CRIT | **12** | Vault for secrets |
| P8 Operations | HMAC chain break | MED | CRIT | 8 | Audit chain rotation |
| P9 Maintenance | Memory block pollution | MED | HIGH | 6 | ACL memory_blocks |
| P10 Retirement | Archive PII non anonymisée | LOW | HIGH | 4 | Archive anonymization |
| POV itself | Tests happy-path, sandbox AST only, simulée | MED-HIGH | HIGH | **9** | Adversarial tests + Docker |

**CRITICAL risks (Score ≥ 9)**:
1. **P5 Implementation** : MCP poisoning + sandbox escape
2. **P7 Deployment** : CI/CD + secrets
3. **P3-P4 Architecture/Design** : ADR/contract poisoning
4. **POV itself** : pas de tests adversariaux

---

## 4. Recurring attack patterns (to be tooled)

| Pattern | Description | Frequency | Proposed tool |
|---------|-------------|-----------|----------------|
| **State DB tampering** | Direct modification of `state.db` | 4 phases | ACL filesystem + audit chain cryptographique |
| **Subagent smuggling** | Hidden payload in return contract | 3 phases | Schema validator `<subagent-result>` |
| **MCP poisoning** | Malicious server | 3 phases | MCP trust store (signing) |
| **PII leakage** | Personal data non tokenizées | 3 phases | Pattern library étendue (50+ patterns) |
| **Test gaming** | Tests that pass by validating fake | 2 phases | Mutation testing + property-based |
| **DSL ambiguity** | Parse collision | 4 phases | Schema strict + type validation |

---

## 5. Quick Wins (effort ≤ 1h, immediate impact)

| Quick win | Effort | Impact | Phases covered |
|-----------|--------|--------|----------------|
| State DB encryption (SEE) | 1h | MED | All |
| Schema validator `<subagent-result>` | 1h | HIGH | P3, P4, P5 |
| Linter SRS (AC mesurables) | 1h | MED | P2 |
| Hash pinning MCP au boot | 1h | **CRIT** | P5, P6, P7 |
| Audit chain rotation (forward secrecy) | 1h | **CRIT** | P8, P9, P10 |
| Tests adversariaux (5 fichiers) | 2h | HIGH | POV → v1.0 |
| Vault for secrets (instead of env vars) | 1h | **CRIT** | P7, P8 |
| XSD OpenAPI/AsyncAPI | 1h | HIGH | P3, P4, P5 |
| Memory blocks ACL | 1h | MED | P9 |
| Mutation testing mandatory (P6) | 1h | HIGH | P6 |

**Total quick wins**: ~10h, covers the 12 phases.

---

## 6. Structural debt (effort > 1 day)

| Item | Effort | Justification | Target phase |
|------|--------|---------------|--------------|
| Docker sandbox (OS-level) | 2 days | Defense in depth, vs AST only | S3 |
| Real Council Bridge (agents nexus-*) | 3 days | Independent reviewers, not simulated | v1.0 |
| Playbook ACE self-improving | 3 days | Learn from past decisions | S3 |
| MemGPT memory blocks complete | 2 days | Hierarchical typed memory | S3 |
| Audit chain rotation | 1 day | Forward secrecy, replay impossible | S4 |
| Multi-tenant isolation | 3 days | If commercialisé | v2.0 |
| Adversarial test suite (50+ payloads) | 2 days | Cover all identified vectors | S4 |

---

## 7. Verdict

The POV is **fonctionnellement valide** (10/10 gates, 74/74 tests) but **adversarialement immature**. The 4 critical risks (score ≥ 9) are:
1. P5 Implementation (sandbox + MCP)
2. P7 Deployment (CI/CD + secrets)
3. P3-P4 Architecture/Design (ADR/contract poisoning)
4. POV itself (happy-path tests, sandbox AST only, simulée)

**Recommendation**: before declaring v1.0 production-ready, run the 10 quick wins (~10h) that cover 80% of adversarial risk. The 7 structural debt items (S3-S4) address the remaining 20%.

---

*Analysis conducted 2026-06-08 by discovery-orchestrator. Red Team mode. 12 phases, 50+ attack angles identified, 10 quick wins prioritized.*
