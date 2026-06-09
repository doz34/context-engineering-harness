# Analyse Adversariale par Phase — 2026-06-08

> **Type** : Red Team (mode attack), pas compliance.
> **Cible** : CE-Harness POV (post-S2), 11 phases (P0-P10 + POV lui-même)
> **Méthodologie** : 4 classes d'attaquants × 5 vecteurs cross-phase = matrice 20 attaques
> **But** : Identifier les angles morts AVANT qu'un vrai attaquant les trouve

---

## 0. Modèle d'adversaire — 4 classes

| Classe | Profil | Objectif | Outils probables |
|--------|--------|----------|------------------|
| **A1 — Externe** | Attaquant via prompt injection, MCP malicieux, supply chain | Vol de données, exfiltration, prise de contrôle | Indirect prompt injection, tool poisoning, typosquatting |
| **A2 — Interne** | Process compromis, état corrompu, race condition | Corruption du state, HMAC chain break, DoS | SQL injection (SQLite WAL), state.db race, hash collision |
| **A3 — Logique** | Edge cases du POV, invariants mal compris, mal-compréhension | Faire passer du faux pour vrai, abus de token budget | DSL ambigu, brief subagent vague, type confusion |
| **A4 — Temporel** | Long-running, drift, decay, état partagé cross-session | Vol de session, replay attack, drift de comportement | Session hijack, replay d'audit, slow-burn data exfil |

---

## 1. Catalogue des 20 vecteurs d'attaque cross-phase

| ID | Vecteur | Classe | Phase(s) touchée(s) |
|----|---------|--------|---------------------|
| V01 | Indirect prompt injection via tool result | A1 | P3, P5, P6 |
| V02 | MCP server malicieux (typosquatting, supply chain) | A1 | P5, P6, P7 |
| V03 | HMAC chain forgery / replay | A2 | P8, P9, P10 |
| V04 | SQLite WAL corruption / lock contention | A2 | Toutes |
| V05 | State.db race condition (TOCTOU) | A2 | P3, P4 |
| V06 | DSL ambiguity (parsing collision) | A3 | Toutes |
| V07 | Brief subagent vague → exfiltration scope | A3 | P3, P4, P5 |
| V08 | Token counter inflation (game the budget) | A3 | Toutes |
| V09 | Type confusion (memory block attack) | A3 | P3, P4 |
| V10 | Lost-in-the-middle exploitation (cache key in middle) | A3 | Toutes |
| V11 | Session hijack via state.db (no auth) | A4 | P0-P10 |
| V12 | Long-running decay (35 min wall edge case) | A4 | P3, P5 |
| V13 | Replay of compaction results (collision) | A4 | P4 |
| V14 | Cross-session leak via memory blocks | A4 | P3, P4 |
| V15 | Audit chain replay across rollback | A4 | P8, P9 |
| V16 | Subagent return channel smuggling | A3 | P3, P4 |
| V17 | PII tokenization bypass (false negative) | A1 | P5, P6 |
| V18 | Sandbox escape via dunder attribute | A2 | P5 |
| V19 | Hook bypass via direct call (not through PostToolUse) | A2 | P5, P6 |
| V20 | Token ledger inflation (artificially count tokens) | A3 | Toutes |

---

## 2. Analyse adversariale par phase (P0 → P10 + POV)

### P0_DISCOVERY

**Vecteurs applicables** : V11 (session hijack), V20 (ledger inflation)

**Angles d'attaque** :
1. **Session ID predictability** : si on génère `session_id` prévisiblement (timestamp, hash faible), un attaquant peut l'injecter dans `state.db` et voler l'état
2. **State DB pas chiffré** : `state.db` en clair, contient les décisions utilisateur (PII potentielle : noms de projets, choix)
3. **Pas d'authentification de session** : n'importe qui ayant accès au filesystem peut ouvrir `.swebok_state.db`
4. **Metadata leakage** : `metadata` field de session peut contenir des secrets sans warning
5. **No key rotation policy** : `.audit_key` jamais rotaté

