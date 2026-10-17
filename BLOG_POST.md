---
title: "Building MANDATE: Multi-Agent Epistemic Memory, Invalidation & Guarded Remediation with FalkorDB"
published: true
tags: ai, falkordb, graphrag, python
canonical_url: https://github.com/AmanM006/mandate
description: "How we used FalkorDB's sub-millisecond graph traversals, monotonic fencing, and Cypher to solve multi-agent hallucinations, selective memory invalidation, and human-in-the-loop governance."
---

# Building MANDATE: Multi-Agent Epistemic Memory, Invalidation & Guarded Remediation with FalkorDB

*Submitted to the WeMakeDevs Graph Hacks Hackathon — Track 2 (Multi-Agent Architectures & Memory) & Track 3 (Human-in-the-Loop & Interactive Systems).*

---

## 1. The Core Dilemma in Multi-Agent AI Systems

Autonomous AI agents are increasingly tasked with operating complex enterprise environments—auditing regulatory policies, querying enterprise data pipelines, and executing remediations. But in production, multi-agent workflows hit three catastrophic walls:

1. **Context Window Amnesia & Disconnected Sessions:**  
   When Agent Session A audits a system and terminates, Agent Session B has zero native visibility into Session A’s factual premises. Relying on conversational summaries causes subtle hallucinations and lost epistemic dependencies.
2. **Catastrophic Forgetting during Invalidation:**  
   When engineering evidence changes (e.g., an SSO bypass is introduced), typical vector embeddings or RAG pipelines fail to selectively invalidate only the affected claims. They either fail to update downstream assumptions or wipe out unrelated, perfectly valid conclusions.
3. **Unguarded Autonomous Mutations:**  
   Allowing LLM agents direct write privileges on production infrastructure is unacceptable. Conversely, traditional human-in-the-loop mechanisms suffer from race conditions, zombie worker overwrites, and state drift.

To solve this, we built **MANDATE** — an epistemic graph-native governance engine powered by **FalkorDB**.

---

## 2. Why FalkorDB?

When architecting epistemic multi-agent memory, relational databases require painful recursive CTEs, and vector databases lack explicit causal edges. 

We chose **FalkorDB** for three decisive technical capabilities:

- **Sub-Millisecond Multi-Hop Traversal:** Epistemic dependency trees (`[:DEPENDS_ON_PREMISE*1..4]`) require instantaneous recursive traversal across legal statutes, enterprise claims, and engineering telemetry. FalkorDB’s GraphBLAS sparse-matrix engine executes deep graph queries in microseconds.
- **Single-Query Atomic Remediation:** FalkorDB allows us to enforce monotonic fencing tokens, cryptographic reviewer approvals, and graph schema mutations in a single atomic Cypher transaction.
- **Multi-Tenant Graph Namespace Isolation:** By routing tenants to isolated FalkorDB graph namespaces, tenant data segregation is guaranteed at the database engine level.

---

## 3. System Architecture & The Epistemic Graph Model

At the heart of MANDATE is a typed, multi-relational property graph:

```
[Statutory Provision] <---[:GOVERNED_BY]--- [Compliance Control]
                                                    ^
                                                    | (monitors)
[ActionProposal] ---[:REMEDIES_CLAIM]---> [Claim] <-+
        |                                   |
        +---[:BASED_ON_EVIDENCE]---> [Evidence]
                                            ^
[InvalidationEvent] ---[:INVALIDATES]-------+
```

### The Nodes:
- `Provision`: Statutory legal obligations (e.g., DPDP Act 2023 Sec 9(1) for Parental Consent).
- `Control`: Modeled enterprise security gates (e.g., `CTL_VPC_GATE`).
- `DataFlow`: Observed runtime data streams (`DF_01`).
- `Claim`: Epistemic assertion derived from premises (`CLM_VPC_01`).
- `Task` & `ActionProposal`: Durable worker tasks equipped with lease timers and monotonic fence tokens.
- `ApprovalRecord`: Cryptographic, single-use server signatures bound to authenticated compliance officers.

---

## 4. Track 2: True Cross-Session Memory & Epistemic Invalidation

How does MANDATE solve multi-agent memory without shared in-memory variables?

### Step 1: Agent Session A (Cold Start Discovery)
Agent A runs in a dedicated Python process, discovers a bypass edge between `DF_01` and `CTL_VPC_GATE`, computes a `FAILING_CONTROLS_DETECTED` verdict, writes an `AssessmentConclusion` node into FalkorDB, and **terminates completely**:

```cypher
MATCH (clm:Claim {claim_id: 'CLM_VPC_01', tenant_id: $tenant_id})
CREATE (c:AssessmentConclusion {
    conclusion_id: $cid,
    session_id: $session_id,
    agent_id: 'agent_investigator_a',
    verdict: 'FAILING_CONTROLS_DETECTED',
    created_at: timestamp()
})
MERGE (c)-[:EVALUATES_CLAIM]->(clm)
MERGE (t:Task {task_id: 'TSK_HANDOFF_01', tenant_id: $tenant_id})
SET t.status = 'OPEN', t.target_conclusion_id = $cid
```

### Step 2: Agent Session B (Selective Invalidation)
Process 2 (Agent B) starts cold. It connects to FalkorDB, recovers `TSK_HANDOFF_01`, and acquires a fenced lease.

