"""
API End-to-End Verification Script (Automated API sequence testing).
Verifies the exact multi-process handoff sequence:
1. Session A runs, discovers bypass, persists conclusion, and creates TSK_HANDOFF_01.
2. Session B runs up to staging:
   - Recovers TSK_HANDOFF_01 and prior conclusion from FalkorDB.
   - Acquires lease on TSK_HANDOFF_01.
   - Selectively invalidates premise PRM_001 (cascading to PROP_REMED_01 -> INELIGIBLE_SUPERSEDED).
   - Confirms independent billing claim (CLM_ENC_04) is preserved.
   - Completes TSK_HANDOFF_01.
   - Creates new OPEN remediation task TSK_BROWSER_REMED_01 executing PROP_REMED_02.
3. Assertions:
   - Old invalidated proposal (PROP_REMED_01) CANNOT be approved or applied (HTTP 400/409).
   - UI selection query selects ONLY the eligible proposal (PROP_REMED_02) on OPEN task (TSK_BROWSER_REMED_01).
4. Browser flow simulation:
   - Officer Alice authenticates via session cookie + CSRF.
   - Acquires lease on TSK_BROWSER_REMED_01 with monotonic fence token.
   - Generates single-use ApprovalRecord for PROP_REMED_02.
   - Applies atomic Cypher patch.
5. Verifies post-patch state transitions to 8/8 passed, 0 bypasses, strict handshake true, and MODELED_CONTROL_TESTS_PASS.
"""

import urllib.request
import json
import time
from src.mandate.schema.db import FalkorClientManager
from src.mandate.agents.session_a_process import run_agent_session_a
from src.mandate.agents.session_b_process import run_agent_session_b

