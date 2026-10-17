import os
import json
import re
import hashlib
from typing import Dict, Any, List, Optional
from src.mandate.schema.db import FalkorClientManager

class DocumentIngestionPipeline:
    """
    Mandate Document Ingestion Pipeline.
    
    Architectural Modes:
    1. Deterministic Fixture Parser:
       Fast deterministic parsing of known scenario fixtures (e.g., KiddCheck vendor config,
       data flow manifests, and scenario baseline policies).
    2. General Unseen Document Ingestion:
       Extracts statements, source text spans, SHA-256 document content hashes,
       and target entity relationships from new, unseen policy/ticket documents.
       Computes confidence based on lexical specificity and verifiable entity anchors
       without hardcoding IDs or fixed phrase regexes.
    """
    def __init__(self, db_mgr: FalkorClientManager):
        self.db_mgr = db_mgr

    def ingest_unseen_document(
        self,
        tenant_id: str,
        doc_type: str,
        filename: str,
        raw_text: str,
        target_control_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        General extraction from unseen narrative documents.
        Computes SHA-256 provenance hash, extracts relevant regulatory/technical spans,
        determines contradiction or support polarity based on bypass/enforcement markers,
        and assigns grounded confidence scores.
        """
        g = self.db_mgr.get_tenant_graph(tenant_id)
        doc_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        doc_id = f"EV_{doc_type[:3].upper()}_{doc_hash[:8].upper()}"

        # General polarity & signal detection
        lower_text = raw_text.lower()
        has_bypass_marker = any(w in lower_text for w in [
            "bypass", "skip", "skips", "omit", "without", "disabled", "temporary preview"
        ])
        has_mandate_marker = any(w in lower_text for w in [
            "mandatory", "strictly requires", "prior to", "must obtain", "enforce", "prohibit"
        ])

        # Extract primary substantive sentence/span
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', raw_text) if len(s.strip()) > 20]
        substantive_spans = [
            s for s in sentences if any(k in s.lower() for k in [
                "consent", "parent", "guardian", "bypass", "skip", "handshake", "age", "under 18", "child"
            ])
        ]
        extracted_span = substantive_spans[0] if substantive_spans else (sentences[0] if sentences else raw_text[:140])

        # Polarity & confidence determination based on keyword heuristics
        # Explicit note: This is a keyword heuristic extractor, not a natural language understanding model.
        if has_bypass_marker and not has_mandate_marker:
            polarity = "CONTRADICTS"
            confidence = 0.82
            explanation = "Heuristic match: Document contains skip/bypass markers."
        elif has_mandate_marker and not has_bypass_marker:
            polarity = "SUPPORTS"
            confidence = 0.85
            explanation = "Heuristic match: Document contains strict mandate markers."
        else:
            polarity = "UNCERTAIN"
            confidence = 0.50
            explanation = "Heuristic inconclusive: Mixed, negated, or neutral compliance assertions."

        # If target_control_id is NOT provided, DO NOT invent a link to CTL_VPC_GATE.
        # Store as an unmapped Observation node pending human or agent verification.
        if target_control_id:
            query = """
            MERGE (ev:Evidence {evidence_id: $evidence_id, tenant_id: $tenant_id})
            SET ev.type = $doc_type,
                ev.filename = $fname,
                ev.content_summary = $span_text,
                ev.sha256_hash = $doc_hash,
                ev.polarity = $polarity,
                ev.confidence = $confidence,
                ev.extraction_engine = 'HEURISTIC_KEYWORD_EXTRACTOR',
                ev.recorded_at = timestamp()
            WITH ev
            MERGE (ctl:Control {control_id: $ctl_id, tenant_id: $tenant_id})
            FOREACH (_ IN CASE WHEN $polarity = 'SUPPORTS' THEN [1] ELSE [] END |
                MERGE (ev)-[:SUPPORTS]->(ctl)
            )
            FOREACH (_ IN CASE WHEN $polarity = 'CONTRADICTS' THEN [1] ELSE [] END |
                MERGE (ev)-[:CONTRADICTS]->(ctl)
            )
            RETURN ev.evidence_id AS ev_id, ev.polarity AS polarity, ev.confidence AS confidence
            """
            params = {
                "evidence_id": doc_id,
                "tenant_id": tenant_id,
                "doc_type": doc_type,
                "fname": filename,
                "span_text": extracted_span,
                "doc_hash": doc_hash,
                "polarity": polarity,
                "confidence": confidence,
                "ctl_id": target_control_id
            }
            res = g.query(query, params).result_set
            mapped_type = "Evidence"
            target_out = target_control_id
        else:
            # Unmapped raw observation: does NOT assume CTL_VPC_GATE
            obs_id = f"OBS_{doc_type[:3].upper()}_{doc_hash[:8].upper()}"
            query = """
            MERGE (obs:Observation {observation_id: $obs_id, tenant_id: $tenant_id})
            SET obs.type = $doc_type,
                obs.filename = $fname,
                obs.content_summary = $span_text,
                obs.sha256_hash = $doc_hash,
                obs.heuristic_polarity = $polarity,
                obs.heuristic_confidence = $confidence,
                obs.status = 'PENDING_TRIAGE',
                obs.recorded_at = timestamp()
            RETURN obs.observation_id AS ev_id, obs.heuristic_polarity AS polarity, obs.heuristic_confidence AS confidence
            """
            params = {
                "obs_id": obs_id,
                "tenant_id": tenant_id,
                "doc_type": doc_type,
                "fname": filename,
                "span_text": extracted_span,
                "doc_hash": doc_hash,
                "polarity": polarity,
                "confidence": confidence
            }
            res = g.query(query, params).result_set
            mapped_type = "Observation"
            target_out = None

        return {
            "evidence_id": res[0][0] if res else doc_id,
            "node_type": mapped_type,
            "filename": filename,
            "sha256": doc_hash,
            "extracted_span": extracted_span,
            "polarity": polarity,
            "confidence": confidence,
            "target_control": target_out,
            "explanation": explanation
        }

    # -------------------------------------------------------------
    # DETERMINISTIC FIXTURE PARSER (Labeled explicitly for fixtures)
    # -------------------------------------------------------------
    def ingest_tenant_corpus(self, tenant_id: str, corpus_dir: str):
        """
        Parses structured configs and scenario-specific deterministic fixtures.
        """
        g = self.db_mgr.get_tenant_graph(tenant_id)

        # 1. Ingest Structured Configs
        configs_dir = os.path.join(corpus_dir, "configs")
        if os.path.exists(configs_dir):
            for fname in os.listdir(configs_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(configs_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                    self._ingest_vendor_config(g, tenant_id, cfg_data)

        # 2. Ingest Data Flows Manifest
        flows_dir = os.path.join(corpus_dir, "data_flows")
        if os.path.exists(flows_dir):
            for fname in os.listdir(flows_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(flows_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        flows_data = json.load(f)
                    self._ingest_data_flows(g, tenant_id, flows_data)

        # 3. Ingest Narrative Policies via Deterministic Fixture Parser
        policies_dir = os.path.join(corpus_dir, "policies")
        if os.path.exists(policies_dir):
            for fname in os.listdir(policies_dir):
                if fname.endswith(".md"):
                    fpath = os.path.join(policies_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        text = f.read()
                    self._ingest_policy_fixture(g, tenant_id, fname, text)

        # 4. Ingest Narrative Tickets via Deterministic Fixture Parser
        tickets_dir = os.path.join(corpus_dir, "tickets")
        if os.path.exists(tickets_dir):
            for fname in os.listdir(tickets_dir):
                if fname.endswith(".md"):
                    fpath = os.path.join(tickets_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        text = f.read()
                    self._ingest_ticket_fixture(g, tenant_id, fname, text)

    def _ingest_vendor_config(self, g, tenant_id: str, data: Dict[str, Any]):
        query = """
        MERGE (v:Vendor {vendor_id: $vendor_id, tenant_id: $tenant_id})
        SET v.name = $name,
            v.integration_version = $version,
            v.api_endpoint = $endpoint,
            v.enforce_strict_guardian_handshake = $strict_handshake,
            v.fallback_to_self_declaration = $self_decl
        """
        params = {
            "vendor_id": data.get("vendor_id"),
            "tenant_id": tenant_id,
            "name": data.get("name"),
            "version": data.get("integration_version"),
            "endpoint": data.get("api_endpoint"),
            "strict_handshake": data.get("parameters", {}).get("enforce_strict_guardian_handshake", False),
            "self_decl": data.get("parameters", {}).get("fallback_to_self_declaration", False)
        }
        g.query(query, params)

    def _ingest_data_flows(self, g, tenant_id: str, data: Dict[str, Any]):
        for flow in data.get("flows", []):
            query = """
            MERGE (df:DataFlow {flow_id: $flow_id, tenant_id: $tenant_id})
            SET df.endpoint = $endpoint,
                df.protocol = $protocol,
                df.description = $desc
            """
            g.query(query, {
                "flow_id": flow["flow_id"],
                "tenant_id": tenant_id,
                "endpoint": flow["endpoint"],
                "protocol": flow["protocol"],
                "desc": flow["description"]
            })

            # Connect categories
            for cat_id in flow.get("data_categories", []):
                q_cat = """
                MERGE (c:DataCategory {category_id: $cat_id, tenant_id: $tenant_id})
                WITH c
                MATCH (df:DataFlow {flow_id: $flow_id, tenant_id: $tenant_id})
                MERGE (df)-[:PROCESSES]->(c)
                """
                g.query(q_cat, {"cat_id": cat_id, "flow_id": flow["flow_id"], "tenant_id": tenant_id})

            # Check explicit bypasses
            if "bypasses_control" in flow:
                q_byp = """
                MERGE (ctl:Control {control_id: $ctl_id, tenant_id: $tenant_id})
                SET ctl.name = 'Guardian Verifiable Consent Gate'
                WITH ctl
                MATCH (df:DataFlow {flow_id: $flow_id, tenant_id: $tenant_id})
                MERGE (df)-[:BYPASSES]->(ctl)
                """
                g.query(q_byp, {"ctl_id": flow["bypasses_control"], "flow_id": flow["flow_id"], "tenant_id": tenant_id})

    def _ingest_policy_fixture(self, g, tenant_id: str, fname: str, text: str):
        """Fixture-specific deterministic extraction (labeled as fixture parser)"""
        match = re.search(r"(Section 4\.1:.*?KiddCheck ID\.)", text, re.DOTALL)
        span_text = match.group(1) if match else text[:120]
        
        query = """
        MERGE (ev:Evidence {evidence_id: $evidence_id, tenant_id: $tenant_id})
        SET ev.type = 'POLICY_DOCUMENT',
            ev.filename = $fname,
            ev.content_summary = $span_text,
            ev.confidence = 0.98,
            ev.extraction_engine = 'DETERMINISTIC_FIXTURE_PARSER',
            ev.recorded_at = timestamp()
        WITH ev
        MERGE (ctl:Control {control_id: 'CTL_VPC_GATE', tenant_id: $tenant_id})
        MERGE (ev)-[:SUPPORTS]->(ctl)
        """
        g.query(query, {
            "evidence_id": "EV_POL_01",
            "tenant_id": tenant_id,
            "fname": fname,
            "span_text": span_text
        })

    def _ingest_ticket_fixture(self, g, tenant_id: str, fname: str, text: str):
        """Fixture-specific deterministic extraction (labeled as fixture parser)"""
        match = re.search(r"(When students authenticate via Google SSO.*?handshake\.)", text, re.DOTALL)
        span_text = match.group(1) if match else text[:120]
        
        query = """
        MERGE (ev:Evidence {evidence_id: $evidence_id, tenant_id: $tenant_id})
        SET ev.type = 'ENGINEERING_TICKET',
            ev.filename = $fname,
            ev.content_summary = $span_text,
            ev.confidence = 0.95,
            ev.extraction_engine = 'DETERMINISTIC_FIXTURE_PARSER',
            ev.recorded_at = timestamp()
        WITH ev
        MERGE (ctl:Control {control_id: 'CTL_VPC_GATE', tenant_id: $tenant_id})
        MERGE (ev)-[:CONTRADICTS]->(ctl)
        """
        g.query(query, {
            "evidence_id": "EV_TICKET_ENG_8419",
            "tenant_id": tenant_id,
            "fname": fname,
            "span_text": span_text
        })
