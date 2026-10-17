import urllib.request
import hashlib
import os

PDFS = {
    "dpdp_act_2023.pdf": {
        "url": "https://www.meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf",
        "description": "Digital Personal Data Protection Act, 2023 (Act No. 22 of 2023)"
    },
    "dpdp_rules_2025_gsr846e.pdf": {
        "url": "https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf",
        "description": "Digital Personal Data Protection Rules, 2025 (G.S.R. 846(E))"
    },
    "dpdp_corrigendum_gsr892e.pdf": {
        "url": "https://www.meity.gov.in/static/uploads/2025/12/3c7ebbae0e5456f493f486e6845df86b.pdf",
        "description": "Corrigendum to DPDP Rules, 2025 (G.S.R. 892(E))"
    }
}

def download_and_verify(out_dir: str = "official_pdfs"):
    os.makedirs(out_dir, exist_ok=True)
    results = {}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for fname, meta in PDFS.items():
        fpath = os.path.join(out_dir, fname)
        print(f"Fetching {fname} from {meta['url']}...")
        req = urllib.request.Request(meta["url"], headers=headers)
        with urllib.request.urlopen(req) as resp, open(fpath, "wb") as out:
            data = resp.read()
            out.write(data)
        
        file_bytes = len(data)
        sha256 = hashlib.sha256(data).hexdigest()
        print(f"  -> Saved {fname} ({file_bytes} bytes)")
        print(f"  -> Computed SHA-256: {sha256}")
        results[fname] = {
            "bytes": file_bytes,
            "sha256": sha256,
            "url": meta["url"],
            "desc": meta["description"]
        }
    return results

if __name__ == "__main__":
    download_and_verify()
