import os
import secrets
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Header, Depends, Cookie, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from src.mandate.schema.db import FalkorClientManager
from src.mandate.tools.graph_tools import GraphTools
from src.mandate.eval.behavioral_tests import SyntheticBehavioralTestRunner
from src.mandate.schema.ingestion_pipeline import DocumentIngestionPipeline

app = FastAPI(title="Mandate FalkorDB Compliance Core API & Web Console", version="2.0.0")
db_mgr = FalkorClientManager()
tools = GraphTools(db_mgr)
pipeline = DocumentIngestionPipeline(db_mgr)
behavioral_runner = SyntheticBehavioralTestRunner()

# -------------------------------------------------------------
# AUTHENTICATED USER REGISTRY & SECURE SESSION STORE
# -------------------------------------------------------------
DEFAULT_TENANT_KEYS = {
    os.getenv("AETHERLEARN_API_KEY", "key_aetherlearn_live_9921"): "aetherlearn",
    os.getenv("NEXUSOPS_API_KEY", "key_nexusops_live_1104"): "nexusops"
}

TENANT_ACL: Dict[str, str] = DEFAULT_TENANT_KEYS

# Authenticated demo identities with explicitly allowed tenant scopes
DEMO_USERS = {
    "officer_alice": {
        "password": "alice_secret_compliance_2026",
        "name": "Alice Sharma (Senior DPDP Compliance Officer)",
        "allowed_tenants": ["aetherlearn"],
        "role": "COMPLIANCE_OFFICER"
    },
    "auditor_bob": {
        "password": "bob_secret_audit_2026",
        "name": "Bob Mehta (NexusOps Lead Auditor)",
        "allowed_tenants": ["nexusops"],
        "role": "EXTERNAL_AUDITOR"
    },
    "admin_super": {
        "password": "admin_master_secret_2026",
        "name": "Platform SuperAdmin",
        "allowed_tenants": ["aetherlearn", "nexusops"],
        "role": "SUPERADMIN"
    }
}

# Server-side authenticated sessions: token -> {user_id, active_tenant, allowed_tenants, csrf_token}
AUTHENTICATED_SESSIONS: Dict[str, Dict[str, Any]] = {}

def verify_tenant_auth(
    x_tenant_id: str = Header(..., description="Target tenant ID namespace"),
    x_api_key: str = Header(..., description="Secret tenant API access key")
) -> str:
    """
    Direct API authorization dependency for machine/test clients.
    """
    authorized_tenant = TENANT_ACL.get(x_api_key)
    if not authorized_tenant:
        raise HTTPException(status_code=401, detail="INVALID_API_KEY")
    if authorized_tenant != x_tenant_id:
        raise HTTPException(
            status_code=403,
            detail=f"FORBIDDEN: Provided API key is authorized for tenant '{authorized_tenant}', cannot access '{x_tenant_id}'."
        )
    return authorized_tenant

def get_current_session(
    mandate_session: Optional[str] = Cookie(None, description="Secure browser session token")
) -> Optional[Dict[str, Any]]:
    if mandate_session and mandate_session in AUTHENTICATED_SESSIONS:
        return AUTHENTICATED_SESSIONS[mandate_session]
    return None

def get_tenant_from_session_or_key(
    x_tenant_id: Optional[str] = Header(None, description="Target tenant ID namespace"),
    x_api_key: Optional[str] = Header(None, description="Secret tenant API access key"),
    mandate_session: Optional[str] = Cookie(None, description="Secure browser session token")
) -> str:
    """
    Strict resolver: rejects unauthenticated requests with 401.
    Never defaults to a fallback tenant.
    """
    if x_api_key:
        if not x_tenant_id:
            raise HTTPException(status_code=400, detail="MISSING_X_TENANT_ID_HEADER")
        return verify_tenant_auth(x_tenant_id, x_api_key)

    if mandate_session:
        session = AUTHENTICATED_SESSIONS.get(mandate_session)
        if not session:
            raise HTTPException(status_code=401, detail="INVALID_OR_EXPIRED_SESSION")
        target = x_tenant_id or session["active_tenant"]
        if target not in session["allowed_tenants"]:
            raise HTTPException(
                status_code=403,
                detail=f"FORBIDDEN: User '{session['user_id']}' is not authorized for tenant '{target}'."
            )
        return target

    raise HTTPException(status_code=401, detail="UNAUTHENTICATED_REQUEST")

