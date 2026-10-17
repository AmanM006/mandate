from pypdf import PdfReader

reader_act = PdfReader("official_pdfs/dpdp_act_2023.pdf")
print("--- ACT SEARCH ---")
for i, page in enumerate(reader_act.pages):
    txt = page.extract_text() or ""
    if "Section 9" in txt or "Processing of personal data of children" in txt or "parent" in txt:
        print(f"Act PDF Page {i+1} has matches")
        for line in txt.split("\n"):
            if "child" in line.lower() or "parent" in line.lower() or "9." in line:
                print(f"  P{i+1}: {line}")

reader_rules = PdfReader("official_pdfs/dpdp_rules_2025_gsr846e.pdf")
print("\n--- RULES SEARCH ---")
for i in range(min(5, len(reader_rules.pages))):
    txt = reader_rules.pages[i].extract_text() or ""
    print(f"Rules PDF Page {i+1} first 500 chars:")
    print(txt[:500])
    print("-" * 40)
