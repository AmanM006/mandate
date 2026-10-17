# Mandate: FalkorDB-Native Compliance Investigation, Invalidation & Guarded Remediation Engine

**Mandate** is a multi-agent compliance intelligence system natively powered by **FalkorDB Graph Database**. Built for **WeMakeDevs × FalkorDB Graph Hacks** targeting:
- **Track 2: Multi-Agent Architectures & Memory**
- **Track 3: Human-in-the-Loop & Interactive Systems**

---

## 1. Graph Data Model & Cypher Implementation

Mandate models statutory requirements, corporate technical architectures, and multi-agent coordination states strictly as native graph entities in FalkorDB across isolated namespaces (`mandate_aetherlearn`, `mandate_nexusops`, `mandate_dpdp_public`).

```
(LegalProvision) <---[:DEPENDS_ON_PREMISE]--- (Claim) <---[:REMEDIES_CLAIM]--- (ActionProposal)
                                                |                                    |
                                                v                                    v
                                       [:PROCESSES]                              [:COVERS_FLOW]
                                                |                                    |
(DataCategory) <--------------------------- (DataFlow) -----------------------> (Control)
                                                |                                    ^
                                                +-------------[:BYPASSES]------------+ (Conflict)
                                                |
                                                v
                                            (Vendor)
```

### Core Cypher Operations

#### 1. Contradiction Traversal (Track 3: Company Brain)
Traces data flows that bypass mandatory regulatory controls and identifies contradictory engineering evidence:
```cypher
MATCH (df:DataFlow {tenant_id: $tenant_id})-[b:BYPASSES]->(ctl:Control {tenant_id: $tenant_id})
OPTIONAL MATCH (ev_contra:Evidence {tenant_id: $tenant_id})-[:CONTRADICTS]->(ctl)
OPTIONAL MATCH (ev_sup:Evidence {tenant_id: $tenant_id})-[:SUPPORTS]->(ctl)
RETURN df.endpoint AS endpoint,
       ctl.name AS bypassed_control,
       collect(DISTINCT ev_contra.evidence_id) AS contradictory_evidence,
       collect(DISTINCT ev_sup.evidence_id) AS supporting_evidence
```

#### 2. Selective Causal Invalidation (Track 2: Agent Memory)
When evidence invalidates a premise, downstream claims cascade to `INVALIDATED_STALE` and an immutable `InvalidationEvent` audit node is linked without mutating independent claims (e.g., billing encryption `CLM_ENC_04` remains untouched):
```cypher
MATCH (p:Premise {premise_id: $premise_id, tenant_id: $tenant_id})
SET p.status = 'SUPERSEDED'
WITH p
MATCH (claim:Claim {tenant_id: $tenant_id})-[:DEPENDS_ON_PREMISE|DEPENDS_ON_CLAIM*1..4]->(p)
WHERE claim.status <> 'INVALIDATED_STALE'
CREATE (evt:InvalidationEvent {
    event_id: $event_id,
    tenant_id: $tenant_id,
    timestamp: timestamp(),
    triggered_by_premise: p.premise_id,
    previous_status: claim.status,
    new_status: 'INVALIDATED_STALE',
    reason: $reason
})
CREATE (claim)-[:HAS_INVALIDATION_HISTORY]->(evt)
SET claim.status = 'INVALIDATED_STALE',
    claim.is_stale = true
```

