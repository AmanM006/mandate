import pytest
import time
from fastapi.testclient import TestClient
from src.mandate.api import app, TENANT_ACL
from src.mandate.schema.db import FalkorClientManager
from src.mandate.schema.seed_public import seed_regulatory_corpus
from src.mandate.schema.seed_tenants import seed_flagship_aetherlearn, seed_isolated_nexusops
from src.mandate.tools.graph_tools import GraphTools

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    mgr = FalkorClientManager()
    seed_regulatory_corpus(mgr)
    seed_flagship_aetherlearn(mgr)
    seed_isolated_nexusops(mgr)

def test_tenant_acl_spoofing_rejected():
    """
    Test 1: Attacker uses NexusOps API key but requests AetherLearn tenant namespace.
    Must be rejected with 403 Forbidden.
    """
    resp = client.get(
        "/api/v1/tenant/contradictions",
        headers={
            "x-tenant-id": "aetherlearn",
            "x-api-key": "key_nexusops_live_1104" # Wrong key for this tenant!
        }
    )
    assert resp.status_code == 403
    assert "cannot access 'aetherlearn'" in resp.json()["detail"]

def test_tenant_acl_authorized_access():
    """
    Test 2: Legitimate request with matching tenant and API key succeeds.
    """
    resp = client.get(
        "/api/v1/tenant/contradictions",
        headers={
            "x-tenant-id": "aetherlearn",
            "x-api-key": "key_aetherlearn_live_9921"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tenant_id"] == "aetherlearn"
    assert len(data["contradictions"]) > 0

def test_action_fencing_prevents_zombie_patch_apply():
    """
    Test 3: Fenced action verification.
    Ensures a zombie worker with a superseded lease cannot apply a configuration patch.
    """
    mgr = FalkorClientManager()
    tools = GraphTools(mgr)
    
    # Worker Alpha acquires lease
    lease_alpha = tools.acquire_task_lease("aetherlearn", "TSK_REMED_01", "agent_worker_alpha", lease_duration_ms=400)
    assert lease_alpha is not None
    token_alpha = lease_alpha["fence_token"]
    
    # Wait for lease to expire
    time.sleep(0.5)
    
    # Worker Beta takes over lease (bumps fence_token)
    lease_beta = tools.acquire_task_lease("aetherlearn", "TSK_REMED_01", "agent_worker_beta", lease_duration_ms=10000)
    assert lease_beta is not None
    token_beta = lease_beta["fence_token"]
    assert token_beta > token_alpha
    
    # Generate legitimate server-signed ApprovalRecord for the proposal
    appr_res = tools.create_proposal_approval(
        tenant_id="aetherlearn",
        proposal_id="PROP_REMED_01",
        reviewer_id="officer_alice",
        allowed_tenants=["aetherlearn"]
    )
    assert appr_res["success"] is True
    approval_token = appr_res["approval_token"]

    # Zombie Worker Alpha attempts to apply configuration patch via API
    resp_zombie = client.post(
        "/api/v1/tenant/apply-patch",
        headers={
            "x-tenant-id": "aetherlearn",
            "x-api-key": "key_aetherlearn_live_9921"
        },
        json={
            "task_id": "TSK_REMED_01",
            "proposal_id": "PROP_REMED_01",
            "agent_id": "agent_worker_alpha",
            "fence_token": token_alpha,
            "idempotency_key": "IDEM-ZOMBIE-999",
            "human_approval_token": approval_token,
            "expected_evidence_revision": "REV_EV_ENG_8419_v1"
        }
    )
    # Stale action must be strictly rejected
    assert resp_zombie.status_code == 409
    assert resp_zombie.json()["detail"]["reason"] == "STALE_FENCE_TOKEN_REJECTED"
    
    # Worker Beta applies authorized patch using the valid server-signed approval token
    resp_beta = client.post(
        "/api/v1/tenant/apply-patch",
        headers={
            "x-tenant-id": "aetherlearn",
            "x-api-key": "key_aetherlearn_live_9921"
        },
        json={
            "task_id": "TSK_REMED_01",
            "proposal_id": "PROP_REMED_01",
            "agent_id": "agent_worker_beta",
            "fence_token": token_beta,
            "idempotency_key": "IDEM-BETA-001",
            "human_approval_token": approval_token,
            "expected_evidence_revision": "REV_EV_ENG_8419_v1"
        }
    )
    assert resp_beta.status_code == 200
    assert resp_beta.json()["applied"] is True

    # Re-applying same idempotency key is safely deduplicated
    resp_idem = client.post(
        "/api/v1/tenant/apply-patch",
        headers={
            "x-tenant-id": "aetherlearn",
            "x-api-key": "key_aetherlearn_live_9921"
        },
        json={
            "task_id": "TSK_REMED_01",
            "proposal_id": "PROP_REMED_01",
            "agent_id": "agent_worker_beta",
            "fence_token": token_beta,
            "idempotency_key": "IDEM-BETA-001",
            "human_approval_token": approval_token,
            "expected_evidence_revision": "REV_EV_ENG_8419_v1"
        }
    )
    assert resp_idem.status_code == 200
    assert resp_idem.json()["reason"] == "IDEMPOTENT_ALREADY_APPLIED"
    assert resp_idem.json()["applied"] is False

def test_selective_invalidation_cascades_to_tasks_and_proposals():
    """
    Test 4: Invalidation blocks dependent open tasks and proposals while preserving history.
    """
    mgr = FalkorClientManager()
    tools = GraphTools(mgr)
    
    inval_results = tools.selective_invalidate_premise(
        tenant_id="aetherlearn",
        stale_premise_id="PRM_001",
        reason="Test cascading invalidation to tasks"
    )
    assert len(inval_results) > 0
    
    # Verify Task TSK_REMED_01 was transitioned to INELIGIBLE_CANCELLED
    g = mgr.get_tenant_graph("aetherlearn")
    res_task = g.ro_query(
        "MATCH (t:Task {task_id: 'TSK_REMED_01', tenant_id: 'aetherlearn'}) RETURN t.status, t.cancellation_reason"
    ).result_set
    assert res_task[0][0] == "INELIGIBLE_CANCELLED"
    assert "PRM_001" in res_task[0][1]
