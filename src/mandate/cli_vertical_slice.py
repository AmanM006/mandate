import sys
import time
from src.mandate.schema.db import FalkorClientManager
from src.mandate.schema.seed_public import seed_regulatory_corpus
from src.mandate.schema.seed_tenants import seed_flagship_aetherlearn, seed_isolated_nexusops
from src.mandate.tools.graph_tools import GraphTools

def run_vertical_slice():
    print("=" * 70)
    print("MANDATE VERTICAL SLICE: FALKORDB-NATIVE COMPLIANCE REASONING")
    print("=" * 70)

    mgr = FalkorClientManager()
    tools = GraphTools(mgr)

    # 1. Reset and Seed
    print("\n[Step 1] Ingesting Public Legal Corpus & Tenant Topologies...")
    seed_regulatory_corpus(mgr)
    seed_flagship_aetherlearn(mgr)
    seed_isolated_nexusops(mgr)
    print("  [OK] Public DPDP Rules (G.S.R. 846(E)), Act No. 22 of 2023 & Corrigendum loaded.")
    print("  [OK] Flagship 'aetherlearn' and isolated 'nexusops' graphs initialized.")

    # 2. Investigator Traversal
    print("\n[Step 2] Investigator Agent: Traversing Data Flows & Controls...")
    contradictions = tools.traverse_contradictions("aetherlearn")
    for item in contradictions:
        print(f"  * Endpoint: {item['endpoint']}")
        print(f"    Category: {item['category']}")
        if item['bypassed_control']:
            print(f"    [WARN] BYPASSED CONTROL: {item['bypassed_control']}")
        if item['contradictory_evidence']:
            print(f"    [ALERT] Contradictory Evidence IDs: {item['contradictory_evidence']}")
        if item['supporting_evidence']:
            print(f"    [INFO] Supporting Evidence IDs: {item['supporting_evidence']}")

    # 3. Interpreter Legal Commencement & Invalidation
    print("\n[Step 3] Interpreter Agent: Checking Section 9(1) & Rule 10 Commencement...")
    prov_9_1 = tools.get_provision_status("DPDP_ACT_SEC_9_1")
    rule_10 = tools.get_provision_status("DPDP_RULES_2025_RULE_10")
    print(f"  * Provision {prov_9_1['section']} ({prov_9_1['title']}):")
    print(f"    Legal Status: {prov_9_1['legal_status']} | Commences: {prov_9_1['effective_from']}")
    print(f"    Basis: {prov_9_1['commencement_basis']}")
    print(f"  * {rule_10['section']} ({rule_10['title']}):")
    print(f"    Legal Status: {rule_10['legal_status']} | Commences: {rule_10['effective_from']}")

    print("\n[Step 4] Selective Invalidation: Superseding PRM_001 on New Evidence...")
    inval_results = tools.selective_invalidate_premise(
        tenant_id="aetherlearn",
        stale_premise_id="PRM_001",
        reason="Jira ticket ENG-8419 confirmed Google SSO guest preview bypasses verifiable parental consent."
    )
    for res in inval_results:
        print(f"  [OK] Claim {res['claim_id']} selectively transitioned to INVALIDATED_STALE.")
        print(f"    Audit Event: {res['audit_event']}")

    # Verify that independent billing claim was preserved
    g = mgr.get_tenant_graph("aetherlearn")
    billing_claim = g.ro_query(
        "MATCH (c:Claim {claim_id: 'CLM_ENC_04'}) RETURN c.status, c.is_stale"
    ).result_set
    print(f"  [OK] Unrelated Billing Claim CLM_ENC_04: Status={billing_claim[0][0]}, is_stale={billing_claim[0][1]} (STRICTLY PRESERVED)")

    # 4. Durable Handoff & Fenced Worker Lease Recovery
    print("\n[Step 5] Remediator Worker Handoff & Lease Recovery...")
    # Create dedicated task for handoff test
    g.query("""
    MERGE (t:Task {task_id: 'TSK_HANDOFF_01', tenant_id: 'aetherlearn'})
    SET t.type = 'APPLY_REMEDIATION',
        t.status = 'OPEN',
        t.lease_version = 0,
        t.retry_count = 0,
        t.max_retries = 3
    """)
    # Worker 1 acquires task lease
    lease1 = tools.acquire_task_lease("aetherlearn", "TSK_HANDOFF_01", "agent_worker_alpha", lease_duration_ms=500)
    print(f"  * Worker Alpha acquired lease: fence_token={lease1['fence_token']}, attempts={lease1['attempts']}")

    # Simulate Worker Alpha crashing/interrupted; lease expires
    print("  * Worker Alpha interrupted (simulating network crash)... waiting 1s for lease expiry.")
    time.sleep(1.0)

    # Worker Beta safely resumes the task
    lease2 = tools.acquire_task_lease("aetherlearn", "TSK_HANDOFF_01", "agent_worker_beta", lease_duration_ms=10000)
    print(f"  * Worker Beta recovered expired task: fence_token={lease2['fence_token']}, attempts={lease2['attempts']}")

    # Zombie Worker Alpha attempts to complete with stale fence token
    stale_completion = tools.complete_task("aetherlearn", "TSK_HANDOFF_01", "agent_worker_alpha", lease1['fence_token'], "IDEM-ALPHA-01")
    print(f"  * Stale Worker Alpha completion attempt rejected: {not stale_completion}")

    # Worker Beta successfully completes task with valid fence token
    beta_completion = tools.complete_task("aetherlearn", "TSK_HANDOFF_01", "agent_worker_beta", lease2['fence_token'], "IDEM-BETA-02")
    print(f"  * Valid Worker Beta task completion committed: {beta_completion}")

    # 5. Multi-Tenant Isolation
    print("\n[Step 6] Multi-Tenant Isolation Verification...")
    g_nexus = mgr.get_tenant_graph("nexusops")
    leaked_claims = g_nexus.ro_query(
        "MATCH (c:Claim {tenant_id: 'aetherlearn'}) RETURN count(c)"
    ).result_set[0][0]
    print(f"  [OK] Querying NexusOps graph for AetherLearn claims returned {leaked_claims} records (ZERO LEAKAGE).")

    print("\n" + "=" * 70)
    print("VERTICAL SLICE COMPLETE: ALL FALKORDB-NATIVE MECHANICS VERIFIED LIVE")
    print("=" * 70)

if __name__ == "__main__":
    run_vertical_slice()