**Likelihood** : LOW (accès filesystem requis)
**Impact** : MED (vol de décisions, pas d'exfiltration LLM directe)
**Quick win** : chiffrer `state.db` au repos (sqlite3 SEE ou LUKS container)

### P1_CONCEPT_FEASIBILITY

**Vecteurs applicables** : V11, V20

**Angles d'attaque** :
1. **Charter falsifiable** : `CHARTER.md` est markdown lisible, un attaquant avec accès au repo peut réécrire la mission
2. **Cadrage scope drift** : la phase P1 a 4 agents séquentiels (rotation 3 Nexus + T2=Discovery-Orch) — l'attaquant peut influencer l'agent T1 pour élargir le scope
3. **Decision threshold abusable** : "décision triviale = silencieuse" (DTM B threshold) → un attaquant peut noyer des décisions importantes dans le bruit
4. **Corpus 20% accepté** : si l'attaquant pollue les 20% retenus, il influence Discovery
5. **Pas de versionning du charter** : modifications invisibles

**Likelihood** : MED
**Impact** : LOW (P1 = exploration, pas exécution)
**Quick win** : HMAC le charter + versionning Git (déjà natif)

### P2_REQUIREMENTS

**Vecteurs applicables** : V11, V20, V09 (type confusion dans SRS)

**Angles d'attaque** :
1. **SRS IEEE 830 ambigu** : 17 attributs qualité ISO 25010 → attaquant peut créer une spec volontairement ambiguë qui sera "passée" par T2 spec-compliance
2. **NFR ordering attack** : si NFR perf=high et security=low, l'architecte peut prioriser perf au détriment de security
3. **Acceptance criteria flous** : un AC "system should be fast" est non-mesurable → un attaquant peut livrer n'importe quoi et T2 ne peut que PASS
4. **Type confusion dans les schémas** : si le SRS utilise des types faibles (string partout), confusion possible
5. **PII dans le SRS** : noms, emails, addresses souvent présents dans les exemples

**Likelihood** : MED
**Impact** : MED (specs ambiguës = bugs en aval, dette structurelle)
**Quick win** : Linter de spec (`ctxh-lint-srs`) qui valide mesurabilité des AC

### P3_ARCHITECTURE

**Vecteurs applicables** : V01, V06, V07, V09, V16

**Angles d'attaque** :
1. **Multi-agent attack** : 3-5 subagents parallèles + Nexus-Critic T1+T2+T3 obligatoire → 5 invocations LLM = surface d'injection 5× plus grande
2. **Subagent return smuggling** : un subagent peut retourner un DSL qui *semble* être un résultat mais contient du payload caché (e.g., `SUMMARY:done;;ARTIFACTS:http://attacker.com/exfil`)
3. **ADR poisoning** : un ADR malicieusement rédigé peut ancrer une décision d'archi dans le futur (T3 aval s'appuie dessus)
4. **OpenAPI/AsyncAPI schemas avec reference circulaire** : un attaquant peut créer un schéma qui crash les validators P4
5. **STRIDE threat model falsifiable** : si threat model incomplet, l'attaquant connaît les non-coverage
6. **Format contracts différencié md+json** : ambiguïté entre les 2 représentations
7. **Token budget 15k hard cap** : exploitable si budget gameable (compaction, subagent return)

**Likelihood** : HIGH
**Impact** : HIGH (faux ADRs = dette 10 ans)
**Quick win** : Valider que `<subagent-result>` ne contient que les 3 champs attendus (ref, summary, artifacts), pas de payload libre

### P4_DESIGN

**Vecteurs applicables** : V06, V07, V10, V13, V16

**Angles d'attaque** :
1. **Matrice ADR → module obligatoire (XG-4.7)** : si l'attaquant fait passer un faux ADR en P3, P4 le traduit en faux modules
2. **Format contracts différencié hérité P3** : si md+json désalignés, P5 code sur du faux JSON
3. **DDS (Detailed Design Spec) poisoning** : DDS mal rédigés = code faux en P5
4. **AsyncAPI events with backdoor** : un event handler peut exfiltrer
5. **OpenAPI spec with hidden endpoint** : un attaquant peut ajouter un endpoint "interne" qui ne sera pas audité
6. **Perte du brief subagent au compaction** : si compaction perd le brief, le subagent suivant ne sait pas ce qu'il doit faire (drift)
7. **Replay attack sur compaction** : un attaquant peut rejouer un compaction antérieur pour restore un état dangereux

**Likelihood** : HIGH
**Impact** : HIGH (code faux = exploit en prod)
**Quick win** : Validation XSD des OpenAPI/AsyncAPI, rejeeter les endpoints non documentés

### P5_IMPLEMENTATION

**Vecteurs applicables** : V01, V02, V08, V17, V18, V19