def verify_csrf_write_protection(
    x_csrf_token: Optional[str] = Header(None, description="CSRF prevention header"),
    mandate_session: Optional[str] = Cookie(None, description="Secure browser session token"),
    x_api_key: Optional[str] = Header(None, description="API Key for automated calls")
):
    """
    Enforces same-origin CSRF validation for browser writes.
    API keys bypass browser cookie CSRF checks.
    """
    if x_api_key:
        return
    if mandate_session:
        session = AUTHENTICATED_SESSIONS.get(mandate_session)
        if not session or not x_csrf_token or x_csrf_token != session.get("csrf_token"):
            raise HTTPException(status_code=403, detail="CSRF_TOKEN_INVALID_OR_MISSING")

# -------------------------------------------------------------
# REQUEST SCHEMAS
# -------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: Optional[str] = None

class TenantSwitchRequest(BaseModel):
    tenant_id: str

class ProposalApprovalRequest(BaseModel):
    proposal_id: str
    duration_sec: Optional[int] = 300

class GuardedPatchRequest(BaseModel):
    task_id: str
    proposal_id: str
    agent_id: str
    fence_token: int
    idempotency_key: str
    human_approval_token: str
    expected_evidence_revision: Optional[str] = None

class UnseenDocumentRequest(BaseModel):
    doc_type: str
    filename: str
    content: str
    target_control_id: Optional[str] = None

# -------------------------------------------------------------
# AUTHENTICATION & APPROVAL ENDPOINTS
# -------------------------------------------------------------
@app.post("/api/v1/auth/login")
def login(req: LoginRequest, response: Response):
    user = DEMO_USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
    
    tenant = req.tenant_id or user["allowed_tenants"][0]
    if tenant not in user["allowed_tenants"]:
        raise HTTPException(status_code=403, detail=f"User not authorized for tenant '{tenant}'")

    session_id = secrets.token_hex(24)
    csrf_token = secrets.token_hex(16)
    AUTHENTICATED_SESSIONS[session_id] = {
        "user_id": req.username,
        "name": user["name"],
        "role": user["role"],
        "active_tenant": tenant,
        "allowed_tenants": user["allowed_tenants"],
        "csrf_token": csrf_token
    }

    response.set_cookie(
        key="mandate_session",
        value=session_id,
        httponly=True,
        samesite="strict"
    )
    return {
        "status": "SUCCESS",
        "username": req.username,
        "name": user["name"],
        "role": user["role"],
        "active_tenant": tenant,
        "allowed_tenants": user["allowed_tenants"],
        "csrf_token": csrf_token
    }

@app.post("/api/v1/auth/switch-tenant")
def switch_tenant(
    req: TenantSwitchRequest,
    session: Optional[Dict[str, Any]] = Depends(get_current_session)
):
    if not session:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")
    if req.tenant_id not in session["allowed_tenants"]:
        raise HTTPException(
            status_code=403,
            detail=f"FORBIDDEN: User '{session['user_id']}' cannot access tenant '{req.tenant_id}'"
        )
    session["active_tenant"] = req.tenant_id
    return {"status": "SUCCESS", "active_tenant": req.tenant_id}

@app.get("/api/v1/auth/me")
def get_current_user_profile(session: Optional[Dict[str, Any]] = Depends(get_current_session)):
    if not session:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "username": session["user_id"],
        "name": session["name"],
        "role": session["role"],
        "active_tenant": session["active_tenant"],
        "allowed_tenants": session["allowed_tenants"],
        "csrf_token": session["csrf_token"]
    }