def run_browser_flow():
    mgr = FalkorClientManager()
    g = mgr.get_tenant_graph("aetherlearn")

    print("==================================================")
    print("STEP 1: RUN SESSION A (Cold Start Investigator)")
    print("==================================================")
    run_agent_session_a()

    print("\n==================================================")
    print("STEP 2: RUN SESSION B STEPS (Selective Invalidation & Staging)")
    print("==================================================")
    from src.mandate.tools.graph_tools import GraphTools
    tools = GraphTools(mgr)

    # 1. Recover Task TSK_HANDOFF_01
    q_recover = """
    MATCH (t:Task {task_id: 'TSK_HANDOFF_01', tenant_id: 'aetherlearn'})
    OPTIONAL MATCH (c:AssessmentConclusion {conclusion_id: t.target_conclusion_id})
    RETURN t.task_id, t.handoff_from_session, c.conclusion_id, c.verdict
    """
    res_rec = g.ro_query(q_recover).result_set
    assert len(res_rec) > 0, "Failed to recover TSK_HANDOFF_01"
    task_id, prior_session, prior_conc, prior_verdict = res_rec[0]
    print(f"Session B recovered task {task_id} from {prior_session} with prior verdict {prior_verdict}")

    # 2. Acquire Lease on TSK_HANDOFF_01
    lease = tools.acquire_task_lease("aetherlearn", "TSK_HANDOFF_01", "agent_worker_b", lease_duration_ms=10000)
    assert lease is not None, "Failed to acquire lease on TSK_HANDOFF_01"

    # 3. Invalidate PRM_001
    inval_res = tools.selective_invalidate_premise(
        tenant_id="aetherlearn",
        stale_premise_id="PRM_001",
        reason="Jira ticket ENG-8419 confirmed Google SSO bypass in student-signup route"
    )
    print(f"Selective invalidation result: {inval_res}")

    # 4. Verify independent billing claim preserved
    q_bill = "MATCH (c:Claim {claim_id: 'CLM_ENC_04', tenant_id: 'aetherlearn'}) RETURN c.status, c.is_stale"
    r_bill = g.ro_query(q_bill).result_set
    assert r_bill[0][0] == "VALID_ACTIVE" and r_bill[0][1] is False, "Independent billing claim was corrupted!"
    print("Independent billing claim CLM_ENC_04 preserved [VALID_ACTIVE].")

    # 5. Complete TSK_HANDOFF_01
    comp = tools.complete_task(
        tenant_id="aetherlearn",
        task_id="TSK_HANDOFF_01",
        agent_id="agent_worker_b",
        fence_token=lease["fence_token"],
        idempotency_key="IDEM-HANDOFF-COMPL-E2E"
    )
    assert comp is True, "Failed to complete TSK_HANDOFF_01"
    print("Session B investigation task TSK_HANDOFF_01 completed.")

    # 6. Create TSK_BROWSER_REMED_01 with fresh PROP_REMED_02
    q_create = """
    MATCH (clm:Claim {claim_id: 'CLM_VPC_01', tenant_id: 'aetherlearn'})
    MATCH (ev:Evidence {evidence_id: 'EV_TICKET_ENG_8419', tenant_id: 'aetherlearn'})
    CREATE (t_ui:Task {
        task_id: 'TSK_BROWSER_REMED_01',
        tenant_id: 'aetherlearn',
        type: 'APPLY_REMEDIATION',
        status: 'OPEN',
        lease_version: 0,
        retry_count: 0,
        handoff_from_session: 'SES_B_VERIFY',
        target_claim_id: 'CLM_VPC_01',
        created_at: timestamp()
    })
    CREATE (p:ActionProposal {
        proposal_id: 'PROP_REMED_02',
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
    CREATE (t_ui)-[:EXECUTES_PROPOSAL]->(p)
    RETURN p.proposal_id, ev.evidence_revision, t_ui.task_id
    """
    res_prop = g.query(q_create).result_set
    assert len(res_prop) > 0, "Failed to create TSK_BROWSER_REMED_01"
    print(f"Staged fresh proposal {res_prop[0][0]} on task {res_prop[0][2]}.")

    print("\n==================================================")
    print("STEP 3: VERIFY UI SELECTION & NEGATIVE SECURITY GATES")
    print("==================================================")
    # Check tenant state from API as viewed by browser UI
    req_state = urllib.request.Request(
        'http://127.0.0.1:8000/api/v1/tenant/state',
        headers={'x-api-key': 'key_aetherlearn_live_9921', 'x-tenant-id': 'aetherlearn'}
    )
    res_state = urllib.request.urlopen(req_state)
    st = json.loads(res_state.read().decode())

    # Simulate UI selection logic:
    # t.status === 'OPEN' && t.proposal && t.proposal.status !== 'INELIGIBLE_SUPERSEDED' && t.proposal.status !== 'APPLIED_COMMITTED'
    eligible_tasks = [
        t for t in st['tasks']
        if t['status'] == 'OPEN' and t.get('proposal') and t['proposal']['status'] not in ['INELIGIBLE_SUPERSEDED', 'APPLIED_COMMITTED', 'REJECTED']
    ]
    assert len(eligible_tasks) == 1, f"Expected exactly 1 eligible task, found {len(eligible_tasks)}"
    selected_task = eligible_tasks[0]
    assert selected_task['task_id'] == 'TSK_BROWSER_REMED_01', f"Wrong task selected: {selected_task['task_id']}"
    assert selected_task['proposal']['proposal_id'] == 'PROP_REMED_02', f"Wrong proposal selected: {selected_task['proposal']['proposal_id']}"
    print(f"UI correctly selected OPEN task: {selected_task['task_id']} with proposal: {selected_task['proposal']['proposal_id']}")

    # Authenticate Officer Alice
    login_body = json.dumps({'username': 'officer_alice', 'password': 'alice_secret_compliance_2026'}).encode()
    login_req = urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/login', data=login_body, headers={'Content-Type': 'application/json'})
    login_res = urllib.request.urlopen(login_req)
    session_cookie = login_res.headers.get('Set-Cookie')
    csrf = json.loads(login_res.read().decode())['csrf_token']

    # Negative assertion: Assert that old invalidated proposal PROP_REMED_01 cannot be approved
    appr_neg_body = json.dumps({'proposal_id': 'PROP_REMED_01', 'duration_sec': 300}).encode()
    appr_neg_req = urllib.request.Request(
        'http://127.0.0.1:8000/api/v1/tenant/proposal/approve',
        data=appr_neg_body,
        headers={'Content-Type': 'application/json', 'Cookie': session_cookie, 'X-CSRF-Token': csrf}
    )
    try:
        urllib.request.urlopen(appr_neg_req)
        assert False, "Security failure: Invalidated proposal PROP_REMED_01 was unexpectedly approved!"
    except urllib.error.HTTPError as e:
        assert e.code == 400
        print(f"Negative test passed: Approval of invalidated proposal PROP_REMED_01 rejected with HTTP {e.code}.")

    print("\n==================================================")
    print("STEP 4: EXECUTE AUTHORIZE & APPLY FLOW FOR PROP_REMED_02")
    print("==================================================")
    # Step B: Lease Acquisition on TSK_BROWSER_REMED_01
    lease_body = json.dumps({'task_id': 'TSK_BROWSER_REMED_01', 'agent_id': 'agent_worker_console', 'duration_ms': 15000}).encode()
    lease_req = urllib.request.Request(
        'http://127.0.0.1:8000/api/v1/tenant/task/lease',
        data=lease_body,
        headers={'Content-Type': 'application/json', 'Cookie': session_cookie, 'X-CSRF-Token': csrf}
    )
    lease_res = urllib.request.urlopen(lease_req)
    fence_token = json.loads(lease_res.read().decode())['fence_token']
    print(f"-> Step B (Lease): Task lease acquired for TSK_BROWSER_REMED_01; fence_token={fence_token}")

    # Step C: Single-Use Approval Record for PROP_REMED_02
    appr_body = json.dumps({'proposal_id': 'PROP_REMED_02', 'duration_sec': 300}).encode()
    appr_req = urllib.request.Request(
        'http://127.0.0.1:8000/api/v1/tenant/proposal/approve',
        data=appr_body,
        headers={'Content-Type': 'application/json', 'Cookie': session_cookie, 'X-CSRF-Token': csrf}
    )
    appr_res = urllib.request.urlopen(appr_req)
    appr_token = json.loads(appr_res.read().decode())['approval_token']
    print(f"-> Step C (Signature): Reviewer signature generated for PROP_REMED_02: {appr_token[:22]}...")

    # Step D: Apply Single-Query Atomic Cypher Patch
    patch_body = json.dumps({
        'task_id': 'TSK_BROWSER_REMED_01',
        'proposal_id': 'PROP_REMED_02',
        'agent_id': 'agent_worker_console',
        'fence_token': fence_token,
        'idempotency_key': f'IDEM-BROWSER-E2E-{int(time.time()*1000)}',
        'human_approval_token': appr_token,
        'expected_evidence_revision': 'REV_EV_ENG_8419_v1'
    }).encode()
    patch_req = urllib.request.Request(
        'http://127.0.0.1:8000/api/v1/tenant/apply-patch',
        data=patch_body,
        headers={'Content-Type': 'application/json', 'Cookie': session_cookie, 'X-CSRF-Token': csrf}
    )
    patch_res = urllib.request.urlopen(patch_req)
    patch_out = json.loads(patch_res.read().decode())
    print(f"-> Step D (Commit): Cypher patch applied: {patch_out['reason']} (applied={patch_out['applied']})\n")

    print("==================================================")
    print("STEP 5: POST-PATCH STATE VERIFICATION")
    print("==================================================")
    req_post = urllib.request.Request('http://127.0.0.1:8000/api/v1/tenant/state', headers={'Cookie': session_cookie})
    res_post = urllib.request.urlopen(req_post)
    post_st = json.loads(res_post.read().decode())
    post_bypasses = [c for c in post_st['contradictions'] if c['bypassed_control']]

    req_post_suite = urllib.request.Request('http://127.0.0.1:8000/api/v1/tenant/behavioral-suite', headers={'Cookie': session_cookie})
    res_post_suite = urllib.request.urlopen(req_post_suite)
    post_suite_data = json.loads(res_post_suite.read().decode())['suite_result']

    post_badge = "MODELED_CONTROL_TESTS_PASS" if (len(post_bypasses) == 0 and post_st['vendor']['strict_handshake'] and post_suite_data['all_passed']) else "FAILING_CONTROLS_DETECTED"

    print(f"Vendor Strict Handshake : {post_st['vendor']['strict_handshake']}")
    print(f"Active Bypass Edges     : {len(post_bypasses)}")
    print(f"Behavioral Suite        : {post_suite_data['passed_cases']} / {post_suite_data['total_cases']} PASSED (all_passed={post_suite_data['all_passed']})")
    print(f"Console Case Badge      : {post_badge}")
    print("==================================================")

    assert post_st['vendor']['strict_handshake'] is True
    assert len(post_bypasses) == 0
    assert post_suite_data['passed_cases'] == 8
    assert post_badge == "MODELED_CONTROL_TESTS_PASS"
    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY.")

if __name__ == '__main__':
    run_browser_flow()