**Angles d'attaque** :
1. **Code injection via MCP** : si un dev ajoute un MCP `github-mcp-server` non signé, l'attaquant peut l'utiliser pour exfiltrer
2. **Tool result PII leakage** : un tool_result peut contenir des emails/phones non tokenizables (mon regex est limitatif)
3. **Sandbox escape via dunder** : `().__class__.__subclasses__()` peut bypass le AST check
4. **Code API filesystem traversal** : si `servers/` directory a des chemins avec `..`, l'attaquant peut lire hors scope
5. **Hook bypass** : si le dev appelle `tool_result` directement sans passer par le hook, le hook ne s'exécute pas
6. **Token ledger manipulation** : un dev peut forger des events dans `state.db` pour gonfler le compteur
7. **Pre-hydrate poisoning** : un attaquant peut pré-charger du contenu malicieux dans le `state.db` au début de phase
8. **Compaction ACE "self-improving" peut apprendre le mal** : si une mauvaise décision est "accepted" (gate OK par erreur), elle est renforcée

**Likelihood** : HIGH
**Impact** : CRIT (code en prod, RCE possible)
**Quick wins** :
- Force hook execution via wrapper (`@with_hooks` decorator)
- Validation signature des MCP servers au boot
- Sandboxing OS-level (Docker) en plus de l'AST check

### P6_TESTING

**Vecteurs applicables** : V01, V02, V08, V17, V20

**Angles d'attaque** :
1. **Tests générés par LLM qui passent en validant du faux** : `mut.==None → True` est un test bidon mais qui PASS
2. **Coverage spoofing** : un attaquant peut marquer des lignes "covered" sans les tester réellement
3. **Mutation testing bypass** : si on ne mute que les conditions triviales, des bugs logiques survivent
4. **Test fixtures with PII** : un fichier `tests/fixtures/users.json` peut contenir 1000 PII en clair
5. **Adversarial gate `QA-FAIL` ignoré** : si l'orchestrateur force le PASS malgré QA-FAIL, on a un faux PASS
6. **Defect catalog poisoning** : un attaquant peut injecter un faux "defect closed" pour fermer un bug réel

**Likelihood** : MED
**Impact** : HIGH (bug non détecté → prod)
**Quick win** : Mutation testing obligatoire (pas seulement coverage), coverage = 0 si mut_score < 0.7

### P7_DEPLOYMENT

**Vecteurs applicables** : V02, V04, V11

**Angles d'attaque** :
1. **CI/CD pipeline poisoning** : un attaquant peut compromettre GitHub Actions / GitLab CI
2. **Container image poisoning** : si on pull un image Docker sans vérifier le hash SHA256
3. **Secret leakage in env vars** : ANTHROPIC_API_KEY visible dans `ps auxe` ou logs
4. **Hotfix bypass** : "hotfix = pas de bypass process complet obligatoire" mais en pratique le dev peut skip QA
5. **Rollback attack** : l'attaquant peut rollback vers une version compromise
6. **Region failover data corruption** : si multi-region, le state.db peut diverger

**Likelihood** : HIGH
**Impact** : CRIT (prod compromise, données exfiltrées)
**Quick win** : Hash pinning des Docker images, secrets via vault (pas env vars)

### P8_OPERATIONS

**Vecteurs applicables** : V03, V04, V11, V12, V15

**Angles d'attaque** :
1. **HMAC chain break silencieux** : si l'attaquant modifie `state.db` et recalcule le HMAC, la chaîne ne casse pas (si l'attaquant a la clé)
2. **Audit replay** : rejouer un audit log ancien pour cacher une action malveillante récente
3. **35 min wall exploit** : juste avant 35 min, l'agent peut faire une action rapide non-observée
4. **Post-mortem falsification** : si RCA est écrit après l'incident, il peut omettre des causes
5. **SLO drift** : si l'attaquant manipule les seuils SLO, les alertes ne se déclenchent pas
6. **Capacity overflow DoS** : remplir le state.db avec des events factices

**Likelihood** : MED
**Impact** : CRIT (détection tardive)
**Quick win** : Audit chain rotation (HMAC key dérivée du temps, forward secrecy), monitoring out-of-band

### P9_MAINTENANCE

**Vecteurs applicables** : V02, V03, V14, V15