@app.post("/api/v1/tenant/proposal/approve")
def approve_proposal(
    req: ProposalApprovalRequest,
    session: Optional[Dict[str, Any]] = Depends(get_current_session),
    tenant_id: str = Depends(get_tenant_from_session_or_key),
    _csrf: None = Depends(verify_csrf_write_protection)
):
    """
    Creates a server-signed, single-use ApprovalRecord bound to the authenticated user.
    """
    reviewer_id = session["user_id"] if session else "api_automated_signer"
    allowed_tenants = session["allowed_tenants"] if session else [tenant_id]

    res = tools.create_proposal_approval(
        tenant_id=tenant_id,
        proposal_id=req.proposal_id,
        reviewer_id=reviewer_id,
        allowed_tenants=allowed_tenants,
        duration_sec=req.duration_sec or 300
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res)
    return res

# -------------------------------------------------------------
# CORE API ENDPOINTS
# -------------------------------------------------------------
@app.get("/api/v1/tenant/state")
def get_tenant_full_state(tenant_id: str = Depends(get_tenant_from_session_or_key)):
    try:
        mgr = FalkorClientManager()
        g = mgr.get_tenant_graph(tenant_id)
        local_tools = GraphTools(mgr)
        contradictions = local_tools.traverse_contradictions(tenant_id)
        
        q_claims = """
        MATCH (c:Claim {tenant_id: $tenant_id})
        OPTIONAL MATCH (c)-[:HAS_INVALIDATION_HISTORY]->(evt:InvalidationEvent)
        RETURN c.claim_id, c.provision_id, c.assertion, c.status, c.is_stale,
               collect({event_id: evt.event_id, reason: evt.reason, timestamp: evt.timestamp})
        """
        res_claims = g.ro_query(q_claims, {"tenant_id": tenant_id}).result_set
        claims = []
        for r in res_claims:
            claims.append({
                "claim_id": r[0],
                "provision_id": r[1],
                "assertion": r[2],
                "status": r[3],
                "is_stale": r[4],
                "invalidation_history": [ev for ev in r[5] if ev.get("event_id")]
            })

        q_tasks = """
        MATCH (t:Task {tenant_id: $tenant_id})
        OPTIONAL MATCH (t)-[:EXECUTES_PROPOSAL]->(p:ActionProposal)
        RETURN t.task_id, t.type, t.status, t.owner_agent, t.lease_version,
               p.proposal_id, p.status, p.evidence_revision, p.enforce_strict_guardian_handshake
        """
        res_tasks = g.ro_query(q_tasks, {"tenant_id": tenant_id}).result_set
        tasks = []
        for r in res_tasks:
            tasks.append({
                "task_id": r[0],
                "type": r[1],
                "status": r[2],
                "owner": r[3],
                "fence_token": r[4],
                "proposal": {
                    "proposal_id": r[5],
                    "status": r[6],
                    "evidence_revision": r[7],
                    "handshake_enforced": r[8]
                } if r[5] else None
            })

        q_vendor = "MATCH (v:Vendor {tenant_id: $tenant_id}) RETURN v.vendor_id, v.name, v.enforce_strict_guardian_handshake"
        res_v = g.ro_query(q_vendor, {"tenant_id": tenant_id}).result_set
        vendor = {"vendor_id": res_v[0][0], "name": res_v[0][1], "strict_handshake": res_v[0][2]} if res_v else {}
    except Exception:
        contradictions = []
        claims = []
        tasks = []
        vendor = {"vendor_id": "VND_01", "name": "KiddCheck ID", "strict_handshake": False}

    return {
        "tenant_id": tenant_id,
        "vendor": vendor,
        "contradictions": contradictions,
        "claims": claims,
        "tasks": tasks
    }

@app.get("/api/v1/tenant/contradictions")
def get_contradictions(tenant_id: str = Depends(get_tenant_from_session_or_key)):
    return {
        "tenant_id": tenant_id,
        "contradictions": tools.traverse_contradictions(tenant_id)
    }

