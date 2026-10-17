import sys
from pypdf import PdfReader

reader_rules = PdfReader("official_pdfs/dpdp_rules_2025_gsr846e.pdf")
with open("official_pdfs/rules_p1_to_p5.txt", "w", encoding="utf-8") as out:
    for i in range(min(5, len(reader_rules.pages))):
        out.write(f"=== RULES PDF PAGE {i+1} ===\n")
        out.write(reader_rules.pages[i].extract_text() or "")
        out.write("\n\n")

reader_corrig = PdfReader("official_pdfs/dpdp_corrigendum_gsr892e.pdf")
with open("official_pdfs/corrigendum_text.txt", "w", encoding="utf-8") as out:
    out.write("=== CORRIGENDUM PDF ===\n")
    out.write(reader_corrig.pages[0].extract_text() or "")

print("Saved rules and corrigendum text to official_pdfs/")
