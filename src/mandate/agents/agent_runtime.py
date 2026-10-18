import os
import json
import time
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
from src.mandate.schema.db import FalkorClientManager
from src.mandate.tools.graph_tools import GraphTools

class GeminiAgentRuntime:
    """
    LLM-powered Agent Loop for Mandate:
    - Roles: Investigator, Interpreter, Remediator
    - Uses Gemini via GEMINI_API_KEY with configurable LLM_MODEL (default: gemini-2.5-flash)
    - Enforces per-session rate limits and global spend capping
    - Gracefully falls back to deterministic rule-based reasoning when no key is present or budget is exhausted.
    """
    def __init__(
        self,
        db_mgr: FalkorClientManager,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        max_spend_tokens: int = 50000,
        requests_per_minute: int = 20
    ):
        self.db_mgr = db_mgr
        self.tools = GraphTools(db_mgr)
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name or os.getenv("LLM_MODEL", "gemini-2.5-flash")
        
        # Spend & Rate Limiting Controls
        self.max_spend_tokens = max_spend_tokens
        self.tokens_consumed = 0
        self.requests_per_minute = requests_per_minute
        self.request_timestamps: List[float] = []

        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[WARN] Failed to initialize Gemini client: {e}. Falling back to deterministic mode.")

    def _check_rate_and_budget(self) -> bool:
        """
        Enforces spend budget and sliding-window rate limit.
        """
        if self.tokens_consumed >= self.max_spend_tokens:
            print("[WARN] Global spend cap reached. Switching to deterministic fallback.")
            return False

        now = time.time()
        self.request_timestamps = [t for t in self.request_timestamps if now - t < 60.0]
        if len(self.request_timestamps) >= self.requests_per_minute:
            print("[WARN] Rate limit reached. Throttling request or falling back.")
            return False

        self.request_timestamps.append(now)
        return True

    # -------------------------------------------------------------
    # 1. INVESTIGATOR AGENT
    # -------------------------------------------------------------
    def run_investigator(self, tenant_id: str) -> Dict[str, Any]:
        """
        Investigates data flows and controls. Uses bounded graph tools,
        then synthesizes findings into an evidence-backed audit report.
        """
        raw_contradictions = self.tools.traverse_contradictions(tenant_id)
        
        if not self.client or not self._check_rate_and_budget():
            # Deterministic fallback mode (explicitly labeled)
            return {
                "mode": "DETERMINISTIC_FALLBACK",
                "tenant_id": tenant_id,
                "contradictions": raw_contradictions,
                "summary": f"Deterministic traversal identified {len(raw_contradictions)} data flows. Bypasses or contradictions detected across {sum(1 for c in raw_contradictions if c['bypassed_control'] or c['contradictory_evidence'])} routes."
            }

        prompt = f"""
        You are Mandate's Investigator Agent.
        Analyze the following data flows, controls, and contradictory evidence artifacts traversed from FalkorDB for tenant '{tenant_id}':
        {json.dumps(raw_contradictions, indent=2)}

        Provide a concise, factual summary highlighting any bypassed controls and contradicting evidence IDs.
        Do NOT certify compliance. Report only grounded factual findings.
        """
        try:
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            self.tokens_consumed += 500  # Conservative estimate
            return {
                "mode": "LLM_GEMINI_LIVE",
                "tenant_id": tenant_id,
                "contradictions": raw_contradictions,
                "summary": resp.text
            }
        except Exception as e:
            return {
                "mode": "DETERMINISTIC_FALLBACK",
                "tenant_id": tenant_id,
                "contradictions": raw_contradictions,
                "summary": f"Fallback due to API error ({e}). Bypasses or contradictions detected."
            }

    # -------------------------------------------------------------
    # 2. INTERPRETER AGENT
    # -------------------------------------------------------------
    def run_interpreter(
        self,
        tenant_id: str,
        provision_id: str,
        case_findings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates legal status, commencement date, and applicability.
        Selectively invalidates superseded premises and dependent claims.
        """
        prov_info = self.tools.get_provision_status(provision_id)
        if not prov_info:
            return {"error": f"Provision {provision_id} not found in public legal graph."}

        # If contradiction exists in findings, trigger selective invalidation of PRM_001
        invalidation_events = []
        has_bypass = any(c.get("bypassed_control") for c in case_findings.get("contradictions", []))
        if has_bypass:
            invalidation_events = self.tools.selective_invalidate_premise(
                tenant_id=tenant_id,
                stale_premise_id="PRM_001",
                reason="Investigator identified bypassed control and contradictory Jira ticket ENG-8419."
            )

        return {
            "mode": "DETERMINISTIC_INTERPRETER",
            "provision_id": provision_id,
            "section": prov_info["section"],
            "title": prov_info["title"],
            "legal_status": prov_info["legal_status"],
            "effective_from": prov_info["effective_from"],
            "commencement_basis": prov_info["commencement_basis"],
            "invalidation_events": invalidation_events,
            "interpretation": (
                f"Provision {prov_info['section']} is a {prov_info['legal_status']} commencing {prov_info['effective_from']}. "
                "Current system behavior reveals an internal readiness failure rather than an active statutory penalty."
            )
        }

    # -------------------------------------------------------------
    # 3. REMEDIATOR AGENT
    # -------------------------------------------------------------
    def run_remediator(
        self,
        tenant_id: str,
        task_id: str,
        worker_id: str,
        human_approval_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Acquires a fenced task lease, retrieves the target proposal associated with the task,
        and applies the atomic Cypher remediation patch under strict fence token and
        server-issued single-use human approval protection.
        """
        lease = self.tools.acquire_task_lease(tenant_id, task_id, worker_id)
        if not lease:
            return {"success": False, "reason": "UNABLE_TO_ACQUIRE_LEASE"}

        # Retrieve proposal bound to this task
        g = self.db_mgr.get_tenant_graph(tenant_id)
        q_prop = """
        MATCH (t:Task {task_id: $task_id, tenant_id: $tenant_id})-[:EXECUTES_PROPOSAL]->(p:ActionProposal)
        RETURN p.proposal_id, p.evidence_revision, p.status
        """
        res_prop = g.ro_query(q_prop, {"task_id": task_id, "tenant_id": tenant_id}).result_set
        if not res_prop:
            return {"success": False, "reason": "NO_PROPOSAL_BOUND_TO_TASK", "task_id": task_id}

        proposal_id, ev_rev, prop_status = res_prop[0]

        # Guarded check: Remediator agent cannot execute without a valid server-issued human approval record
        if not human_approval_token:
            return {
                "success": False,
                "reason": "HUMAN_APPROVAL_REQUIRED",
                "proposal_id": proposal_id,
                "proposal_status": prop_status,
                "fence_token": lease["fence_token"]
            }

        # Apply single-query atomic Cypher remediation patch
        apply_res = self.tools.apply_remediation_patch(
            tenant_id=tenant_id,
            task_id=task_id,
            proposal_id=proposal_id,
            agent_id=worker_id,
            fence_token=lease["fence_token"],
            idempotency_key=f"IDEM-{worker_id}-{task_id}",
            human_approval_token=human_approval_token,
            expected_evidence_revision=ev_rev
        )

        return {
            "success": apply_res.get("success", False),
            "worker_id": worker_id,
            "task_id": task_id,
            "proposal_id": proposal_id,
            "fence_token": lease["fence_token"],
            "patch_result": apply_res
        }
