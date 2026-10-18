from src.mandate.schema.db import FalkorClientManager
from src.mandate.eval.eval_runner import EvaluationRunner

mgr = FalkorClientManager()
runner = EvaluationRunner(mgr)
bench = runner.run_benchmark()

print(f"\nTotal Cases: {bench['total_cases']}, Passed: {bench['passed']}, Accuracy: {bench['accuracy_percentage']:.1f}%\n")
print("| Case ID | Provision ID | Expected Result (Legal / Ev / Claim) | Independently Observed Result | Graph / Behavioral Evidence Detail | Verdict |")
print("|:---|:---|:---|:---|:---|:---:|")
for r in bench['results']:
    cid = r['case_id']
    pid = r['provision_id']
    exp = f"{r['expected']['legal_status']} / {r['expected']['evidence_status']} / {r['expected']['claim_status']}"
    obs = f"{r['observed']['legal_status']} / {r['observed']['evidence_status']} / {r['observed']['claim_status']}"
    det = r['observed']['detail'].replace("|", "/")
    status = "PASS" if r['passed'] else "FAIL"
    print(f"| {cid} | `{pid}` | {exp} | {obs} | {det} | **{status}** |")