#### 3. Single-Query Atomic Cypher Remediation (Track 1 & Track 2)
Matches all preconditions in a single query before mutating vendor configuration and deleting bypass edges, preventing TOCTOU races:
```cypher
MATCH (t:Task {task_id: $task_id, tenant_id: $tenant_id})-[:EXECUTES_PROPOSAL]->(p:ActionProposal {proposal_id: $proposal_id, tenant_id: $tenant_id})
MATCH (p)-[:REMEDIES_CLAIM]->(clm:Claim {tenant_id: $tenant_id})
MATCH (p)-[:BASED_ON_EVIDENCE]->(ev:Evidence {tenant_id: $tenant_id})
MATCH (v:Vendor {vendor_id: p.target_vendor_id, tenant_id: $tenant_id})
MATCH (a:ApprovalRecord {token: $token, tenant_id: $tenant_id})-[:APPROVES_PROPOSAL]->(p)
WHERE t.status = 'IN_PROGRESS'
  AND t.owner_agent = $agent_id
  AND t.lease_version = $fence_token
  AND t.lease_expires_at IS NOT NULL
  AND t.lease_expires_at >= timestamp()
  AND p.status = 'APPROVED'
  AND ev.evidence_revision = p.evidence_revision
  AND a.used = false
  AND a.expires_at >= timestamp()
  AND a.mutation_sig = p.mutation_sig
SET a.used = true,
    a.consumed_at = timestamp(),
    t.status = 'COMPLETED',
    t.idempotency_key = $idempotency_key,
    p.status = 'APPLIED_COMMITTED',
    v.enforce_strict_guardian_handshake = p.enforce_strict_guardian_handshake
WITH t, p, v
OPTIONAL MATCH (df:DataFlow {flow_id: p.target_flow_id, tenant_id: $tenant_id})-[b:BYPASSES]->(ctl:Control)
DELETE b
RETURN t.task_id, v.enforce_strict_guardian_handshake, p.proposal_id
```

---

## 2. Benchmark Breakdown & Detailed Evaluation Results

### Core Regulatory Development Benchmark: 14 / 30 Passed (46.7%)

The 14/30 score is an exact, un-inflated measurement reflecting the specific ground-truth scenarios currently modeled in graph fixtures and statutory commencement logic:

#### Supported & Passing Test Cases (14 Cases):
- **TC-01**: Conflicting internal control bypass (`DF_01` $\rightarrow$ `CTL_VPC_GATE`).
- **TC-02**: Vendor strict handshake gap on future obligation (`VND_01.enforce_strict_guardian_handshake = false`).
- **TC-04**: Evidence supporting active content moderation control (`CTL_CONTENT_MOD`).
- **TC-05**: Notice translation commencement obligations under Rule 3.
- **TC-09**: Selective premise invalidation audit retention on `PRM_001`.
- **TC-10**: Independent claim survival (`CLM_ENC_04` AES-256 billing claim).
- **TC-13**: Cross-border negative list statutory prohibition check under Section 16.
- **TC-14**: Exemption verification for pedagogical research anonymizer under Section 17(2)(b).
- **TC-17**: Breach notification timing under Section 8(6).
- **TC-25**: Consent Manager registration boundary validation under Rule 4.
- **TC-27**: Multi-tenant namespace isolation (`nexusops` query returns 0 `aetherlearn` claims).
- **TC-28**: Behavioral compliance test suite transition (5/8 pre-patch $\rightarrow$ 8/8 post-patch).
- **TC-29**: Distributed task lease acquisition and fencing token monotonicity.
- **TC-30**: Immutable `InvalidationEvent` audit trail persistence in graph.

#### Unimplemented / Out-of-Scope Test Cases (16 Cases):
- **TC-03, TC-06, TC-07, TC-08, TC-11, TC-12, TC-15, TC-16, TC-18, TC-19, TC-20, TC-21, TC-22, TC-23, TC-24, TC-26**: These test cases evaluate external statutory provisions (e.g., DPIIT startup exemption certificate checks, Corrigendum formatting rules, Right to Erasure workflows, and employee intern HR pipelines) that are not currently seeded in the demo fixtures.

### Reserved Evaluation Suite: 8 / 8 Verified (100.0%)

