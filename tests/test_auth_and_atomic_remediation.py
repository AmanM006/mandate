import pytest
import time
from fastapi.testclient import TestClient
from src.mandate.api import app, AUTHENTICATED_SESSIONS
from src.mandate.schema.db import FalkorClientManager
from src.mandate.schema.seed_public import seed_regulatory_corpus
from src.mandate.schema.seed_tenants import seed_flagship_aetherlearn, seed_isolated_nexusops
from src.mandate.tools.graph_tools import GraphTools

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    AUTHENTICATED_SESSIONS.clear()
    mgr = FalkorClientManager()
    seed_regulatory_corpus(mgr)
    seed_flagship_aetherlearn(mgr)
    seed_isolated_nexusops(mgr)

def test_unauthenticated_requests_rejected_with_401():
    """
    Test 1: Unauthenticated request to /api/v1/tenant/state without session or API key.
    Must return 401 Unauthorized (never defaults to AetherLearn).
    """
    resp = client.get("/api/v1/tenant/state")
    assert resp.status_code == 401
    assert "UNAUTHENTICATED_REQUEST" in resp.json()["detail"]

    resp_patch = client.post(
        "/api/v1/tenant/apply-patch",
        json={
            "task_id": "TSK_REMED_01",
            "proposal_id": "PROP_REMED_01",
            "agent_id": "agent_alpha",
            "fence_token": 1,
            "idempotency_key": "IDEM-UNAUTH-01",
            "human_approval_token": "APPR_FAKE"
        }
    )
    assert resp_patch.status_code == 401

def test_cross_tenant_session_spoofing_rejected():
    """
    Test 2: Auditor Bob (authorized only for nexusops) logs in, attempts to access aetherlearn.
    Must be rejected with 403 Forbidden.
    """
    # Login as Bob
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "auditor_bob", "password": "bob_secret_audit_2026"}
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["active_tenant"] == "nexusops"

    # Try accessing Aetherlearn with Bob's cookie session
    resp = client.get(
        "/api/v1/tenant/state",
        headers={"x-tenant-id": "aetherlearn"}
    )
    assert resp.status_code == 403
    assert "not authorized for tenant 'aetherlearn'" in resp.json()["detail"]

