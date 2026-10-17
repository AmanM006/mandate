# Updated Milestone 1 Walkthrough: Graph Schema, Event-Sourced Invalidation & Fenced Leases

## 1. Updated Schema Enhancements

### A. Directed Graph Dependency Model
To support recursive variable-length dependency evaluation across multi-premise arguments:
- `(:Claim)-[:DEPENDS_ON_CLAIM]->(:Claim)`: Explicit claim-to-claim dependency edges.
- `(:Claim)-[:DEPENDS_ON_PREMISE]->(:Premise)`: Claim grounded in specific premises.
- `(:Premise)-[:SUPERSEDED_BY]->(:Premise)`: Explicit premise replacement edge.
- `(:DataFlow)-[:BYPASSES]->(:Control)`: Formal edge representing deliberate or accidental control bypasses (e.g. quick preview signup bypasses guardian verification).

### B. Event-Sourced Invalidation Audit Log
Rather than destructively overwriting status, all invalidations write a durable `InvalidationEvent`:
- `(:InvalidationEvent {event_id, timestamp, triggered_by_premise, previous_status, new_status, reason})`
- `(:Claim)-[:HAS_INVALIDATION_HISTORY]->(:InvalidationEvent)`
- Multi-premise claims are evaluated using conjuncts: a claim transitions to `INVALIDATED_STALE` if any essential premise is marked `SUPERSEDED`, but the record preserves which premises remain valid.

### C. Fenced Task Lease with Idempotency Key
To ensure distributed worker safety and eliminate double-completion from revived zombie workers:
- `Task` properties: `task_id`, `type`, `status`, `owner_agent`, `lease_version`, `lease_expires_at`, `max_retries`, `retry_count`, `idempotency_key`.
- Allowed states: `OPEN`, `IN_PROGRESS`, `COMPLETED`, `FAILED`.

---

## 2. Tested Cypher Formulations

### Query 1: Contradiction Traversal (Incorporating Bypass Edges)
```cypher
MATCH (flow:DataFlow {tenant_id: $tenant_id})
OPTIONAL MATCH (flow)-[:PROCESSES]->(cat:DataCategory)
OPTIONAL MATCH (flow)-[:BYPASSES]->(bypassed_ctl:Control)
OPTIONAL MATCH (ctl:Control)-[:COVERS_FLOW]->(flow)
OPTIONAL MATCH (ev_contra:Evidence)-[:CONTRADICTS]->(ctl)
RETURN flow.endpoint AS endpoint,
       cat.name AS category,
       bypassed_ctl.name AS bypassed_control,
       ctl.name AS active_control,
       collect(DISTINCT ev_contra.evidence_id) AS contradicting_evidence
```
*What it reads*: Data flows, data categories, bypassed controls, active controls, and contradictory evidence artifacts.
*What it writes*: Read-only.
*What fails without FalkorDB*: Graph-native traversal seamlessly catches both missing control links and explicit `BYPASSES` relationships simultaneously across disparate systems and tickets.

---

### Query 2: Event-Sourced Multi-Premise Selective Invalidation
```cypher
MATCH (p_stale:Premise {premise_id: $stale_premise_id, tenant_id: $tenant_id})
SET p_stale.status = 'SUPERSEDED'
WITH p_stale
MATCH (claim:Claim {tenant_id: $tenant_id})-[:DEPENDS_ON_PREMISE|DEPENDS_ON_CLAIM*1..4]->(p_stale)
WHERE claim.status <> 'INVALIDATED_STALE'
CREATE (evt:InvalidationEvent {
    event_id: 'INVAL-EVT-' + apoc.util.randomUUID(),
    timestamp: timestamp(),
    triggered_by_premise: p_stale.premise_id,
    previous_status: claim.status,
    new_status: 'INVALIDATED_STALE',
    reason: 'Upstream premise superseded: ' + p_stale.premise_id
})
CREATE (claim)-[:HAS_INVALIDATION_HISTORY]->(evt)
SET claim.status = 'INVALIDATED_STALE',
    claim.is_stale = true
RETURN claim.claim_id AS invalidated_claim,
       evt.event_id AS audit_event_id
```
*What it reads*: Upstream premise and transitive dependency chain (`DEPENDS_ON_PREMISE` and `DEPENDS_ON_CLAIM` up to 4 hops).
*What it writes*: InvalidationEvent node, relationship link, and updates claim status without deleting history.
*What fails without FalkorDB*: Relational recursion requires maintaining bespoke adjacency tables. A document store requires pulling whole claim graphs into memory, risking concurrent race conditions and dirty writes.

---

### Query 3: Fenced Atomic Task Lease Acquisition with Failure State
```cypher
MATCH (t:Task {task_id: $task_id, tenant_id: $tenant_id})
WHERE (t.status = 'OPEN') 
   OR (t.status = 'IN_PROGRESS' AND t.lease_expires_at < timestamp() AND t.retry_count < t.max_retries)
SET t.status = 'IN_PROGRESS',
    t.owner_agent = $agent_id,
    t.lease_version = coalesce(t.lease_version, 0) + 1,
    t.lease_expires_at = timestamp() + $lease_duration_ms,
    t.retry_count = t.retry_count + 1
RETURN t.task_id AS acquired_task,
       t.lease_version AS fence_token,
       t.retry_count AS attempts
```
*What it reads*: Task status, expiration against server `timestamp()`, and retry budget.
*What it writes*: Increments `lease_version` fencing token, increments retry counter, and sets expiration.
*What fails without FalkorDB*: Without an atomic database-level fence, worker crashes result in split-brain execution where multiple agent processes apply duplicate configuration patches.

---

### Query 4: Fenced Idempotent Task Completion
```cypher
MATCH (t:Task {task_id: $task_id, tenant_id: $tenant_id})
WHERE t.status = 'IN_PROGRESS' 
  AND t.owner_agent = $agent_id 
  AND t.lease_version = $fence_token
SET t.status = 'COMPLETED',
    t.idempotency_key = $idempotency_key,
    t.completed_at = timestamp()
RETURN t.task_id AS completed_task,
       t.idempotency_key AS key
```
*What it reads*: Task lease version and agent identity.
*What it writes*: Commits completion only if the worker still holds the exact fencing token it acquired.
*What fails without FalkorDB*: If a stalled worker wakes up after lease expiry, this query safely rejects its write because `lease_version` was already bumped by the replacement worker.
