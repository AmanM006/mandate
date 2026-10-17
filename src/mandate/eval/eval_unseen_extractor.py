"""
Benchmark Evaluation Suite for Mandate's Heuristic Keyword Extractor.

Evaluates DocumentIngestionPipeline.ingest_unseen_document against a diverse,
ground-truth corpus of:
1. Positive enforcement documents (SUPPORTS)
2. Negative bypass/skip documents (CONTRADICTS)
3. Negated statements ("not skipping", "never bypasses")
4. Quoted/Disclaimed statements ("claimed to bypass", "reports an alleged skip")
5. Neutral/Unrelated documents (UNCERTAIN)
6. Contradictory/Mixed documents (UNCERTAIN)

Computes exact Precision, Recall, and F1 per class, measuring the true bounds of
heuristic keyword extraction without making unwarranted claims of NLP understanding.
"""

from typing import Dict, Any, List
from src.mandate.schema.db import FalkorClientManager
from src.mandate.schema.ingestion_pipeline import DocumentIngestionPipeline

BENCHMARK_CORPUS = [
    # Class 1: Unseen Clear Positive Enforcement (Expected: SUPPORTS)
    {
        "id": "POS_01",
        "doc_type": "POLICY",
        "filename": "annual_guardian_verification_std.md",
        "text": "Every user registration under 18 must obtain prior verifiable consent from a legal parent or guardian before account creation. All student onboarding strictly requires guardian SMS verification.",
        "expected_polarity": "SUPPORTS"
    },
    {
        "id": "POS_02",
        "doc_type": "ARCHITECTURE_NOTE",
        "filename": "arch_id_gateway.md",
        "text": "The authentication service mandates verifiable guardian proof. Platform access is prohibited until the parent handshake completes successfully.",
        "expected_polarity": "SUPPORTS"
    },
    {
        "id": "POS_03",
        "doc_type": "SOP",
        "filename": "sop_youth_enrollment.md",
        "text": "Prior to activating minor learning portals, support agents must enforce verified guardian documentation without exception.",
        "expected_polarity": "SUPPORTS"
    },

    # Class 2: Unseen Clear Negative Bypass (Expected: CONTRADICTS)
    {
        "id": "NEG_01",
        "doc_type": "TICKET",
        "filename": "jira_eng_9102.md",
        "text": "Temporary preview route allows students to bypass parent identity check and explore lessons without verification.",
        "expected_polarity": "CONTRADICTS"
    },
    {
        "id": "NEG_02",
        "doc_type": "RELEASE_NOTE",
        "filename": "rel_v2_4_hotfix.md",
        "text": "Hotfix v2.4 skips guardian handshake on Android mobile builds to prevent drop-offs during marketing push.",
        "expected_polarity": "CONTRADICTS"
    },
    {
        "id": "NEG_03",
        "doc_type": "CONFIG_MEMO",
        "filename": "memo_guest_sso.md",
        "text": "Guest signup flow disabled age gating to let prospective students test course modules freely.",
        "expected_polarity": "CONTRADICTS"
    },

    # Class 3: Negated Statements (Heuristic limitation: may falsely trigger bypass markers)
    {
        "id": "NEGATED_01",
        "doc_type": "AUDIT_FINDING",
        "filename": "audit_remediation_closure.md",
        "text": "Auditors verified that the production auth gateway is NOT skipping guardian verification under any condition.",
        "expected_polarity": "SUPPORTS"  # True semantic meaning is compliant/supportive
    },
    {
        "id": "NEGATED_02",
        "doc_type": "SECURITY_MEMO",
        "filename": "sec_notice_44.md",
        "text": "Engineers are strictly instructed: never bypass parental verification protocols on youth endpoints.",
        "expected_polarity": "SUPPORTS"  # True semantic meaning is compliant/supportive
    },

    # Class 4: Quoted / Attribution Disclaimers (Heuristic limitation)
    {
        "id": "QUOTED_01",
        "doc_type": "INCIDENT_REPORT",
        "filename": "inc_2026_04.md",
        "text": "Customer reported an alleged bypass, but log inspection confirmed that all registrations were fully verified by KiddCheck ID.",
        "expected_polarity": "SUPPORTS"
    },

    # Class 5: Unrelated / Neutral Documents (Expected: UNCERTAIN)
    {
        "id": "NEUTRAL_01",
        "doc_type": "INFRA_SPEC",
        "filename": "redis_cluster_sizing.md",
        "text": "Production Redis clusters utilize 3 nodes with multi-AZ failover and 64GB RAM allocated for cache warming.",
        "expected_polarity": "UNCERTAIN"
    },
    {
        "id": "NEUTRAL_02",
        "doc_type": "BILLING_NOTE",
        "filename": "stripe_invoice_format.md",
        "text": "Quarterly subscription invoices are generated on the 1st of each calendar month and archived in S3.",
        "expected_polarity": "UNCERTAIN"
    },

    # Class 6: Mixed / Conflicting Text (Expected: UNCERTAIN)
    {
        "id": "MIXED_01",
        "doc_type": "DISCUSSION_THREAD",
        "filename": "slack_sync_auth.md",
        "text": "While parent consent is mandatory by policy, the dev environment currently skips external API calls.",
        "expected_polarity": "UNCERTAIN"
    }
]