@app.post("/api/v1/tenant/apply-patch")
def apply_guarded_patch(
    req: GuardedPatchRequest,
    tenant_id: str = Depends(get_tenant_from_session_or_key),
    _csrf: None = Depends(verify_csrf_write_protection)
):
    result = tools.apply_remediation_patch(
        tenant_id=tenant_id,
        task_id=req.task_id,
        proposal_id=req.proposal_id,
        agent_id=req.agent_id,
        fence_token=req.fence_token,
        idempotency_key=req.idempotency_key,
        human_approval_token=req.human_approval_token,
        expected_evidence_revision=req.expected_evidence_revision
    )
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result)
    return result

@app.get("/api/v1/tenant/behavioral-suite")
def run_behavioral_suite(tenant_id: str = Depends(get_tenant_from_session_or_key)):
    try:
        mgr = FalkorClientManager()
        g = mgr.get_tenant_graph(tenant_id)
        q_vendor = "MATCH (v:Vendor {vendor_id: 'VND_01', tenant_id: $tenant_id}) RETURN v.enforce_strict_guardian_handshake"
        res_v = g.ro_query(q_vendor, {"tenant_id": tenant_id}).result_set
        strict_handshake = bool(res_v[0][0]) if res_v and res_v[0][0] is not None else False

        q_bypass = "MATCH (df:DataFlow {flow_id: 'DF_01', tenant_id: $tenant_id})-[:BYPASSES]->(ctl:Control) RETURN count(df)"
        res_b = g.ro_query(q_bypass, {"tenant_id": tenant_id}).result_set
        has_bypass = (res_b[0][0] > 0) if res_b else True
    except Exception:
        strict_handshake = False
        has_bypass = True
    
    suite_result = behavioral_runner.evaluate(
        vendor_strict_handshake=strict_handshake,
        guest_sso_bypass=has_bypass
    )
    return {
        "tenant_id": tenant_id,
        "live_config": {
            "strict_guardian_handshake": strict_handshake,
            "guest_sso_bypass_active": has_bypass
        },
        "suite_result": suite_result
    }

@app.post("/api/v1/tenant/ingest-unseen-document")
def ingest_unseen_doc(
    req: UnseenDocumentRequest,
    tenant_id: str = Depends(get_tenant_from_session_or_key)
):
    result = pipeline.ingest_unseen_document(
        tenant_id=tenant_id,
        doc_type=req.doc_type,
        filename=req.filename,
        raw_text=req.content,
        target_control_id=req.target_control_id
    )
    return result

@app.get("/api/v1/legal/provisions")
def get_legal_provisions():
    g_pub = db_mgr.get_public_graph()
    q = "MATCH (p:LegalProvision) RETURN p.provision_id, p.section, p.title, p.legal_status, p.effective_from, p.commencement_basis"
    res = g_pub.ro_query(q).result_set
    provisions = []
    for r in res:
        provisions.append({
            "provision_id": r[0],
            "section": r[1],
            "title": r[2],
            "legal_status": r[3],
            "effective_from": r[4],
            "commencement_basis": r[5]
        })
    return {"provisions": provisions}

@app.get("/api/v1/tenant/claim/{claim_id}")
def get_claim(
    claim_id: str,
    tenant_id: str = Depends(get_tenant_from_session_or_key)
):
    g = db_mgr.get_tenant_graph(tenant_id)
    query = """
    MATCH (c:Claim {claim_id: $claim_id, tenant_id: $tenant_id})
    OPTIONAL MATCH (c)-[:HAS_INVALIDATION_HISTORY]->(evt:InvalidationEvent)
    RETURN c.claim_id AS id,
           c.status AS status,
           c.is_stale AS is_stale,
           collect(evt.reason) AS reasons
    """
    res = g.ro_query(query, {"claim_id": claim_id, "tenant_id": tenant_id}).result_set
    if not res:
        raise HTTPException(status_code=404, detail="CLAIM_NOT_FOUND")
    return {
        "tenant_id": tenant_id,
        "claim_id": res[0][0],
        "status": res[0][1],
        "is_stale": res[0][2],
        "invalidation_history": res[0][3]
    }

# -------------------------------------------------------------
# WEB CONSOLE HTML SERVING
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def get_web_console():
    template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)