def test_forged_approval_token_rejected():
    """
    Test 3: Caller tries to supply arbitrary APPR_HUMAN_ string without server-created ApprovalRecord.
    Must be rejected by single-query atomic validation with INVALID_APPROVAL_RECORD.
    """
    mgr = FalkorClientManager()
    tools = GraphTools(mgr)
    lease = tools.acquire_task_lease("aetherlearn", "TSK_REMED_01", "agent_worker_alice", lease_duration_ms=10000)
    assert lease is not None

    resp = client.post(
        "/api/v1/tenant/apply-patch",
        headers={
            "x-tenant-id": "aetherlearn",
            "x-api-key": "key_aetherlearn_live_9921"
        },
        json={
            "task_id": "TSK_REMED_01",
            "proposal_id": "PROP_REMED_01",
            "agent_id": "agent_worker_alice",
            "fence_token": lease["fence_token"],
            "idempotency_key": "IDEM-FORGE-01",
            "human_approval_token": "APPR_HUMAN_CALLER_INVENTED_TOKEN",
            "expected_evidence_revision": "REV_EV_ENG_8419_v1"
        }
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["reason"] == "INVALID_APPROVAL_RECORD"

def test_single_use_approval_double_spend_rejected():
    """
    Test 4: A server-signed ApprovalRecord can only be consumed once.
    Concurrent or repeated attempts must fail with APPROVAL_TOKEN_ALREADY_USED.
    """
    mgr = FalkorClientManager()
    tools = GraphTools(mgr)
    lease = tools.acquire_task_lease("aetherlearn", "TSK_REMED_01", "agent_worker_primary", lease_duration_ms=10000)
    assert lease is not None

    # Server creates legitimate ApprovalRecord
    appr_res = tools.create_proposal_approval(
        tenant_id="aetherlearn",
        proposal_id="PROP_REMED_01",
        reviewer_id="officer_alice",
        allowed_tenants=["aetherlearn"]
    )
    token = appr_res["approval_token"]

    # First apply succeeds
    resp1 = client.post(
        "/api/v1/tenant/apply-patch",
        headers={
            "x-tenant-id": "aetherlearn",
            "x-api-key": "key_aetherlearn_live_9921"
        },
        json={
            "task_id": "TSK_REMED_01",
            "proposal_id": "PROP_REMED_01",
            "agent_id": "agent_worker_primary",
            "fence_token": lease["fence_token"],
            "idempotency_key": "IDEM-FIRST-RUN",
            "human_approval_token": token,
            "expected_evidence_revision": "REV_EV_ENG_8419_v1"
        }
    )
    assert resp1.status_code == 200
    assert resp1.json()["applied"] is True

    # Second attempt with different idempotency key but same approval token must be rejected
    resp2 = client.post(
        "/api/v1/tenant/apply-patch",
        headers={
            "x-tenant-id": "aetherlearn",
            "x-api-key": "key_aetherlearn_live_9921"
        },
        json={
            "task_id": "TSK_REMED_01",
            "proposal_id": "PROP_REMED_01",
            "agent_id": "agent_worker_primary",
            "fence_token": lease["fence_token"],
            "idempotency_key": "IDEM-SECOND-RUN",
            "human_approval_token": token,
            "expected_evidence_revision": "REV_EV_ENG_8419_v1"
        }
    )
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["reason"] == "APPROVAL_TOKEN_ALREADY_USED"

def test_intermediate_invalidation_between_approval_and_apply_rejects_patch():
    """
    Test 5: Intermediate invalidation occurs after proposal approval but before execution.
    Atomic Cypher check verifies proposal eligibility and rejects execution without modifying vendor config.
    """
    mgr = FalkorClientManager()
    tools = GraphTools(mgr)
    g = mgr.get_tenant_graph("aetherlearn")

    # Worker leases task
    lease = tools.acquire_task_lease("aetherlearn", "TSK_REMED_01", "agent_worker_mid", lease_duration_ms=10000)
    assert lease is not None

    # Server generates approval
    appr_res = tools.create_proposal_approval(
        tenant_id="aetherlearn",
        proposal_id="PROP_REMED_01",
        reviewer_id="officer_alice",
        allowed_tenants=["aetherlearn"]
    )
    token = appr_res["approval_token"]

    # Upstream invalidation occurs: premise PRM_001 is invalidated, which marks proposal INELIGIBLE_SUPERSEDED
    tools.selective_invalidate_premise(
        tenant_id="aetherlearn",
        stale_premise_id="PRM_001",
        reason="Upstream engineering change invalidated baseline premise"
    )

    # Worker attempts apply: must fail atomically
    resp = client.post(
        "/api/v1/tenant/apply-patch",
        headers={
            "x-tenant-id": "aetherlearn",
            "x-api-key": "key_aetherlearn_live_9921"
        },
        json={
            "task_id": "TSK_REMED_01",
            "proposal_id": "PROP_REMED_01",
            "agent_id": "agent_worker_mid",
            "fence_token": lease["fence_token"],
            "idempotency_key": "IDEM-MID-INVAL",
            "human_approval_token": token,
            "expected_evidence_revision": "REV_EV_ENG_8419_v1"
        }
    )
    assert resp.status_code == 409
    assert ("PROPOSAL_NOT_APPROVED" in resp.json()["detail"]["reason"] or "PROPOSAL_INELIGIBLE" in resp.json()["detail"]["reason"])

    # Verify vendor configuration remained UNCHANGED (strict handshake remains false)
    q_vendor = "MATCH (v:Vendor {vendor_id: 'VND_01', tenant_id: 'aetherlearn'}) RETURN v.enforce_strict_guardian_handshake"
    res_v = g.ro_query(q_vendor).result_set
    assert res_v[0][0] is False or res_v[0][0] is None

def test_atomic_preconditions_reject_swapped_task_evidence_mutation_and_missing_vendor():
    """
    Test 6: Strict Atomicity and Precondition Invariants.
    1. Swapping in a mismatched Task-Proposal relationship fails.
    2. Modifying Evidence revision in graph immediately before apply causes query to fail atomically.
    3. Missing target Vendor in proposal aborts write.
    In all cases: ApprovalRecord is NOT consumed and Vendor configuration is NOT modified.
    """
    mgr = FalkorClientManager()
    tools = GraphTools(mgr)
    g = mgr.get_tenant_graph("aetherlearn")

    # 1. Swapping in a different Task ID
    g.query("MERGE (t2:Task {task_id: 'TSK_OTHER_99', tenant_id: 'aetherlearn'}) SET t2.status='IN_PROGRESS', t2.owner_agent='agent_rogue', t2.lease_version=1")
    appr1 = tools.create_proposal_approval("aetherlearn", "PROP_REMED_01", "officer_alice", ["aetherlearn"])
    token1 = appr1["approval_token"]

    resp_swap = client.post(
        "/api/v1/tenant/apply-patch",
        headers={"x-tenant-id": "aetherlearn", "x-api-key": "key_aetherlearn_live_9921"},
        json={
            "task_id": "TSK_OTHER_99", # Unbound task!
            "proposal_id": "PROP_REMED_01",
            "agent_id": "agent_rogue",
            "fence_token": 1,
            "idempotency_key": "IDEM-SWAP-TASK",
            "human_approval_token": token1,
            "expected_evidence_revision": "REV_EV_ENG_8419_v1"
        }
    )
    assert resp_swap.status_code == 409
    assert resp_swap.json()["detail"]["reason"] == "TASK_PROPOSAL_MISMATCH"

    # Verify token1 was NOT marked as used
    res_tok1 = g.ro_query("MATCH (a:ApprovalRecord {token: $tok}) RETURN a.used", {"tok": token1}).result_set
    assert res_tok1[0][0] is False

    # 2. Evidence revision mutated in graph right before apply
    lease = tools.acquire_task_lease("aetherlearn", "TSK_REMED_01", "agent_worker_precond", lease_duration_ms=10000)
    appr2 = tools.create_proposal_approval("aetherlearn", "PROP_REMED_01", "officer_alice", ["aetherlearn"])
    token2 = appr2["approval_token"]

    # Modify underlying evidence revision in graph
    g.query("MATCH (ev:Evidence {evidence_id: 'EV_TICKET_ENG_8419', tenant_id: 'aetherlearn'}) SET ev.evidence_revision = 'REV_EV_ENG_8419_v2_MUTATED'")

    resp_ev = client.post(
        "/api/v1/tenant/apply-patch",
        headers={"x-tenant-id": "aetherlearn", "x-api-key": "key_aetherlearn_live_9921"},
        json={
            "task_id": "TSK_REMED_01",
            "proposal_id": "PROP_REMED_01",
            "agent_id": "agent_worker_precond",
            "fence_token": lease["fence_token"],
            "idempotency_key": "IDEM-MUTATED-EV",
            "human_approval_token": token2,
            "expected_evidence_revision": "REV_EV_ENG_8419_v1"
        }
    )
    assert resp_ev.status_code == 409
    assert resp_ev.json()["detail"]["reason"] == "EVIDENCE_GRAPH_REVISION_MISMATCH"

    # Verify token2 was NOT used
    res_tok2 = g.ro_query("MATCH (a:ApprovalRecord {token: $tok}) RETURN a.used", {"tok": token2}).result_set
    assert res_tok2[0][0] is False

    # 3. Missing target Vendor
    # Create proposal with non-existent vendor
    g.query("""
    MERGE (t3:Task {task_id: 'TSK_NOVENDOR_01', tenant_id: 'aetherlearn'})
    SET t3.status = 'IN_PROGRESS', t3.owner_agent = 'agent_novendor', t3.lease_version = 1
    MERGE (p3:ActionProposal {proposal_id: 'PROP_NOVENDOR_01', tenant_id: 'aetherlearn'})
    SET p3.target_vendor_id = 'VND_DOES_NOT_EXIST', p3.status = 'APPROVED', p3.evidence_revision = 'REV_1'
    MERGE (t3)-[:EXECUTES_PROPOSAL]->(p3)
    """)
    appr3 = tools.create_proposal_approval("aetherlearn", "PROP_NOVENDOR_01", "officer_alice", ["aetherlearn"])
    token3 = appr3["approval_token"]

    resp_novendor = client.post(
        "/api/v1/tenant/apply-patch",
        headers={"x-tenant-id": "aetherlearn", "x-api-key": "key_aetherlearn_live_9921"},
        json={
            "task_id": "TSK_NOVENDOR_01",
            "proposal_id": "PROP_NOVENDOR_01",
            "agent_id": "agent_novendor",
            "fence_token": 1,
            "idempotency_key": "IDEM-NOVENDOR",
            "human_approval_token": token3,
            "expected_evidence_revision": "REV_1"
        }
    )
    assert resp_novendor.status_code == 409
    assert resp_novendor.json()["detail"]["reason"] == "TARGET_VENDOR_NOT_FOUND"

    res_tok3 = g.ro_query("MATCH (a:ApprovalRecord {token: $tok}) RETURN a.used", {"tok": token3}).result_set
    assert res_tok3[0][0] is False