Standalone validation suite executing in disposable namespaces with live demo invariance assertions:
1. **HIDDEN-01**: Cross-border transfer prohibition under Section 16 (`FUTURE_OBLIGATION`).
2. **HIDDEN-02**: Consent Manager boundary verification under Rule 4.
3. **HIDDEN-03**: Research exemption threshold validation under Section 17(2)(b) with active anonymization control.
4. **HIDDEN-04**: Startup exemption boundary review under Section 17(3) (`UNRESOLVED_UNCERTAIN`).
5. **HIDDEN-05**: Multi-tenant child-data segregation (verified isolated tenant access with zero claims returned for `nexusops`).
6. **HIDDEN-06**: Expired server approval rejection (`APPROVAL_TOKEN_EXPIRED`).
7. **HIDDEN-07**: Concurrent dual-worker lease collision and zombie worker rejection (`STALE_FENCE_TOKEN_REJECTED`).
8. **HIDDEN-08**: Multi-session episodic recovery (seeded graph-shape check: two distinct session conclusion nodes connected by `[:SUPERSEDES]`).

---

## 3. Quick Start & Direct Seed Commands

### 1. Launch FalkorDB Container
```bash
docker run -d --restart=unless-stopped --name mandate-falkordb -p 6379:6379 falkordb/falkordb-server:latest
```

### 2. Direct Seed Command (Fresh Pre-Patch Baseline)
Seeds the public regulatory corpus, the flagship AetherLearn graph with the planted bypass, and the isolated NexusOps tenant:
```bash
python -c "from src.mandate.schema.seed_public import seed_regulatory_corpus; from src.mandate.schema.seed_tenants import seed_flagship_aetherlearn, seed_isolated_nexusops; from src.mandate.schema.db import FalkorClientManager; mgr = FalkorClientManager(); seed_regulatory_corpus(mgr); seed_flagship_aetherlearn(mgr, 'aetherlearn'); seed_isolated_nexusops(mgr, 'nexusops'); print('Demo graphs seeded successfully!')"
```

### 3. Run Test Suites & Multi-Agent Demonstration
```bash
# Unit, security, and Cypher atomicity invariants (12 tests)
python -m pytest tests/ -v

# 30-case development benchmark (14/30 passed)
python -m src.mandate.eval.eval_runner

# 8-case reserved evaluation suite (8/8 passed)
python -m src.mandate.eval.hidden_benchmark

# Track 2 Cross-Process Multi-Agent Demonstration (Two Independent Processes)
python -m src.mandate.agents.session_a_process
python -m src.mandate.agents.session_b_process

# API End-to-End Verification (Automated endpoint sequence check)
python verify_browser_flow.py
```

### 4. Launch the Web Console
```bash
uvicorn src.mandate.api:app --host 127.0.0.1 --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser. Demo credentials:
- **Username**: `officer_alice`
- **Password**: `alice_secret_compliance_2026`

---

## 4. Submission Video & Demonstration

- **Demonstration Video Link**: [Watch the 3-Minute Demonstration Video](https://youtu.be/8QXf8TykYZc)
  - Shows fresh pre-patch state (`FAILING_CONTROLS_DETECTED`, 1 bypass, false handshake, 5/8 passing).
  - Shows independent execution of Process 1 (`Session A`) and Process 2 (`Session B`) coordinating via FalkorDB.
  - Shows selective invalidation of `PRM_001` and preservation of independent billing claim `CLM_ENC_04`.
  - Shows real officer approval and UI button click committing the atomic Cypher patch.
  - Shows rendered post-patch screen transition (0 bypasses, true handshake, 8/8 tests passing, `MODELED_CONTROL_TESTS_PASS`, and `[:SUPERSEDES]` graph path).

---

## 5. AI Assistance & Transparency Disclosure

In accordance with competition guidelines:
- **Architecture & System Design**: Designed by team lead Aman Mishra.
- **AI Coding Assistance**: Google Antigravity (DeepMind agentic coding system) was utilized for Cypher query optimization, refactoring API endpoints, generating pytest edge cases, and drafting benchmark runners.
- **All FalkorDB Cypher queries, graph schemas, and statutory commencement interpretations were strictly human-verified and tested against the official Gazette of India and FalkorDB v4.22 documentation.**
