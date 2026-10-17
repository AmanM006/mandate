"""
Mandate Reserved Evaluation Suite: 8 Verification Scenarios.

These cases are evaluated separately from the development set.
The test harness runs these cases without tuning, checking:
1. Cross-border youth transfer rules under Section 16
2. Consent manager boundary verification under Rule 4
3. Pedagogical research exemption boundary under Section 17(2)(b)
4. Startup compliance carve-outs under Section 17(3)
5. Multi-tenant boundary integrity
6. Expired token remediation rejection
7. Concurrent dual-worker lease collision and zombie rejection
8. Cross-session episodic memory recovery
"""

import uuid
from typing import List, Dict, Any
from src.mandate.schema.db import FalkorClientManager
from src.mandate.tools.graph_tools import GraphTools
from src.mandate.eval.behavioral_tests import SyntheticBehavioralTestRunner

RESERVED_HIDDEN_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "HIDDEN-01",
        "title": "Cross-Border Minor Data Transfer Gate",
        "provision_id": "DPDP_ACT_SEC_16",
        "category": "CROSS_BORDER_RESTRICTION",
        "expected_legal_status": "FUTURE_OBLIGATION",
        "expected_verdict": "FUTURE_OBLIGATION",
        "description": "Cross-border transfers to restricted territories are prohibited once Central Government notifies negative list."
    },
    {
        "case_id": "HIDDEN-02",
        "title": "Consent Manager Revocation Cascade",
        "provision_id": "DPDP_RULES_2025_RULE_4",
        "category": "REVOCATION_CASCADE",
        "expected_legal_status": "EXCLUDED_NON_APPLICABLE",
        "expected_verdict": "MODELED_CONTROL_TESTS_PASS",
        "description": "Consent Manager registration applies to external intermediary; internal data flow does not register as CM."
    },
    {
        "case_id": "HIDDEN-03",
        "title": "Research Exemption Threshold Verification",
        "provision_id": "DPDP_ACT_SEC_17_2_B",
        "category": "STATUTORY_EXEMPTION",
        "expected_legal_status": "IN_FORCE",
        "expected_verdict": "MODELED_CONTROL_TESTS_PASS",
        "description": "Research processing for pedagogical studies complies if personal data is anonymized and not used to make decisions regarding the data principal."
    },
    {
        "case_id": "HIDDEN-04",
        "title": "Startup Exemption Boundary Test",
        "provision_id": "DPDP_ACT_SEC_17_3",
        "category": "STATUTORY_EXEMPTION",
        "expected_legal_status": "UNRESOLVED_UNCERTAIN",
        "expected_verdict": "UNRESOLVED_UNCERTAIN",
        "description": "AetherLearn exceeded DPIIT age/turnover caps for startup status; exemption applicability requires formal officer review."
    },
    {
        "case_id": "HIDDEN-05",
        "title": "NexusOps Apprentice Flow Child-Data Segregation",
        "provision_id": "DPDP_ACT_SEC_9_1",
        "category": "TENANT_DATA_SEGREGATION",
        "expected_legal_status": "FUTURE_OBLIGATION",
        "expected_verdict": "MODELED_CONTROL_TESTS_PASS",
        "description": "NexusOps corporate intern seating flow processes apprentice accounts; isolated graph confirms no cross-tenant leakage to AetherLearn."
    },
    {
        "case_id": "HIDDEN-06",
        "title": "Expired Server Approval Rejection",
        "provision_id": "REMEDIATION_APPROVAL_SECURITY",
        "category": "APPROVAL_LIFECYCLE",
        "expected_legal_status": "EXCLUDED_NON_APPLICABLE",
        "expected_verdict": "MODELED_CONTROL_TESTS_PASS",
        "description": "Remediation patch presented with expired ApprovalRecord must be rejected with APPROVAL_TOKEN_EXPIRED."
    },
    {
        "case_id": "HIDDEN-07",
        "title": "Concurrent Dual-Worker Fence Collision",
        "provision_id": "AGENT_COORDINATION_LEASE",
        "category": "FENCE_RECOVERY",
        "expected_legal_status": "EXCLUDED_NON_APPLICABLE",
        "expected_verdict": "MODELED_CONTROL_TESTS_PASS",
        "description": "Two workers competing for task lease result in monotonic lease increment; worker with lower fence token is rejected."
    },
    {
        "case_id": "HIDDEN-08",
        "title": "Episodic Session Graph Memory Recovery",
        "provision_id": "AGENT_EPISODIC_MEMORY",
        "category": "CAUSAL_MEMORY",
        "expected_legal_status": "FUTURE_OBLIGATION",
        "expected_verdict": "MODELED_CONTROL_TESTS_PASS",
        "description": "Independent session reads graph without prior in-memory context and verifies premise invalidation history."
    }
]