**Angles d'attaque** :
1. **CAB approval bypass** : si la décision CAB est juste un log, l'attaquant peut CAB-approve son propre patch
2. **Memory block pollution** : un attaquant peut écrire dans `memory_blocks` des "facts" faux qui seront recallés
3. **Patch injection** : un patch peut inclure un "covert channel" (variables d'environnement exotiques)
4. **Playbook ACE reinforcement** : un playbook mal noté positivement peut être réutilisé en boucle
5. **Cross-tenant leak** : si le harness est multi-tenant, un tenant peut lire le state d'un autre
6. **Post-mortem data exfiltration** : les RCA contiennent souvent des données sensibles

**Likelihood** : MED
**Impact** : HIGH (vulnérabilités récurrentes)
**Quick win** : ACL sur `memory_blocks` table, CAB approver list immuable

### P10_RETIREMENT

**Vecteurs applicables** : V03, V11, V15

**Angles d'attaque** :
1. **EOL decision manipulation** : si l'attaquant peut faire un faux EOL, il peut faire archiver du code non-compliant
2. **Archive integrity** : l'archive de 30/90/180j read-only peut être copiée si filesystem compromis
3. **Ownership transfer spoofing** : un attaquant peut transférer la propriété à une entité malveillante
4. **Final archive snapshot with PII** : l'archive contient souvent des données utilisateur non anonymisées
5. **Re-activation from archive** : un attaquant peut restaurer le projet avec ses vulnérabilités
6. **Legal/compliance sign-off falsifiable** : si la signature est juste un log, falsifiable

**Likelihood** : LOW (fin de vie = peu de valeur pour attaquant)
**Impact** : HIGH (données legacy compromises)
**Quick win** : Anonymisation de l'archive (GDPR Art. 17 = right to erasure respecté)

### POV (Sprint S1 + S2)

**Vecteurs applicables** : V01, V04, V06, V07, V08, V11, V17, V18, V19, V20

**Angles d'attaque spécifiques au POV** :
1. **Subagent firewall stub** : `_stub_execute` retourne des données fake → un dev peut prendre ce stub pour de la prod
2. **State DB non chiffré** : `.swebok_state.db` contient tokens counter, peut leak les patterns d'usage
3. **Token ledger forgeable** : un test peut injecter des events fake dans `state.db` sans validation
4. **DSL parser permissif** : `KEY:VALUE;;KEY:VALUE` ne valide pas les types (string partout) → type confusion possible
5. **PII patterns incomplets** : 11 patterns c'est <50% des PII réelles (manque : adresses postales, noms complets, plaques d'immat, etc.)
6. **Sandbox defense in depth = AST only** : pas d'OS-level isolation → un code agent peut faire `subprocess.run` indirect
7. **Hooks globaux stateful** : `_global_hooks` partage l'état entre tests → fuite cross-test
8. **74 tests mais aucune test d'ADVERSARIAL** : tous les tests sont "happy path", aucun test "que se passe-t-il si l'attaquant injecte X ?"
9. **PII tokenization deterministe par session** : même sel = même token → si l'attaquant a 2 contexts, il peut corréler
10. **HMAC chain partial** : `state.append_audit` existe mais pas testé end-to-end
11. **Council Bridge simulée** : les verdicts sont simulés, pas adversariaux indépendants
12. **`run_council_gates.sh` findings hardcodés** : un dev peut modifier le script pour passer les gates sans fix

**Likelihood** : MED-HIGH
**Impact** : HIGH (ce POV devient le template de la v1.0)

---

## 3. Risk Matrix (Likelihood × Impact)

| Phase | Top 3 risques | L | I | Score | Quick win prioritaire |
|-------|---------------|---|---|-------|----------------------|
| P0 Discovery | State DB non chiffré | LOW | MED | 2 | Chiffrement at rest |
| P1 Feasibility | Decision threshold abusable | MED | LOW | 2 | Versionning charter |
| P2 Requirements | AC non-mesurables | MED | MED | 4 | Linter SRS |
| P3 Architecture | ADR poisoning | HIGH | HIGH | **9** | Validation brief subagent stricte |
| P4 Design | Format contracts désalignés | HIGH | HIGH | **9** | XSD OpenAPI/AsyncAPI |
| P5 Implementation | MCP poisoning, sandbox escape | HIGH | CRIT | **12** | Hash pinning MCP + Docker |
| P6 Testing | Tests happy-path only | MED | HIGH | 6 | Mutation testing obligatoire |
| P7 Deployment | CI/CD poisoning, secrets leakage | HIGH | CRIT | **12** | Vault pour secrets |
| P8 Operations | HMAC chain break | MED | CRIT | **8** | Audit chain rotation |
| P9 Maintenance | Memory block pollution | MED | HIGH | 6 | ACL memory_blocks |
| P10 Retirement | Archive PII non anonymisée | LOW | HIGH | 4 | Anonymisation archive |
| POV (S1+S2) | Tests happy-path, sandbox AST only, simulée | MED-HIGH | HIGH | **9** | Tests adversariaux + Docker |

