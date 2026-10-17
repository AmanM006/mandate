import hashlib
import os
from pypdf import PdfReader

PDF_METADATA = {
    "dpdp_act_2023.pdf": {
        "title": "Digital Personal Data Protection Act, 2023 (Act No. 22 of 2023)",
        "expected_sha256": "4deb23981d3010c8225a2ff6149e7243dc2268455b299e283afebdd7b72a7d15",
        "expected_bytes": 182082,
        "key_checks": [
            {"label": "Section 9(1) Parental Consent", "pdf_page": 8, "printed_page": 8, "needle": "obtain verifiable consent of the parent"},
            {"label": "Section 9(2) Harm Prohibition", "pdf_page": 8, "printed_page": 8, "needle": "likely to cause any detrimental effect"},
            {"label": "Section 9(3) Anti-Tracking", "pdf_page": 8, "printed_page": 8, "needle": "tracking or behavioural monitoring of children"},
            {"label": "Section 17(1)(b) Judicial Exemption", "pdf_page": 11, "printed_page": 11, "needle": "performance of any judicial or quasi-judicial"},
            {"label": "Section 17(2)(b) Research Exemption", "pdf_page": 12, "printed_page": 12, "needle": "research, archiving or statistical purposes"},
            {"label": "Section 17(3) Startups Exemption", "pdf_page": 12, "printed_page": 12, "needle": "including startups"}
        ]
    },
    "dpdp_rules_2025_gsr846e.pdf": {
        "title": "Digital Personal Data Protection Rules, 2025 (G.S.R. 846(E))",
        "expected_sha256": "eabc7d05e013144615d78ddc0e8b9c9aac1920e814f4fad38ce6560951f5aa08",
        "expected_bytes": 2492944,
        "key_checks": [
            {"label": "Rule 1 Commencement (English)", "pdf_page": 24, "printed_page": 24, "needle": "Rules 1, 2 and 17 to 21 shall come into force"},
            {"label": "Rule 4 (1-Year Commencement)", "pdf_page": 24, "printed_page": 24, "needle": "Rule 4 shall come into force one year after the date of publication"},
            {"label": "Rule 3, 5-16 (18-Month Commencement)", "pdf_page": 24, "printed_page": 24, "needle": "Rules 3, 5 to 16, 22 and 23 shall come into force eighteen months after the date of publication"},
            {"label": "Rule 3 Notice Specifics (English)", "pdf_page": 24, "printed_page": 24, "needle": "Notice given by Data Fiduciary to Data Principal"},
            {"label": "Rule 4 Consent Managers (English)", "pdf_page": 25, "printed_page": 25, "needle": "Registration and obligations of Consent Manager"},
            {"label": "Gazette Upload Marker", "pdf_page": 1, "printed_page": 1, "needle": "CG-DL-E-14112025-267650"}
        ]
    },
    "dpdp_corrigendum_gsr892e.pdf": {
        "title": "Corrigendum to DPDP Rules, 2025 (G.S.R. 892(E))",
        "expected_sha256": "8f8d9526b511801889f8ae022b6d7c5db449283e90fe32792e5896314b32f994",
        "expected_bytes": 408279,
        "key_checks": [
            {"label": "Corrigenda Notification Date", "pdf_page": 1, "printed_page": 1, "needle": "New Delhi, the 10th December, 2025"},
            {"label": "Page 34 typo fix", "pdf_page": 1, "printed_page": 1, "needle": "(18 of 2013)"},
            {"label": "Gazette Upload ID", "pdf_page": 1, "printed_page": 1, "needle": "CG-DL-E-12122025-268455"}
        ]
    }
}

def verify_all_official_pdfs(pdf_dir: str = "official_pdfs"):
    print("=" * 70)
    print("OFFICIAL SOURCE INTEGRITY & SELECTED-STRING VERIFICATION RUNNER")
    print("=" * 70)
    all_ok = True

    for fname, meta in PDF_METADATA.items():
        fpath = os.path.join(pdf_dir, fname)
        if not os.path.exists(fpath):
            print(f"[FAIL] Missing {fname} at {fpath}")
            all_ok = False
            continue

        with open(fpath, "rb") as f:
            data = f.read()

        # 1. Byte length & SHA-256
        actual_bytes = len(data)
        actual_sha256 = hashlib.sha256(data).hexdigest()
        
        bytes_ok = (actual_bytes == meta["expected_bytes"])
        hash_ok = (actual_sha256 == meta["expected_sha256"])

        print(f"\nDocument: {meta['title']}")
        print(f"  Path: {fpath}")
        print(f"  Size: {actual_bytes} bytes [{'OK' if bytes_ok else 'FAIL'}]")
        print(f"  SHA-256: {actual_sha256} [{'OK' if hash_ok else 'FAIL'}]")

        if not (bytes_ok and hash_ok):
            all_ok = False

        # 2. Page & Text Span Audits
        reader = PdfReader(fpath)
        print(f"  Total Pages: {len(reader.pages)}")
        for check in meta["key_checks"]:
            p_idx = check["pdf_page"] - 1
            if p_idx < len(reader.pages):
                txt = reader.pages[p_idx].extract_text() or ""
                needle = check["needle"]
                found = (needle in txt)
                status = "OK" if found else "NOT_FOUND"
                print(f"    * [{status}] {check['label']} (PDF P.{check['pdf_page']}, Printed P.{check['printed_page']})")
                if not found:
                    all_ok = False
            else:
                print(f"    * [FAIL] Page index {check['pdf_page']} out of bounds.")
                all_ok = False

    print("\n" + "=" * 70)
    if all_ok:
        print("[SUCCESS] ALL OFFICIAL DOCUMENTS, BYTES, HASHES, AND SELECTED STRINGS VERIFIED.")
    else:
        print("[WARNING] SOME VERIFICATION CHECKS FAILED.")
    print("=" * 70)
    return all_ok

if __name__ == "__main__":
    verify_all_official_pdfs()