When contradictory engineering evidence arrives (`ENG-8419`), Agent B triggers **selective premise invalidation**:

```cypher
MATCH (p:Premise {premise_id: $premise_id, tenant_id: $tenant_id})
SET p.status = 'SUPERSEDED'
WITH p
MATCH (claim:Claim {tenant_id: $tenant_id})-[:DEPENDS_ON_PREMISE*1..4]->(p)
WHERE claim.status <> 'INVALIDATED_STALE'
CREATE (evt:InvalidationEvent {
    event_id: $event_id,
    triggered_by: p.premise_id,
    new_status: 'INVALIDATED_STALE'
})
CREATE (claim)-[:HAS_INVALIDATION_HISTORY]->(evt)
SET claim.status = 'INVALIDATED_STALE', claim.is_stale = true
WITH claim
OPTIONAL MATCH (prop:ActionProposal {tenant_id: $tenant_id})-[:REMEDIES_CLAIM]->(claim)
SET prop.status = 'INELIGIBLE_SUPERSEDED'
```

### 🎯 The Critical Result:
- Upstream claims dependent on `PRM_001` are invalidated.
- Outdated remediation proposal `PROP_REMED_01` is automatically marked `INELIGIBLE_SUPERSEDED`.
- **Independent claims (like billing encryption `CLM_ENC_04`) remain untouched and valid.**
- Agent B stages a fresh proposal `PROP_REMED_02` on a dedicated task `TSK_BROWSER_REMED_01` for human review.

---

## 5. Track 3: Single-Query Atomic Guarded Remediation

In MANDATE, no agent can mutate production configuration directly. When a Compliance Officer authorizes a proposal in the Web Console, the execution occurs through an **atomic Cypher mutation**:

```cypher
MATCH (t:Task {task_id: $task_id, tenant_id: $tenant_id})-[:EXECUTES_PROPOSAL]->(p:ActionProposal {proposal_id: $proposal_id, tenant_id: $tenant_id})
MATCH (p)-[:REMEDIES_CLAIM]->(clm:Claim {tenant_id: $tenant_id})
MATCH (p)-[:BASED_ON_EVIDENCE]->(ev:Evidence {tenant_id: $tenant_id})
MATCH (v:Vendor {vendor_id: p.target_vendor_id, tenant_id: $tenant_id})
MATCH (a:ApprovalRecord {token: $token, tenant_id: $tenant_id})-[:APPROVES_PROPOSAL]->(p)
WHERE t.status = 'IN_PROGRESS'
  AND t.owner_agent = $agent_id
  AND t.lease_version = $fence_token
  AND t.lease_expires_at >= timestamp()
  AND p.status = 'APPROVED'
  AND ev.evidence_revision = p.evidence_revision
  AND a.used = false
  AND a.expires_at >= timestamp()
  AND a.mutation_sig = p.mutation_sig
SET a.used = true,
    a.consumed_at = timestamp(),
    p.status = 'APPLIED_COMMITTED',
    v.enforce_strict_guardian_handshake = p.enforce_strict_guardian_handshake
WITH p, v
OPTIONAL MATCH (df:DataFlow {flow_id: p.target_flow_id, tenant_id: $tenant_id})-[b:BYPASSES]->(ctl:Control)
DELETE b
RETURN t.task_id, v.enforce_strict_guardian_handshake, p.proposal_id
```

### Why this changes everything:
1. **Monotonic Fencing:** If another worker took over the lease (`lease_version != fence_token`), the write fails.
2. **Single-Use Signature:** The `ApprovalRecord` is consumed in the exact same write. It cannot be double-spent.
3. **Zero Partial Failures:** If any precondition fails, zero nodes or edges mutate.

Once committed, the synthetic behavioral suite re-evaluates all 8 child-safety test cases against the live graph:
- Active Bypasses: **1 -> 0**
- Vendor Strict Handshake: **false -> true**
- Behavioral Suite: **5/8 -> 8/8 PASSED**
- Status Badge: **`MODELED_CONTROL_TESTS_PASS`**

Agent B then commits a new conclusion node linked to Session A via **`[:SUPERSEDES]`**, preserving an unbroken audit trail.

---

## 6. What We Learned & Key Takeaways

1. **Graphs are the missing link for Agent Memory:** Representing memory as vector chunks discards causal relationships. By representing beliefs as dependency graphs, invalidation becomes deterministic and mathematically provable.
2. **Atomic Cypher provides true multi-agent safety:** Concurrency bugs in multi-agent architectures (like split-brain decisions or zombie worker writes) can be solved entirely in the database engine using Cypher conditional patterns.
3. **FalkorDB is exceptionally fast:** Running complex 4-hop recursive invalidations alongside tenant-scoped ACL checks consistently took under 3 milliseconds locally.

---

## 7. Links & Resources

- 💻 **GitHub Repository:** [https://github.com/AmanM006/mandate](https://github.com/AmanM006/mandate)
- 🎥 **Demo Video:** [https://youtu.be/8QXf8TykYZc](https://youtu.be/8QXf8TykYZc)
- ⚡ **Database:** [FalkorDB](https://falkordb.com/)

*Built with Python 3.12, FastAPI, Tailwind CSS, and FalkorDB for the WeMakeDevs Graph Hacks Hackathon 2026.*