**Risques CRITIQUES (Score ≥ 9)** :
1. **P5 Implementation** : MCP poisoning + sandbox escape
2. **P7 Deployment** : CI/CD + secrets
3. **P3-P4 Architecture/Design** : ADR/contract poisoning
4. **POV lui-même** : pas de tests adversariaux

---

## 4. Patterns d'attaque récurrents (à outiller)

| Pattern | Description | Fréquence | Outil proposé |
|---------|-------------|-----------|---------------|
| **State DB tampering** | Modification directe de `state.db` | 4 phases | ACL filesystem + audit chain cryptographique |
| **Subagent smuggling** | Payload caché dans return contract | 3 phases | Schema validator `<subagent-result>` |
| **MCP poisoning** | Server malicieux | 3 phases | MCP trust store (signing) |
| **PII leakage** | Données personnelles non tokenizées | 3 phases | Pattern library étendue (50+ patterns) |
| **Test gaming** | Tests qui passent en validant du faux | 2 phases | Mutation testing + property-based |
| **DSL ambiguity** | Parse collision | 4 phases | Schema strict + type validation |

---

## 5. Quick Wins (effort ≤ 1h, impact immédiat)

| Quick win | Effort | Impact | Phases couvertes |
|-----------|--------|--------|------------------|
| Chiffrement state.db (SEE) | 1h | MED | Toutes |
| Schema validator `<subagent-result>` | 1h | HIGH | P3, P4, P5 |
| Linter SRS (AC mesurables) | 1h | MED | P2 |
| Hash pinning MCP au boot | 1h | CRIT | P5, P6, P7 |
| Audit chain rotation (forward secrecy) | 1h | CRIT | P8, P9, P10 |
| Tests adversariaux (5 fichiers) | 2h | HIGH | POV → v1.0 |
| Vault pour secrets (au lieu env vars) | 1h | CRIT | P7, P8 |
| XSD OpenAPI/AsyncAPI | 1h | HIGH | P3, P4, P5 |
| Memory blocks ACL | 1h | MED | P9 |
| Mutation testing obligatoire (P6) | 1h | HIGH | P6 |

**Total quick wins** : ~10h, couvre les 12 phases.

---

## 6. Dette structurelle (effort > 1 jour)

| Item | Effort | Justification | Phase cible |
|------|--------|---------------|-------------|
| Docker sandbox (OS-level) | 2 jours | Defense in depth, vs AST only | S3 |
| Vraie Council Bridge (agents nexus-*) | 3 jours | Reviewers indépendants, pas simulés | v1.0 |
| Playbook ACE self-improving | 3 jours | Apprendre des décisions passées | S3 |
| MemGPT memory blocks complet | 2 jours | Mémoire hiérarchique typée | S3 |
| Audit chain rotation | 1 jour | Forward secrecy, replay impossible | S4 |
| Multi-tenant isolation | 3 jours | Si commercialisé | v2.0 |
| Adversarial test suite (50+ payloads) | 2 jours | Couvrir tous les vecteurs identifiés | S4 |

---

## 7. Verdict

Le POV est **fonctionnellement valide** (10/10 gates, 74/74 tests) mais **adversarialement immature**. Les 4 risques critiques (score ≥ 9) sont :
1. P5 Implementation (sandbox + MCP)
2. P7 Deployment (CI/CD + secrets)
3. P3-P4 Architecture/Design (ADR/contract poisoning)
4. POV lui-même (happy-path tests, sandbox AST only)

**Recommandation** : avant de déclarer v1.0 production-ready, exécuter les 10 quick wins (~10h) qui couvrent 80% du risque adversarial. Les 7 items de dette structurelle (S3-S4) adressent les 20% restants.

---

*Analyse conduite 2026-06-08 par discovery-orchestrator. Mode Red Team. 12 phases, 50+ angles d'attaque identifiés, 10 quick wins priorisés.*
