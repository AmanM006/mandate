"""
Two-Process Cross-Session Memory Demonstration Script.
Process 2 (Agent Session B):
- Spawns in an independent Python process with zero shared in-memory variables.
- Connects to FalkorDB and retrieves Task TSK_HANDOFF_01 and Session A's conclusion.
- Introduces contradictory engineering evidence / invalidates premise PRM_001.
- Observes the selective invalidation audit trail:
  - Preserves unrelated valid conclusion (CLM_ENC_04 / Stripe AES-256 billing claim).
  - Identifies superseded premise PRM_001.
- Computes revised conclusion:
  - Evaluates active bypasses, remaining controls, and statutory applicability.
  - Arrives at: MODELED_CONTROL_TESTS_PASS (post-remediation) or FAILING_CONTROLS_DETECTED (pre-remediation).
- Persists Revised AssessmentConclusion into FalkorDB.
"""

import sys
import uuid
import datetime
from src.mandate.schema.db import FalkorClientManager
from src.mandate.tools.graph_tools import GraphTools

def run_agent_session_b():
    session_id = f"SES_B_{uuid.uuid4().hex[:8]}"
    print(f"\n=== [PROCESS 2] AGENT SESSION B LAUNCHED (Session: {session_id}, PID: {sys.argv[0]}) ===")

    mgr = FalkorClientManager()
    tools = GraphTools(mgr)
    g = mgr.get_tenant_graph("aetherlearn")

    # 1. Recover Task and Handoff Memory from FalkorDB
    print(f"[{session_id}] Cold-start reading open tasks and prior conclusions from FalkorDB...")
    q_recover = """
    MATCH (t:Task {task_id: 'TSK_HANDOFF_01', tenant_id: 'aetherlearn'})
    OPTIONAL MATCH (c:AssessmentConclusion {conclusion_id: t.target_conclusion_id})
    RETURN t.task_id, t.handoff_from_session, c.conclusion_id, c.verdict, c.agent_id
    """
    res_rec = g.ro_query(q_recover).result_set
    print(f"[{session_id}] Raw Handoff Recovery Result: {res_rec}")
    assert len(res_rec) > 0, "Failed to recover handoff task from FalkorDB."
    task_id, prior_session, prior_conc, prior_verdict, prior_agent = res_rec[0]
    print(f"[{session_id}] Successfully loaded prior state: created by '{prior_agent}' in '{prior_session}' with verdict '{prior_verdict}'.")

    # 2. Acquire Lease
    lease = tools.acquire_task_lease("aetherlearn", "TSK_HANDOFF_01", "agent_worker_b", lease_duration_ms=10000)
    print(f"[{session_id}] Acquired task lease. Fence Token: {lease['fence_token']}")

    # 3. Invalidate upstream premise PRM_001 with audit event
    print(f"[{session_id}] Selectively invalidating premise PRM_001 due to contradiction ENG-8419...")
    inval_res = tools.selective_invalidate_premise(
        tenant_id="aetherlearn",
        stale_premise_id="PRM_001",
        reason="Jira ticket ENG-8419 confirmed Google SSO bypass in student-signup route"
    )
    print(f"[{session_id}] Invalidation result: {inval_res}")

    # 4. Verify that unrelated claim CLM_ENC_04 survived untouched
    q_billing = "MATCH (c:Claim {claim_id: 'CLM_ENC_04', tenant_id: 'aetherlearn'}) RETURN c.status, c.is_stale"
    res_bill = g.ro_query(q_billing).result_set
    print(f"[{session_id}] Independent Billing Claim Status: status={res_bill[0][0]}, is_stale={res_bill[0][1]} [PRESERVED]")
    assert res_bill[0][0] == "VALID_ACTIVE" and res_bill[0][1] is False

    # 5. Autonomous Action Proposal Creation:
    # Notice that PRM_001 invalidation cascaded to PROP_REMED_01 (marked INELIGIBLE_SUPERSEDED).
    # Rather than privileged mutation, Agent B drafts a fresh proposal PROP_REMED_02 tied to
    # current active evidence REV_EV_ENG_8419_v1 to fix the bypass on DF_01.
    print(f"[{session_id}] Drafting fresh proposal PROP_REMED_02 addressing current evidence...")
    fresh_prop_id = "PROP_REMED_02"
    q_create_prop = """
    MATCH (clm:Claim {claim_id: 'CLM_VPC_01', tenant_id: 'aetherlearn'})
    MATCH (ev:Evidence {evidence_id: 'EV_TICKET_ENG_8419', tenant_id: 'aetherlearn'})
    MATCH (t:Task {task_id: 'TSK_HANDOFF_01', tenant_id: 'aetherlearn'})
    CREATE (p:ActionProposal {
        proposal_id: $prop_id,
        tenant_id: 'aetherlearn',
        target_claim_id: 'CLM_VPC_01',
        target_vendor_id: 'VND_01',
        target_flow_id: 'DF_01',
        status: 'PENDING_APPROVAL',
        enforce_strict_guardian_handshake: true,
        remove_guest_bypass: true,
        evidence_revision: ev.evidence_revision,
        created_at: timestamp()
    })
    CREATE (p)-[:REMEDIES_CLAIM]->(clm)
    CREATE (p)-[:BASED_ON_EVIDENCE]->(ev)
    CREATE (t)-[:EXECUTES_PROPOSAL]->(p)
    RETURN p.proposal_id, ev.evidence_revision
    """
    res_prop = g.query(q_create_prop, {"prop_id": fresh_prop_id}).result_set
    assert len(res_prop) > 0, "Failed to create fresh proposal"
    ev_rev = res_prop[0][1]
    print(f"[{session_id}] Successfully created {fresh_prop_id} bound to evidence revision {ev_rev}.")

    # 6. Request and obtain authenticated officer approval
    print(f"[{session_id}] Submitting proposal to authenticated officer review flow...")
    appr = tools.create_proposal_approval("aetherlearn", fresh_prop_id, "officer_alice", ["aetherlearn"])
    assert appr["approval_token"] is not None
    print(f"[{session_id}] Obtained officer approval: {appr['approval_token'][:25]}...")

    # 7. Execute Remediation Patch: Apply allowlisted configuration via Atomic Cypher
    print(f"[{session_id}] Applying remediation patch via strict atomic Cypher write...")
    apply_res = tools.apply_remediation_patch(
        tenant_id="aetherlearn",
        task_id="TSK_HANDOFF_01",
        proposal_id=fresh_prop_id,
        agent_id="agent_worker_b",
        fence_token=lease["fence_token"],
        idempotency_key=f"IDEM-PROC2-{uuid.uuid4().hex[:6]}",
        human_approval_token=appr["approval_token"],
        expected_evidence_revision=ev_rev
    )
    print(f"[{session_id}] Remediation Patch Execution Result: {apply_res}")
    assert apply_res["success"] is True

    # 8. Dynamic Decision Computation via Synthetic Behavioral Suite & Live Graph
    print(f"[{session_id}] Evaluating post-patch controls against live graph...")
    q_eval = """
    MATCH (df:DataFlow {flow_id: 'DF_01', tenant_id: 'aetherlearn'})
    OPTIONAL MATCH (df)-[b:BYPASSES]->(ctl:Control)
    WITH count(b) AS active_bypasses
    MATCH (v:Vendor {vendor_id: 'VND_01', tenant_id: 'aetherlearn'})
    RETURN active_bypasses, v.enforce_strict_guardian_handshake
    """
    res_eval = g.ro_query(q_eval).result_set
    active_bypasses, handshake = res_eval[0]
    print(f"[{session_id}] Graph State Evaluation: active_bypasses={active_bypasses}, handshake_enforced={handshake}")

    # Run Synthetic Behavioral Test Runner to verify all 8 endpoint cases
    from src.mandate.eval.behavioral_tests import SyntheticBehavioralTestRunner
    runner = SyntheticBehavioralTestRunner()
    guest_sso_bypass_active = (active_bypasses > 0)
    behavioral_report = runner.evaluate(
        vendor_strict_handshake=bool(handshake),
        guest_sso_bypass=guest_sso_bypass_active
    )
    print(f"[{session_id}] Synthetic Behavioral Suite: {behavioral_report['passed_cases']}/{behavioral_report['total_cases']} passed.")

    # Compute verdict dynamically strictly from live verification results:
    if behavioral_report["all_passed"] and active_bypasses == 0 and handshake is True:
        computed_verdict = "MODELED_CONTROL_TESTS_PASS"
    else:
        computed_verdict = "FAILING_CONTROLS_DETECTED"

    print(f"[{session_id}] Dynamically Calculated Revised Verdict: {computed_verdict} (Previous: {prior_verdict})")

    # 9. Persist Revised Assessment Conclusion into FalkorDB with SUPERSEDES edge
    q_persist_revised = """
    MATCH (clm:Claim {claim_id: 'CLM_VPC_01', tenant_id: 'aetherlearn'})
    CREATE (c:AssessmentConclusion {
        conclusion_id: $cid,
        tenant_id: 'aetherlearn',
        session_id: $sid,
        agent_id: 'agent_remediator_b',
        verdict: $verdict,
        active_bypasses: $bypasses,
        supersedes_conclusion: $prev_cid,
        behavioral_suite_passed: $all_pass,
        created_at: timestamp(),
        status: 'ACTIVE_RECORD'
    })
    CREATE (c)-[:REVISED_EVALUATION_OF]->(clm)
    CREATE (c)-[:SUPERSEDES]->(prior:AssessmentConclusion {conclusion_id: $prev_cid})
    SET clm.status = $verdict,
        clm.is_stale = false
    RETURN c.conclusion_id, c.verdict
    """
    new_cid = f"CONC_REV_{uuid.uuid4().hex[:8]}"
    res_new = g.query(q_persist_revised, {
        "cid": new_cid,
        "sid": session_id,
        "verdict": computed_verdict,
        "bypasses": active_bypasses,
        "prev_cid": prior_conc,
        "all_pass": behavioral_report["all_pass" if "all_pass" in behavioral_report else "all_passed"]
    }).result_set
    print(f"[{session_id}] Persisted Revised Conclusion node '{res_new[0][0]}' with verdict '{res_new[0][1]}' into FalkorDB.")

    print(f"=== [PROCESS 2] AGENT SESSION B COMPLETED WITH EXIT CODE 0 ===")
    return 0

if __name__ == "__main__":
    sys.exit(run_agent_session_b())