def run_heuristic_extractor_benchmark() -> Dict[str, Any]:
    mgr = FalkorClientManager()
    pipeline = DocumentIngestionPipeline(mgr)
    
    total = len(BENCHMARK_CORPUS)
    results = []
    
    # Confusion matrix counters
    classes = ["SUPPORTS", "CONTRADICTS", "UNCERTAIN"]
    tp = {c: 0 for c in classes}
    fp = {c: 0 for c in classes}
    fn = {c: 0 for c in classes}

    print("\n" + "=" * 80)
    print("HEURISTIC KEYWORD EXTRACTOR BENCHMARK EVALUATION")
    print("=" * 80)

    for item in BENCHMARK_CORPUS:
        ingest_res = pipeline.ingest_unseen_document(
            tenant_id="aetherlearn",
            doc_type=item["doc_type"],
            filename=item["filename"],
            raw_text=item["text"],
            target_control_id=None # Testing unmapped observation behavior
        )
        predicted = ingest_res["polarity"]
        expected = item["expected_polarity"]
        matched = (predicted == expected)
        
        for c in classes:
            if expected == c and predicted == c:
                tp[c] += 1
            elif expected != c and predicted == c:
                fp[c] += 1
            elif expected == c and predicted != c:
                fn[c] += 1

        results.append({
            "id": item["id"],
            "filename": item["filename"],
            "expected": expected,
            "predicted": predicted,
            "matched": matched,
            "node_type": ingest_res["node_type"],
            "explanation": ingest_res["explanation"]
        })
        status_flag = "PASS" if matched else "FAIL (Heuristic Boundary)"
        print(f"[{status_flag:24}] {item['id']:12} | Exp: {expected:11} | Got: {predicted:11} | Node: {ingest_res['node_type']}")

    # Metric calculations
    metrics = {}
    for c in classes:
        precision = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
        recall = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        metrics[c] = {
            "true_positives": tp[c],
            "false_positives": fp[c],
            "false_negatives": fn[c],
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4)
        }

    overall_accuracy = sum(1 for r in results if r["matched"]) / total

    print("-" * 80)
    print(f"Overall Accuracy: {overall_accuracy:.2%} ({sum(1 for r in results if r['matched'])}/{total})")
    print("\nPer-Class Breakdown:")
    for c, m in metrics.items():
        print(f"  {c:12} -> Precision: {m['precision']:.2f} | Recall: {m['recall']:.2f} | F1: {m['f1']:.2f} (TP={m['true_positives']}, FP={m['false_positives']}, FN={m['false_negatives']})")
    print("=" * 80 + "\n")

    return {
        "total_cases": total,
        "overall_accuracy": overall_accuracy,
        "per_class_metrics": metrics,
        "detailed_results": results
    }

if __name__ == "__main__":
    run_heuristic_extractor_benchmark()
