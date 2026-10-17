# Mandate: FalkorDB-Native Compliance Investigation, Invalidation & Guarded Remediation Engine

**Mandate** is a production-grade multi-agent compliance intelligence system natively powered by **FalkorDB Graph Database**. Built for **WeMakeDevs × FalkorDB Graph Hacks** targeting:
- **Track 3: Company Brain (M6 Mac Mini)**
- **Track 2: Agent Memory & Coordination (PS5)**
- **Track 1: Genuine Graph-Driven Remediation Action**

---

## 1. Key Capabilities & Innovations

1. **Statutory Provenance & Official SHA-256 Verifier**
   - Ingests the DPDP Act 2023, DPDP Rules 2025, and Corrigendum G.S.R. 892(E).
   - Validates official MeitY SHA-256 hashes and captures the dual commencement date discrepancy (Gazette date: 13 Nov 2025 vs. Barcode upload: 14 Nov 2025).

2. **Graph-Native Multi-Agent Memory & Lease Fencing (Track 2)**
   - **Cross-Process Agent Handoff**: Decoupled processes coordinate strictly through FalkorDB nodes and relationships (`Task`, `AssessmentConclusion`, `[:EXECUTES_PROPOSAL]`).
   - **Distributed Fencing Tokens (`lease_version`)**: Prevents zombie worker split-brain writes and race conditions without in-memory locks.
   - **Causal Premise Invalidation**: Invalidation of premises cascades down dependency chains while preserving independent valid conclusions and maintaining an immutable audit log.

3. **Strict Single-Query Atomic Remediation in Cypher (Track 1)**
   - Eliminates Time-of-Check to Time-of-Use (TOCTOU) race windows.
   - Matches all preconditions (`Task.lease_version`, `ActionProposal.status = 'APPROVED'`, `Evidence.evidence_revision`, server-signed `ApprovalRecord`) **before** mutating vendor configurations and deleting `[:BYPASSES]` edges.

4. **Honest Heuristic Keyword Extraction & Benchmark Tracking**
   - Distinct classification between deterministic fixture parsers, heuristic keyword extractors, and future LLM extraction pipelines.
   - Evaluated on a diverse benchmark suite (positive, negative, negated, quoted, and neutral documents), reporting exact Precision, Recall, and F1.

5. **Multi-Tenant Graph Namespace Isolation**
   - Strict isolation using FalkorDB `select_graph(tenant_id)` namespaces (`mandate_aetherlearn`, `mandate_nexusops`, `mandate_dpdp_public`). Zero cross-tenant leakage.

---

## 2. Benchmark & Evaluation Results

- **Official Source Integrity**: **100% Verified** ([`docs/source_verification.md`](docs/source_verification.md))
- **30-Case Core Regulatory Development Benchmark**: **14 / 30 Passed (46.7%)**
  - Accurately captures 14 verifiable baseline statutory, multi-tenant isolation, graph contradiction, and behavioral remediation assertions in isolated disposable tenant namespaces without artificial inflating.
- **8-Case Reserved Evaluation Suite**: **8 / 8 Passed (100.0%)**
  - Standalone verification covering Section 16 cross-border transfer gates, Consent Manager boundaries under Rule 4, Section 17(2)(b) pedagogical research anonymizer verification, Section 17(3) startup review caps, cross-tenant isolation, expired approval rejection, zombie agent fence collisions, and multi-session episodic memory recovery.
- **8-Case Behavioral Compliance Runner**: **5/8 Passing Pre-Patch (Failing B01, B02, B04) $\rightarrow$ 8/8 Passing Post-Patch (100.0%)**
- **Pytest Unit & Security Invariants**: **12 / 12 Passed (100%)**

---

## 3. Quick Start & Verification

### Prerequisites
- Docker (with `falkordb/falkordb-server:latest` running on port `6379`)
- Python 3.11+

### Running FalkorDB
```bash
docker run -d --restart=unless-stopped --name mandate-falkordb-prod -p 6379:6379 falkordb/falkordb-server:latest
```

### Installation
```bash
pip install -r requirements.txt
```

### Running All Verifications
```bash
# 1. Run unit, security, and atomicity tests
python -m pytest tests/ -v

# 2. Run official PDF hash and string integrity verifier
python -m src.mandate.eval.verify_source_integrity

# 3. Run the 30-case ground-truth development benchmark
python -m src.mandate.eval.eval_runner

# 4. Run the 8-case reserved evaluation suite
python -m src.mandate.eval.hidden_benchmark

# 5. Run the Track 2 live cross-process multi-agent demonstration
python -m src.mandate.agents.session_a_process
python -m src.mandate.agents.session_b_process

# 6. Run the Heuristic Keyword Extractor benchmark
python -m src.mandate.eval.eval_unseen_extractor
```

### Launching the Web Console
```bash
python -m uvicorn src.mandate.api:app --host 127.0.0.1 --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser. Demo compliance credentials:
- **Username**: `officer_alice`
- **Password**: `alice_secret_compliance_2026`
