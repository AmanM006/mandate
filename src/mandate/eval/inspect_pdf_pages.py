import pypdf
import os

files = {
    "Act": "official_pdfs/dpdp_act_2023.pdf",
    "Rules": "official_pdfs/dpdp_rules_2025_gsr846e.pdf",
    "Corrigendum": "official_pdfs/dpdp_corrigendum_gsr892e.pdf"
}

try:
    from pypdf import PdfReader
    for name, path in files.items():
        reader = PdfReader(path)
        print(f"=== {name} ({len(reader.pages)} pages) ===")
        # Search for Section 9 in Act
        if name == "Act":
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if "Processing of personal data of children" in text or "Section 9" in text:
                    print(f"  [Found Sec 9 on PDF Page {idx+1}]")
                    lines = [l for l in text.split("\n") if "9." in l or "child" in l.lower()]
                    print("  Sample lines:", lines[:3])
        elif name == "Rules":
            for idx in range(min(5, len(reader.pages))):
                text = reader.pages[idx].extract_text() or ""
                if "November" in text or "G.S.R." in text or "commence" in text.lower():
                    print(f"  [Header / Dates on PDF Page {idx+1}]:")
                    for l in text.split("\n")[:10]:
                        if any(k in l for k in ["November", "G.S.R", "Rules", "Gazette", "commence"]):
                            print("   ", l)
except ImportError:
    print("pypdf not installed, checking via basic text scan")
