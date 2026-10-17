import urllib.request
import json
import time

def run_browser_flow():
    # 0. Clean Seed to Pre-Patch
    from src.mandate.schema.seed_public import seed_regulatory_corpus
    from src.mandate.schema.seed_tenants import seed_flagship_aetherlearn, seed_isolated_nexusops
    from src.mandate.schema.db import FalkorClientManager
    mgr = FalkorClientManager()
    seed_regulatory_corpus(mgr)
    seed_flagship_aetherlearn(mgr, "aetherlearn")
    seed_isolated_nexusops(mgr, "nexusops")

    # 1. Verify pre-patch state
    req = urllib.request.Request(
        'http://127.0.0.1:8000/api/v1/tenant/state',
        headers={'x-api-key': 'key_aetherlearn_live_9921', 'x-tenant-id': 'aetherlearn'}
    )
    res = urllib.request.urlopen(req)
    pre_st = json.loads(res.read().decode())
    pre_bypasses = [c for c in pre_st['contradictions'] if c['bypassed_control']]

    req_suite = urllib.request.Request(
        'http://127.0.0.1:8000/api/v1/tenant/behavioral-suite',
        headers={'x-api-key': 'key_aetherlearn_live_9921', 'x-tenant-id': 'aetherlearn'}
    )
    res_suite = urllib.request.urlopen(req_suite)
    suite_data = json.loads(res_suite.read().decode())['suite_result']

    pre_badge = "MODELED_CONTROL_TESTS_PASS" if (len(pre_bypasses) == 0 and pre_st['vendor']['strict_handshake'] and suite_data['all_passed']) else "FAILING_CONTROLS_DETECTED"

    print("==================================================")
    print("PHASE 1: FRESH PRE-PATCH SCREEN STATE")
    print("==================================================")
    print(f"Vendor Strict Handshake : {pre_st['vendor']['strict_handshake']}")
    print(f"Active Bypass Edges     : {len(pre_bypasses)}")
    print(f"Behavioral Suite        : {suite_data['passed_cases']} / {suite_data['total_cases']} PASSED (all_passed={suite_data['all_passed']})")
    print(f"Console Case Badge      : {pre_badge}")
    print("==================================================\n")

    # 2. Simulate User Clicking 'Authorize & Apply Guarded Patch' in Browser UI
    print("Executing uninterrupted browser workflow...")
    # Step A: Login
    login_body = json.dumps({'username': 'officer_alice', 'password': 'alice_secret_compliance_2026'}).encode()
    login_req = urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/login', data=login_body, headers={'Content-Type': 'application/json'})
    login_res = urllib.request.urlopen(login_req)
    session_cookie = login_res.headers.get('Set-Cookie')
    csrf = json.loads(login_res.read().decode())['csrf_token']
    print("-> Step A (Session): Officer Alice authenticated; CSRF token acquired.")

    # Step B: Lease Acquisition
    lease_body = json.dumps({'task_id': 'TSK_REMED_01', 'agent_id': 'agent_worker_console', 'duration_ms': 15000}).encode()
    lease_req = urllib.request.Request('http://127.0.0.1:8000/api/v1/tenant/task/lease', data=lease_body, headers={'Content-Type': 'application/json', 'Cookie': session_cookie, 'X-CSRF-Token': csrf})
    lease_res = urllib.request.urlopen(lease_req)
    fence_token = json.loads(lease_res.read().decode())['fence_token']
    print(f"-> Step B (Lease): Task lease acquired; monotonic fence_token={fence_token}")

    # Step C: Single-Use Human Approval Record
    appr_body = json.dumps({'proposal_id': 'PROP_REMED_01', 'duration_sec': 300}).encode()
    appr_req = urllib.request.Request('http://127.0.0.1:8000/api/v1/tenant/proposal/approve', data=appr_body, headers={'Content-Type': 'application/json', 'Cookie': session_cookie, 'X-CSRF-Token': csrf})
    appr_res = urllib.request.urlopen(appr_req)
    appr_token = json.loads(appr_res.read().decode())['approval_token']
    print(f"-> Step C (Signature): Single-use reviewer signature generated: {appr_token[:22]}...")

    # Step D: Apply Single-Query Atomic Cypher Patch
    patch_body = json.dumps({
        'task_id': 'TSK_REMED_01',
        'proposal_id': 'PROP_REMED_01',
        'agent_id': 'agent_worker_console',
        'fence_token': fence_token,
        'idempotency_key': f'IDEM-BROWSER-E2E-{int(time.time()*1000)}',
        'human_approval_token': appr_token,
        'expected_evidence_revision': 'REV_EV_ENG_8419_v1'
    }).encode()
    patch_req = urllib.request.Request('http://127.0.0.1:8000/api/v1/tenant/apply-patch', data=patch_body, headers={'Content-Type': 'application/json', 'Cookie': session_cookie, 'X-CSRF-Token': csrf})
    patch_res = urllib.request.urlopen(patch_req)
    patch_out = json.loads(patch_res.read().decode())
    print(f"-> Step D (Commit): Single-query Cypher patch applied: {patch_out['reason']} (applied={patch_out['applied']})\n")

    # 3. Post-Patch Screen State Verification
    req_post = urllib.request.Request('http://127.0.0.1:8000/api/v1/tenant/state', headers={'Cookie': session_cookie})
    res_post = urllib.request.urlopen(req_post)
    post_st = json.loads(res_post.read().decode())
    post_bypasses = [c for c in post_st['contradictions'] if c['bypassed_control']]

    req_post_suite = urllib.request.Request('http://127.0.0.1:8000/api/v1/tenant/behavioral-suite', headers={'Cookie': session_cookie})
    res_post_suite = urllib.request.urlopen(req_post_suite)
    post_suite_data = json.loads(res_post_suite.read().decode())['suite_result']

    post_badge = "MODELED_CONTROL_TESTS_PASS" if (len(post_bypasses) == 0 and post_st['vendor']['strict_handshake'] and post_suite_data['all_passed']) else "FAILING_CONTROLS_DETECTED"

    print("==================================================")
    print("PHASE 2: POST-PATCH SCREEN STATE (POST-APPROVAL)")
    print("==================================================")
    print(f"Vendor Strict Handshake : {post_st['vendor']['strict_handshake']}")
    print(f"Active Bypass Edges     : {len(post_bypasses)}")
    print(f"Behavioral Suite        : {post_suite_data['passed_cases']} / {post_suite_data['total_cases']} PASSED (all_passed={post_suite_data['all_passed']})")
    print(f"Console Case Badge      : {post_badge}")
    print("==================================================")

    assert post_st['vendor']['strict_handshake'] is True
    assert len(post_bypasses) == 0
    assert post_suite_data['passed_cases'] == 8
    assert post_badge == "MODELED_CONTROL_TESTS_PASS"

if __name__ == '__main__':
    run_browser_flow()
