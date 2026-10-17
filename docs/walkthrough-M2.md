# Walkthrough: Milestone 2 Vertical Slice Execution

This document details the live execution of Mandate's CLI vertical slice against the real FalkorDB server instance (`127.0.0.1:6379`), covering all queries executed, nodes read and written, and the specific failure modes that occur if FalkorDB is removed.

---

## 1. Trace of Live Operations

### Step 1: Ingestion & Public Legal Graph Seeding
- **Database Targets**: 
  - `mandate_dpdp_public`: Official DPDP statutory provisions, rules, corrigendum, and commencement models.
  - `mandate_aetherlearn`: Flagship edtech tenant with the planted parental consent conflict.
  - `mandate_nexusops`: Isolated B2B monitoring tenant.
- **Nodes Created**: 
  - `SourceDocument`, `DocumentVersion`, `Commencement`, `Provision`
  - `Company`, `Product`, `DataFlow`, `DataCategory`, `Control`, `Evidence`, `Premise`, `Claim`, `Task`
- **What it Reads**: Nothing (idempotent `MERGE` statements).
- **What it Writes**: Graph adjacency matrices and attribute tables in FalkorDB.
- **What Fails Without FalkorDB**: In standard relational schemas or vector databases, cross-tenant isolation requires application-level `WHERE tenant_id = ?` filters that are easily omitted by developer error. FalkorDB's `select_graph(tenant_name)` isolates tenant storage natively at the engine level.

---

### Step 2: Investigator Contradiction Traversal
- **Query Executed**:
  ```cypher
  MATCH (flow:DataFlow {tenant_id: $tenant_id})
  OPTIONAL MATCH (flow)-[:PROCESSES]->(cat:DataCategory)
  OPTIONAL MATCH (flow)-[:BYPASSES]->(bypassed_ctl:Control)
  OPTIONAL MATCH (ctl:Control)-[:COVERS_FLOW]->(flow)
  OPTIONAL MATCH (ev_contra:Evidence)-[:CONTRADICTS]->(ctl)
  OPTIONAL MATCH (ev_supp:Evidence)-[:SUPPORTS]->(ctl)
  RETURN flow.endpoint AS endpoint,
         cat.name AS category,
         bypassed_ctl.name AS bypassed_control,
         ctl.name AS active_control,
         collect(DISTINCT ev_contra.evidence_id) AS contradictions,
         collect(DISTINCT ev_supp.evidence_id) AS supports
  ```
- **Observed Result**:
  - Endpoint `/api/v2/auth/student-signup` was detected processing `Minor Student Profile & Educational Records`.
  - Identified explicit bypass: `[WARN] BYPASSED CONTROL: Guardian Verifiable Consent Gate`.
  - Pinpointed conflicting evidence: Supporting `EV_POL_01` (AetherLearn DPDP Policy) vs. Contradictory `EV_TICKET_ENG_8419` (Jira ticket adding Google SSO Quick Preview bypass).
- **What it Reads**: `DataFlow`, `DataCategory`, `Control`, `Evidence`, and relationships `PROCESSES`, `BYPASSES`, `COVERS_FLOW`, `CONTRADICTS`, `SUPPORTS`.
- **What it Writes**: Read-only (`ro_query`).
- **What Fails Without FalkorDB**: Finding bypassed controls and conflicting evidence simultaneously requires joining five distinct entity tables. In a document or vector store, an LLM must read dozens of unstructured logs and synthesize the link, frequently missing silent bypass edges.

---

### Step 3: Interpreter Legal Status & Commencement Check
- **Query Executed**:
  ```cypher
  MATCH (p:Provision {provision_id: $provision_id})
  OPTIONAL MATCH (p)-[:GOVERNED_BY]->(c:Commencement)
  RETURN p.section_number AS section,
         p.title AS title,
         p.official_text AS text,
         p.legal_status AS legal_status,
         c.effective_from AS effective_from,
         c.transition_months AS transition_months,
         c.basis AS commencement_basis,
         c.is_in_force_now AS is_in_force_now
  ```
- **Observed Result**:
  - Section 9(1) (`Verifiable Parental Consent`): `FUTURE_OBLIGATION`, effective `2027-05-14` (18 months basis under G.S.R. 843(E) / 846(E)).
  - Rule 10 (`Mechanisms for Obtaining VPC`): `FUTURE_OBLIGATION`, effective `2027-05-14`.
- **What it Reads**: `Provision` and `Commencement` nodes connected via `GOVERNED_BY`.
- **What it Writes**: Read-only.
- **What Fails Without FalkorDB**: LLMs hallucinate that all enacted statutory rules are in force immediately. FalkorDB grounds legal applicability strictly in the notification metadata.

---

