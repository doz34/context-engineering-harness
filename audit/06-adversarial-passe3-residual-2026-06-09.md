# Adversarial Passe 3 — Résiduel MED (2026-06-09)

> **Date** : 2026-06-09
> **Cible** : CE-Harness POV post-S3 (0 CRIT, 8 MED restants)
> **But** : Implémenter les 8 MED restants + identifier les nouveaux gaps
> **Verdict attendu** : 0 CRIT, ≤2 MED à la fin de S3-2

---

## 0. État actuel (post-S3)

| Métrique | Passe 1 | Passe 2 | **Passe 3 (départ)** |
|----------|---------|---------|---------------------|
| Risques CRIT (≥ 9) | 5 | 1 | **0** |
| Risques MED (4-8) | 5 | 9 | **8** |
| Score max | 12/12 | 7/12 | **4/12 (P10)** |
| Tests adversariaux | 0 | 55 | **77** |
| Tests totaux | 74 | 197 | **263** |

**8 MED restants** (passe 2 → passe 3) :
1. R3 — Archive PII anonymisation GDPR (P10, 4/12)
2. R4 — OS-level sandbox Docker (P5, 4/12)
3. R5 — State.append_audit → RotatingHMAC (P8, 3/12)
4. R6 — Adversarial payload corpus 50+ (P6, 2/12)
5. R7 — Property-based testing Hypothesis (P6, 2/12)
6. R8 — Per-tenant key encryption (P9, 2/12)
7. R9 — CAB approver immutability (P9, 2/12)
8. R10 — EOL decision HMAC (P10, 4/12)

**Nouveaux risques introduits par S3** (effet secondaire) :
- S3-N1 — `lib/ci_cd_pinning.py` : TOFU sur registry (si la registry est compromise, le digest pinned est faux)
- S3-N2 — `lib/image_pin.py` : `subprocess.run(["skopeo", "inspect"])` peut être lent / DoS / hanging
- S3-N3 — `pin_to_digest` dépend de la disponibilité de `skopeo` ou `docker` CLI

---

## 1. Matrice "Risque → Fix" détaillée

| Risque | Phase | Score | Effort | QW-S3-2 | Module cible |
|--------|-------|-------|--------|---------|--------------|
| R3 Archive PII GDPR | P10 | 4/12 | 1h | QW-S3-6 | `lib/archive_anonymizer.py` |
| R4 OS-level sandbox | P5 | 4/12 | 2h | QW-S3-7 | `lib/docker_sandbox.py` |
| R5 audit HMAC migration | P8 | 3/12 | 30m | QW-S3-8 | `lib/state.py` (modifier append_audit) |
| R6 Adversarial corpus | P6 | 2/12 | 2h | QW-S3-9 | `lib/adversarial_corpus.py` |
| R7 Property-based | P6 | 2/12 | 1h | QW-S3-10 | `lib/property_tests.py` |
| R8 Per-tenant keys | P9 | 2/12 | 1h | QW-S3-11 | `lib/memory_blocks.py` (chiffrement per-tenant) |
| R9 CAB approver immutable | P9 | 2/12 | 30m | QW-S3-12 | `lib/cab_approver.py` |
| R10 EOL HMAC | P10 | 4/12 | 1h | QW-S3-13 | `lib/eol_decision.py` |

**Total** : ~9h pour fermer **tous** les MED.

---

## 2. Nouveaux gaps identifiés pendant S3 (à S3-2 ou v1.0)

### 2.1 S3-N1 — TOFU registry compromise

**Description** : Si la registry Docker (docker.io, gcr.io) est compromise, l'attaquant peut servir un contenu différent au même SHA-256 (collision attack théorique).

**Likelihood** : VERY LOW (SHA-256 collisions pas encore pratiques)
**Impact** : HIGH (déploiement compromis)
**Mitigation S3-2** : `cosign` verify + signature check (out of scope POV)
**Note** : limitation théorique, acceptable POV

### 2.2 S3-N2 — skopeo/docker subprocess DoS

**Description** : `pin_to_digest` lance un subprocess qui peut timeout / DoS / hanging.
**Likelihood** : MED (CI/CD lent = production halt)
**Impact** : MED (build ne peut pas finir)
**Mitigation S3-2** : timeout strict + cache des digests résolus

### 2.3 S3-N3 — `pin_to_digest` dépendance externe

**Description** : Si `skopeo` n'est pas installé, `pin_to_digest` retourne None silencieusement.
**Likelihood** : MED (CI/CD minimal sans skopeo)
**Impact** : LOW (fallback fonctionne avec `docker`)
**Mitigation S3-2** : warning explicite + cache persistant

### 2.4 Nouveau gap détecté en passe 3 — **Memory blocks sans chiffrement at rest**

**Description** : `memory_blocks.py` stocke le content en clair dans SQLite. Si un attaquant a accès au filesystem, il peut lire les facts/episodic.

**Likelihood** : MED (filesystem access = game over de toute façon, mais defense in depth)
**Impact** : MED (PII dans les facts utilisateur)
**Mitigation S3-2** : QW-S3-11 inclut le chiffrement per-tenant

### 2.5 Nouveau gap — **Council Bridge simulée**

**Description** : Les verdicts Council Bridge sont simulés (pas de vrais agents nexus-*).
**Likelihood** : HIGH (on l'a dit depuis le début)
**Impact** : MED (revue moins rigoureuse qu'un vrai red team)
**Mitigation v1.0** : vraie Council Bridge avec agents nexus-* (nécessite infra)

---

## 3. Plan d'implémentation S3-2

| Sprint | Cible | Effort | Tests attendus | Risque résiduel après |
|--------|-------|--------|---------------|------------------------|
| **QW-S3-6** | Archive anonymisation GDPR | 1h | 8 | R3 → 0 |
| **QW-S3-7** | OS-level sandbox Docker | 2h | 10 (integration) | R4 → 1 (Docker runtime dep) |
| **QW-S3-8** | state.append_audit → RotatingHMAC | 30m | 6 | R5 → 0 |
| **QW-S3-9** | Adversarial payload corpus | 2h | 15 | R6 → 0 |
| **QW-S3-10** | Property-based testing | 1h | 8 | R7 → 1 (Hypothesis dep) |
| **QW-S3-11** | Per-tenant key encryption | 1h | 7 | R8 → 0 |
| **QW-S3-12** | CAB approver immutability | 30m | 5 | R9 → 0 |
| **QW-S3-13** | EOL HMAC | 1h | 6 | R10 → 0 |
| **Total** | | **~9h** | **65+ nouveaux** | **0 CRIT, ≤2 MED** |

**Après S3-2** :
- 0 CRIT
- 0-2 MED (Docker runtime + Hypothesis = deps externes)
- 328+ tests (263 + 65+)
- 12 modules sécurité (10 + 2)

---

## 4. Verdict attendu post-S3-2

🟢 **POV production-ready ISO27001-ready** :
- 0 risque CRIT
- ≤2 MED (tous deux liés à des dépendances externes, pas à l'architecture)
- 0 LOW (ou quelques-uns acceptables)
- Adversarial coverage : 100+ payloads
- Tests : 328+
- Modules : 12+

**Sanity check** : 3 passes successives (5 → 1 → 0 CRIT) confirment que la trajectoire est asymptotique vers zero, pas un simple coup de théâtre. Chaque passe ferme **réellement** des risques, **n'introduit** pas de nouveaux CRIT, et **valide** par des tests.

---

*Audit conduit 2026-06-09 par discovery-orchestrator. Passe 3 (pré-S3-2). Objectif : fermer les 8 MED restants.*
