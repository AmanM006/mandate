import pytest
from src.mandate.schema.db import FalkorClientManager
from src.mandate.tools.graph_tools import GraphTools
from src.mandate.schema.seed_public import seed_regulatory_corpus
from src.mandate.schema.seed_tenants import seed_flagship_aetherlearn, seed_isolated_nexusops

@pytest.fixture(autouse=True)
def setup_test_db():
    mgr = FalkorClientManager()
    seed_regulatory_corpus(mgr)
    seed_flagship_aetherlearn(mgr, tenant_id="test_mut_aether")
    seed_isolated_nexusops(mgr, tenant_id="test_mut_nexus")

def test_decisive_evidence_edge_mutation_changes_verdict():
    """
    Mutation Test:
    When the decisive contradiction edge (ev_ticket -[:CONTRADICTS]-> ctl_vpc) is removed,
    the control status changes and the bypass contradiction is cleared.
    """
    mgr = FalkorClientManager()
    g = mgr.get_tenant_graph("test_mut_aether")
    tools = GraphTools(mgr)

    # 1. Baseline: contradiction present
    contra_before = tools.traverse_contradictions("test_mut_aether")
    active_before = [c for c in contra_before if c["bypassed_control"]]
    assert len(active_before) >= 1

    # Ask Mandate before mutation
    ans_before = tools.ask_mandate("test_mut_aether", "Why is youth signup flagged?")
    assert ans_before["verdict"] == "FAILING_CONTROL_BYPASS_DETECTED"

    # 2. Mutate: Remove the contradiction and bypass edge
    g.query("MATCH (df:DataFlow {flow_id: 'DF_01', tenant_id: 'test_mut_aether'})-[b:BYPASSES]->(ctl:Control) DELETE b")
    g.query("MATCH (ev:Evidence {evidence_id: 'EV_TICKET_ENG_8419', tenant_id: 'test_mut_aether'})-[c:CONTRADICTS]->(ctl:Control) DELETE c")

    # 3. Post-mutation: Traversal and verdict must change
    contra_after = tools.traverse_contradictions("test_mut_aether")
    active_after = [c for c in contra_after if c["bypassed_control"]]
    assert len(active_after) == 0

    ans_after = tools.ask_mandate("test_mut_aether", "Why is youth signup flagged?")
    assert ans_after["verdict"] == "NO_ACTIVE_BYPASS"

def test_selective_premise_invalidation_preserves_unrelated_billing_claim():
    """
    Mutation Test:
    Invalidating PRM_001 invalidates downstream CLM_VPC_01 but leaves independent
    billing encryption claim CLM_ENC_04 intact (VALID_ACTIVE, is_stale=False).
    """
    mgr = FalkorClientManager()
    tools = GraphTools(mgr)
    g = mgr.get_tenant_graph("test_mut_aether")

    # Invalidate PRM_001
    inval_res = tools.selective_invalidate_premise(
        tenant_id="test_mut_aether",
        stale_premise_id="PRM_001",
        reason="Mutation test intentional premise invalidation"
    )
    assert len(inval_res) > 0

    # CLM_VPC_01 must be INVALIDATED_STALE
    q_vpc = "MATCH (c:Claim {claim_id: 'CLM_VPC_01', tenant_id: 'test_mut_aether'}) RETURN c.status, c.is_stale"
    r_vpc = g.ro_query(q_vpc).result_set
    assert r_vpc[0][0] == "INVALIDATED_STALE"
    assert r_vpc[0][1] is True

    # Unrelated CLM_ENC_04 must survive VALID_ACTIVE and NOT stale
    q_bill = "MATCH (c:Claim {claim_id: 'CLM_ENC_04', tenant_id: 'test_mut_aether'}) RETURN c.status, c.is_stale"
    r_bill = g.ro_query(q_bill).result_set
    assert r_bill[0][0] == "VALID_ACTIVE"
    assert r_bill[0][1] is False