### Step 4: Selective Invalidation & Causal Event Logging
- **Query Executed**:
  ```cypher
  MATCH (p:Premise {premise_id: $premise_id, tenant_id: $tenant_id})
  SET p.status = 'SUPERSEDED'
  WITH p
  MATCH (claim:Claim {tenant_id: $tenant_id})-[:DEPENDS_ON_PREMISE|DEPENDS_ON_CLAIM*1..4]->(p)
  WHERE claim.status <> 'INVALIDATED_STALE'
  CREATE (evt:InvalidationEvent {
      event_id: $event_id_prefix + claim.claim_id,
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
  RETURN claim.claim_id AS invalidated_claim,
         evt.event_id AS audit_event
  ```
- **Observed Result**:
  - `PRM_001` (Unbroken guardian gate) was marked `SUPERSEDED`.
  - Dependent Claim `CLM_VPC_01` was selectively identified and transitioned to `INVALIDATED_STALE`.
  - Audit record created: `InvalidationEvent` `EVT-INVAL-04c92a-CLM_VPC_01`.
  - Independent Claim `CLM_ENC_04` (Billing encryption) was checked: remained `Status=VALID_ACTIVE`, `is_stale=False` without being touched.
- **What it Reads**: `Premise`, `Claim`, and variable-length dependency path `[:DEPENDS_ON_PREMISE|DEPENDS_ON_CLAIM*1..4]`.
- **What it Writes**: Sets `p.status`, creates `InvalidationEvent`, links `HAS_INVALIDATION_HISTORY`, updates `claim.status`.
- **What Fails Without FalkorDB**: Relational databases cannot traverse variable-depth dependency trees without recursive CTEs that degrade rapidly under multi-parent hierarchies. Without graph dependency chains, automated systems resort to invalidating entire compliance dashboards or failing to propagate invalidations to downstream claims.

---

### Step 5: Durable Task Lease & Concurrency Fencing
- **Queries Executed**:
  1. *Lease Acquisition*:
     ```cypher
     MATCH (t:Task {task_id: $task_id, tenant_id: $tenant_id})
     WHERE (t.status = 'OPEN')
        OR (t.status = 'IN_PROGRESS' AND t.lease_expires_at < timestamp() AND t.retry_count < t.max_retries)
     SET t.status = 'IN_PROGRESS',
         t.owner_agent = $agent_id,
         t.lease_version = coalesce(t.lease_version, 0) + 1,
         t.lease_expires_at = timestamp() + $duration,
         t.retry_count = t.retry_count + 1
     RETURN t.task_id AS acquired_task,
            t.lease_version AS fence_token,
            t.retry_count AS attempts
     ```
  2. *Fenced Task Completion*:
     ```cypher
     MATCH (t:Task {task_id: $task_id, tenant_id: $tenant_id})
     WHERE t.status = 'IN_PROGRESS'
       AND t.owner_agent = $agent_id
       AND t.lease_version = $fence_token
     SET t.status = 'COMPLETED',
         t.idempotency_key = $idempotency_key,
         t.completed_at = timestamp()
     RETURN t.task_id AS completed_task
     ```
- **Observed Result**:
  - Worker Alpha acquired initial lease with `fence_token=1`, `attempts=1`.
  - Worker Alpha was interrupted; after 1 second, the lease expired.
  - Worker Beta claimed the expired task, receiving `fence_token=2`, `attempts=2`.
  - Zombie Worker Alpha woke up and attempted to commit completion using stale token `1`: **Rejected (`False`)**.
  - Worker Beta completed the task using valid token `2`: **Committed (`True`)**.
- **What it Reads**: `Task` properties (`status`, `lease_expires_at`, `max_retries`, `owner_agent`, `lease_version`).
- **What it Writes**: Updates `owner_agent`, increments `lease_version` and `retry_count`, sets `status = 'COMPLETED'` and `idempotency_key`.
- **What Fails Without FalkorDB**: Distributed agent architectures frequently suffer split-brain execution when interrupted agents resume without atomic database fencing. FalkorDB enforces transactional atomic leases directly in the graph state.

---

### Step 6: Multi-Tenant Isolation Verification
- **Query Executed**:
  ```cypher
  MATCH (c:Claim {tenant_id: 'aetherlearn'}) RETURN count(c)
  ```
  Executed inside the `mandate_nexusops` graph space.
- **Observed Result**: `0` records returned.
- **What it Reads**: `Claim` nodes inside tenant graph `mandate_nexusops`.
- **What it Writes**: Read-only.
- **What Fails Without FalkorDB**: Cross-tenant data leakage occurs whenever multi-tenant databases share single index collections. FalkorDB's native multigraph design provides absolute isolation across tenants.