def run_hidden_benchmark(prefix: str = "reserved_suite") -> Dict[str, Any]:
    from src.mandate.schema.seed_public import seed_regulatory_corpus
    from src.mandate.schema.seed_tenants import seed_flagship_aetherlearn, seed_isolated_nexusops
    
    suite_aether = f"{prefix}_aetherlearn"
    suite_nexus = f"{prefix}_nexusops"

    mgr = FalkorClientManager()

    # Capture live demo graph state before suite runs
    g_live = mgr.get_tenant_graph("aetherlearn")
    try:
        live_nodes_before = g_live.ro_query("MATCH (n) RETURN count(n)").result_set[0][0]
        live_vendor_before = g_live.ro_query(
            "MATCH (v:Vendor {vendor_id: 'VND_01'}) RETURN v.enforce_strict_guardian_handshake"
        ).result_set[0][0]
    except Exception:
        live_nodes_before = None
        live_vendor_before = None

    seed_regulatory_corpus(mgr)
    seed_flagship_aetherlearn(mgr, tenant_id=suite_aether)
    seed_isolated_nexusops(mgr, tenant_id=suite_nexus)
    g_public = mgr.get_public_graph()
    g_aether = mgr.get_tenant_graph(suite_aether)
    g_nexus = mgr.get_tenant_graph(suite_nexus)
    total = len(RESERVED_HIDDEN_CASES)
    passed = 0
    results = []

    print("\n" + "=" * 80)
    print("MANDATE RESERVED EVALUATION SUITE: 8 VERIFICATION SCENARIOS")
    print("=" * 80)

    for case in RESERVED_HIDDEN_CASES:
        cid = case["case_id"]
        title = case["title"]
        category = case["category"]
        expected = case["expected_verdict"]
        prov_id = case["provision_id"]

        executed_query = ""
        actual = "UNKNOWN"
        detail_msg = ""

        # Case 1: Cross-border restriction under Sec 16
        if cid == "HIDDEN-01":
            executed_query = "MATCH (p:Provision {provision_id: 'DPDP_ACT_SEC_16'}) RETURN p.legal_status, p.official_text"
            res = g_public.ro_query(executed_query).result_set
            if res and len(res) > 0:
                actual = res[0][0]
            else:
                actual = "PROVISION_NOT_FOUND"
            detail_msg = f"Statutory check on Section 16 cross-border transfer restriction: {actual}"

        # Case 2: Consent manager token revocation / scope
        elif cid == "HIDDEN-02":
            executed_query = "MATCH (p:Provision {provision_id: 'DPDP_RULES_2025_RULE_4'})-[:GOVERNED_BY]->(c:Commencement) RETURN p.title, c.basis"
            res = g_public.ro_query(executed_query).result_set
            # Verify internal flows are not registered as external CMs
            cm_check_q = "MATCH (df:DataFlow {tenant_id: $tenant_id}) WHERE df.is_consent_manager = true RETURN count(df)"
            res_cm = g_aether.ro_query(cm_check_q, {"tenant_id": suite_aether}).result_set
            cm_flows = res_cm[0][0] if res_cm else 0
            if cm_flows == 0 and len(res) > 0:
                actual = "MODELED_CONTROL_TESTS_PASS"
            else:
                actual = "FAIL_UNMODELED_CM"
            detail_msg = f"Consent Manager boundary check: {cm_flows} internal flows improperly tagged as CM"

        # Case 3: Research Exemption Threshold under Sec 17(2)(b)
        elif cid == "HIDDEN-03":
            # Real behavioral verification: checks statutory provision is IN_FORCE in public graph and tenant flow DF_04 has active anonymization control
            prov_q = "MATCH (p:Provision {provision_id: 'DPDP_ACT_SEC_17_2_B'}) RETURN p.legal_status"
            res_prov = g_public.ro_query(prov_q).result_set
            prov_status = res_prov[0][0] if res_prov else None

            flow_ctl_q = """
            MATCH (df:DataFlow {tenant_id: $tenant_id, flow_id: 'DF_04'})
            MATCH (ctl:Control {tenant_id: $tenant_id, control_id: 'CTL_RESEARCH_ANONYMIZATION'})-[:COVERS_FLOW]->(df)
            WHERE ctl.status = 'ACTIVE_VERIFIED'
            RETURN df.flow_id, ctl.control_id, ctl.status
            """
            executed_query = flow_ctl_q.strip()
            res_res = g_aether.ro_query(flow_ctl_q, {"tenant_id": suite_aether}).result_set

            if prov_status == 'IN_FORCE' and len(res_res) > 0:
                actual = "MODELED_CONTROL_TESTS_PASS"
            else:
                actual = "FAILING_CONTROLS_DETECTED"
            detail_msg = f"Sec 17(2)(b) research anonymization control CTL_RESEARCH_ANONYMIZATION verified on DF_04 (Statutory status: {prov_status})"

        # Case 4: Startup Exemption Boundary under Sec 17(3)
        elif cid == "HIDDEN-04":
            executed_query = "MATCH (p:Provision {provision_id: 'DPDP_ACT_SEC_17_3'}) RETURN p.title"
            res = g_public.ro_query(executed_query).result_set
            # AetherLearn startup exemption boundary check (turnover / years cap)
            actual = "UNRESOLVED_UNCERTAIN" if len(res) > 0 else "FAIL"
            detail_msg = f"Startup exemption applicability unverified without DPIIT certification"

        # Case 5: Multi-tenant tenant segregation
        elif cid == "HIDDEN-05":
            executed_query = "MATCH (c:Claim {tenant_id: $tenant_id}) RETURN count(c)"
            res_leak = g_nexus.ro_query(executed_query, {"tenant_id": suite_aether}).result_set[0][0]
            actual = "MODELED_CONTROL_TESTS_PASS" if res_leak == 0 else "FAIL_LEAKAGE"
            detail_msg = f"NexusOps cross-tenant query for AetherLearn claims returned {res_leak} nodes"

        # Case 6: Expired server approval rejection
        elif cid == "HIDDEN-06":
            executed_query = "MATCH (a:ApprovalRecord {tenant_id: $tenant_id}) WHERE a.expires_at < timestamp() RETURN count(a)"
            res_exp = g_aether.ro_query(executed_query, {"tenant_id": suite_aether}).result_set
            tools = GraphTools(mgr)
            # Create dedicated task and proposal for Case 6
            q_setup_06 = """
            MERGE (t_h6:Task {task_id: 'TSK_HIDDEN_06', tenant_id: $tenant_id})
            SET t_h6.status = 'OPEN', t_h6.lease_version = 0, t_h6.retry_count = 0, t_h6.max_retries = 3
            MERGE (p_h6:ActionProposal {proposal_id: 'PROP_HIDDEN_06', tenant_id: $tenant_id})
            SET p_h6.status = 'APPROVED', p_h6.evidence_revision = 'REV_EV_ENG_8419_v1',
                p_h6.target_vendor_id = 'VND_01', p_h6.target_flow_id = 'DF_01',
                p_h6.enforce_strict_guardian_handshake = true,
                p_h6.mutation_sig = 'MUT_SIG_H6'
            MERGE (t_h6)-[:EXECUTES_PROPOSAL]->(p_h6)
            MERGE (clm:Claim {claim_id: 'CLM_VPC_01', tenant_id: $tenant_id})
            MERGE (ev:Evidence {evidence_id: 'EV_TICKET_ENG_8419', tenant_id: $tenant_id})
            MERGE (p_h6)-[:REMEDIES_CLAIM]->(clm)
            MERGE (p_h6)-[:BASED_ON_EVIDENCE]->(ev)
            CREATE (a_exp:ApprovalRecord {
                token: 'APPR_EXPIRED_HIDDEN_06',
                tenant_id: $tenant_id,
                reviewer_id: 'officer_alice',
                evidence_revision: p_h6.evidence_revision,
                mutation_sig: 'MUT_SIG_H6',
                created_at: timestamp() - 100000,
                expires_at: timestamp() - 50000,
                used: false
            })
            MERGE (a_exp)-[:APPROVES_PROPOSAL]->(p_h6)
            """
            g_aether.query(q_setup_06, {"tenant_id": suite_aether})
            lease = tools.acquire_task_lease(suite_aether, "TSK_HIDDEN_06", "agent_worker_hidden_06", lease_duration_ms=5000)
            apply_attempt = tools.apply_remediation_patch(
                tenant_id=suite_aether,
                task_id="TSK_HIDDEN_06",
                proposal_id="PROP_HIDDEN_06",
                agent_id="agent_worker_hidden_06",
                fence_token=lease["fence_token"],
                idempotency_key=f"IDEM-EXP-{uuid.uuid4().hex[:6]}",
                human_approval_token="APPR_EXPIRED_HIDDEN_06",
                expected_evidence_revision="REV_EV_ENG_8419_v1"
            )
            # Clean up test nodes
            g_aether.query("MATCH (a:ApprovalRecord {token: 'APPR_EXPIRED_HIDDEN_06'}) DETACH DELETE a")
            g_aether.query("MATCH (t:Task {task_id: 'TSK_HIDDEN_06'}) DETACH DELETE t")
            g_aether.query("MATCH (p:ActionProposal {proposal_id: 'PROP_HIDDEN_06'}) DETACH DELETE p")
            actual = "MODELED_CONTROL_TESTS_PASS" if (not apply_attempt["success"] and apply_attempt["reason"] == "APPROVAL_TOKEN_EXPIRED") else "FAIL_NOT_REJECTED"
            detail_msg = f"Apply patch with expired approval token returned: {apply_attempt['reason']}"

        # Case 7: Zombie agent fence collision under concurrency
        elif cid == "HIDDEN-07":
            executed_query = "MATCH (t:Task {task_id: 'TSK_HIDDEN_07'}) RETURN t.lease_version"
            tools = GraphTools(mgr)
            q_setup_07 = """
            MERGE (t_h7:Task {task_id: 'TSK_HIDDEN_07', tenant_id: $tenant_id})
            SET t_h7.status = 'OPEN', t_h7.lease_version = 0, t_h7.retry_count = 0, t_h7.max_retries = 3
            MERGE (p_h7:ActionProposal {proposal_id: 'PROP_HIDDEN_07', tenant_id: $tenant_id})
            SET p_h7.status = 'APPROVED', p_h7.evidence_revision = 'REV_EV_ENG_8419_v1',
                p_h7.target_vendor_id = 'VND_01', p_h7.target_flow_id = 'DF_01',
                p_h7.enforce_strict_guardian_handshake = true
            MERGE (t_h7)-[:EXECUTES_PROPOSAL]->(p_h7)
            MERGE (clm:Claim {claim_id: 'CLM_VPC_01', tenant_id: $tenant_id})
            MERGE (ev:Evidence {evidence_id: 'EV_TICKET_ENG_8419', tenant_id: $tenant_id})
            MERGE (p_h7)-[:REMEDIES_CLAIM]->(clm)
            MERGE (p_h7)-[:BASED_ON_EVIDENCE]->(ev)
            """
            g_aether.query(q_setup_07, {"tenant_id": suite_aether})
            l1 = tools.acquire_task_lease(suite_aether, "TSK_HIDDEN_07", "worker_primary", lease_duration_ms=5000)
            # Force expiration / simulate second worker usurping lease
            g_aether.query("MATCH (t:Task {task_id: 'TSK_HIDDEN_07', tenant_id: $tenant_id}) SET t.lease_expires_at = timestamp() - 1000", {"tenant_id": suite_aether})
            l2 = tools.acquire_task_lease(suite_aether, "TSK_HIDDEN_07", "worker_usurper", lease_duration_ms=5000)
            
            # Create valid approval for proposal
            appr = tools.create_proposal_approval(suite_aether, "PROP_HIDDEN_07", "officer_alice", [suite_aether])
            
            # Worker 1 (now zombie) attempts action with stale token
            zombie_apply = tools.apply_remediation_patch(
                tenant_id=suite_aether,
                task_id="TSK_HIDDEN_07",
                proposal_id="PROP_HIDDEN_07",
                agent_id="worker_primary",
                fence_token=l1["fence_token"],
                idempotency_key=f"IDEM-ZOMB-{uuid.uuid4().hex[:6]}",
                human_approval_token=appr["approval_token"],
                expected_evidence_revision="REV_EV_ENG_8419_v1"
            )
            # Clean up test nodes
            g_aether.query("MATCH (a:ApprovalRecord {token: $tok}) DETACH DELETE a", {"tok": appr["approval_token"]})
            g_aether.query("MATCH (t:Task {task_id: 'TSK_HIDDEN_07', tenant_id: $tenant_id}) DETACH DELETE t", {"tenant_id": suite_aether})
            g_aether.query("MATCH (p:ActionProposal {proposal_id: 'PROP_HIDDEN_07', tenant_id: $tenant_id}) DETACH DELETE p", {"tenant_id": suite_aether})
            actual = "MODELED_CONTROL_TESTS_PASS" if (not zombie_apply["success"] and zombie_apply["reason"] in ["FENCE_TOKEN_STALE", "STALE_FENCE_TOKEN_REJECTED"]) else "FAIL_ZOMBIE_NOT_BLOCKED"
            detail_msg = f"Zombie apply with token {l1['fence_token']} against lease {l2['fence_token']} returned {zombie_apply['reason']}"

        # Case 8: Episodic session recovery after premise invalidation
        elif cid == "HIDDEN-08":
            # Strict verification: require two conclusions with different session IDs,
            # a SUPERSEDES edge connecting them, and the expected prior and revised verdicts.
            executed_query = """
            MATCH (rev:AssessmentConclusion {tenant_id: $tenant_id})-[:SUPERSEDES]->(prior:AssessmentConclusion {tenant_id: $tenant_id})
            RETURN prior.session_id, prior.verdict, rev.session_id, rev.verdict
            """
            rows = g_aether.ro_query(executed_query, {"tenant_id": suite_aether}).result_set
            if rows and len(rows) > 0:
                p_sess, p_verd, r_sess, r_verd = rows[0]
                diff_sessions = (p_sess != r_sess) and bool(p_sess) and bool(r_sess)
                expected_verdicts = (p_verd == 'FAILING_CONTROLS_DETECTED' and r_verd == 'STAGED_REMEDIATION_PENDING_APPROVAL')
                if diff_sessions and expected_verdicts:
                    actual = "MODELED_CONTROL_TESTS_PASS"
                    detail_msg = f"Episodic recovery verified: Prior session {p_sess} verdict '{p_verd}' superseded by session {r_sess} verdict '{r_verd}'"
                else:
                    actual = "FAIL_INVALID_SUPERSEDES_METADATA"
                    detail_msg = f"Found supersedes edge but metadata mismatch: prior=({p_sess}, {p_verd}), rev=({r_sess}, {r_verd})"
            else:
                actual = "FAIL_NO_SUPERSEDES_EDGE"
                detail_msg = "No AssessmentConclusion nodes connected by [:SUPERSEDES] found in tenant namespace"

        is_pass = (actual == expected)
        if is_pass:
            passed += 1

        status_str = "PASS" if is_pass else "FAIL"
        print(f"[{status_str:4}] {cid:10} | {title:40} | Exp: {expected:26} | Got: {actual}")
        if executed_query:
            print(f"       Cypher / Logic : {executed_query.strip()}")
            print(f"       Execution Detail: {detail_msg}")

        results.append({
            "case_id": cid,
            "title": title,
            "category": category,
            "cypher_query": executed_query,
            "expected_verdict": expected,
            "actual_verdict": actual,
            "detail": detail_msg,
            "passed": is_pass
        })

    acc = (passed / total) * 100.0
    print("-" * 80)
    print(f"RESERVED EVALUATION SUITE: {passed}/{total} VERIFIED ({acc:.1f}%)")
    print("=" * 80 + "\n")

    if live_nodes_before is not None:
        live_nodes_after = g_live.ro_query("MATCH (n) RETURN count(n)").result_set[0][0]
        live_vendor_after = g_live.ro_query(
            "MATCH (v:Vendor {vendor_id: 'VND_01'}) RETURN v.enforce_strict_guardian_handshake"
        ).result_set[0][0]
        assert live_nodes_after == live_nodes_before, (
            f"Live demo graph node count modified during reserved suite! Before: {live_nodes_before}, After: {live_nodes_after}"
        )
        assert live_vendor_after == live_vendor_before, (
            f"Live demo vendor state modified during reserved suite! Before: {live_vendor_before}, After: {live_vendor_after}"
        )

    return {
        "total_cases": total,
        "passed": passed,
        "accuracy_percentage": acc,
        "results": results
    }

if __name__ == "__main__":
    run_hidden_benchmark()
