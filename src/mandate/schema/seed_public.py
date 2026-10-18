import os
from src.mandate.schema.db import FalkorClientManager

def seed_regulatory_corpus(db_mgr: FalkorClientManager):
    """
    Seeds the authoritative public DPDP corpus into 'mandate_dpdp_public'.
    Includes:
    - Act No. 22 of 2023 (Sec 9(1), 9(2), 9(3), 17(1), 17(2)(b), 17(3), 4, 6(1), 6(4), 10, 16)
    - Rules 2025 (G.S.R. 846(E): Rule 1, 3, 4, 9, 10, 12, 14, 17-21)
    - Corrigendum G.S.R. 892(E)
    - Commencement specifications with exact days and transition basis
    """
    g = db_mgr.get_public_graph()
    
    # 1. Source Documents & Versions
    query_sources = """
    MERGE (doc_act:SourceDocument {identifier: 'DPDP_ACT_2023'})
    SET doc_act.name = 'Digital Personal Data Protection Act, 2023',
        doc_act.authority = 'Ministry of Law and Justice / Parliament of India',
        doc_act.publication_date = '2023-08-11',
        doc_act.gazette_ref = 'Act No. 22 of 2023',
        doc_act.url = 'https://www.meity.gov.in'

    MERGE (doc_rules:SourceDocument {identifier: 'DPDP_RULES_2025'})
    SET doc_rules.name = 'Digital Personal Data Protection Rules, 2025',
        doc_rules.authority = 'Ministry of Electronics and Information Technology (MeitY)',
        doc_rules.notification_date = '2025-11-13',
        doc_rules.publication_date = '2025-11-14',
        doc_rules.gazette_ref = 'G.S.R. 846(E)',
        doc_rules.url = 'https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf'

    MERGE (ver_rules_v1:DocumentVersion {version_id: 'GSR_846E_V1'})
    SET ver_rules_v1.version = '1.0',
        ver_rules_v1.effective_date = '2025-11-14',
        ver_rules_v1.is_corrigendum = false
    MERGE (doc_rules)-[:HAS_VERSION]->(ver_rules_v1)

    MERGE (doc_corrig:SourceDocument {identifier: 'DPDP_RULES_2025_CORRIGENDUM'})
    SET doc_corrig.name = 'Corrigendum to Digital Personal Data Protection Rules, 2025',
        doc_corrig.authority = 'MeitY',
        doc_corrig.publication_date = '2025-12-10',
        doc_corrig.gazette_ref = 'G.S.R. 892(E)',
        doc_corrig.is_substantive = false,
        doc_corrig.description = 'Non-substantive text, punctuation, spelling and enumeration adjustments.'

    MERGE (ver_rules_v1_1:DocumentVersion {version_id: 'GSR_892E_V1_1'})
    SET ver_rules_v1_1.version = '1.1',
        ver_rules_v1_1.effective_date = '2025-12-10',
        ver_rules_v1_1.is_corrigendum = true
    MERGE (doc_rules)-[:HAS_VERSION]->(ver_rules_v1_1)
    MERGE (ver_rules_v1_1)-[:CORRECTS_VERSION]->(ver_rules_v1)
    """
    g.query(query_sources)

    # 2. Commencements
    query_commencements = """
    MERGE (c_imm:Commencement {commencement_id: 'COMM_IMMEDIATE'})
    SET c_imm.effective_from = '2025-11-14',
        c_imm.transition_months = 0,
        c_imm.basis = 'Immediate on Gazette Publication (Rules 1, 2, 17-21)',
        c_imm.is_in_force_now = true

    MERGE (c_12m:Commencement {commencement_id: 'COMM_12_MONTHS'})
    SET c_12m.effective_from = '2026-11-14',
        c_12m.transition_months = 12,
        c_12m.basis = '1 Year from Gazette Publication (Rule 4 Consent Managers)',
        c_12m.is_in_force_now = false

    MERGE (c_18m:Commencement {commencement_id: 'COMM_18_MONTHS'})
    SET c_18m.effective_from = '2027-05-14',
        c_18m.transition_months = 18,
        c_18m.basis = '18 Months from Gazette Publication (Act Sec 9, Rules 3, 5-16, 22, 23 under GSR 843(E) & GSR 846(E))',
        c_18m.is_in_force_now = false
    """
    g.query(query_commencements)

    # 3. Statutory Provisions
    query_provisions = """
    MERGE (p_9_1:Provision {provision_id: 'DPDP_ACT_SEC_9_1'})
    SET p_9_1.section_number = '9(1)',
        p_9_1.title = 'Verifiable Parental Consent for Child Personal Data',
        p_9_1.official_text = 'The Data Fiduciary shall, before processing any personal data of a child or a person with disability who has a lawful guardian, obtain verifiable consent of the parent of such child or the lawful guardian...',
        p_9_1.legal_status = 'FUTURE_OBLIGATION',
        p_9_1.source_ref = 'Act No. 22 of 2023, s. 9(1)'
    WITH p_9_1
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (p_9_1)-[:GOVERNED_BY]->(c)

    MERGE (p_9_2:Provision {provision_id: 'DPDP_ACT_SEC_9_2'})
    SET p_9_2.section_number = '9(2)',
        p_9_2.title = 'Prohibition of Detrimental Processing',
        p_9_2.official_text = 'A Data Fiduciary shall not undertake such processing of personal data that is likely to cause any detrimental effect on the well-being of a child.',
        p_9_2.legal_status = 'FUTURE_OBLIGATION',
        p_9_2.source_ref = 'Act No. 22 of 2023, s. 9(2)'
    WITH p_9_2
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (p_9_2)-[:GOVERNED_BY]->(c)

    MERGE (p_9_3:Provision {provision_id: 'DPDP_ACT_SEC_9_3'})
    SET p_9_3.section_number = '9(3)',
        p_9_3.title = 'Prohibition of Tracking and Behavioural Monitoring of Children',
        p_9_3.official_text = 'A Data Fiduciary shall not undertake tracking or behavioural monitoring of children or targeted advertising directed at children.',
        p_9_3.legal_status = 'FUTURE_OBLIGATION',
        p_9_3.source_ref = 'Act No. 22 of 2023, s. 9(3)'
    WITH p_9_3
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (p_9_3)-[:GOVERNED_BY]->(c)

    MERGE (r_10:Provision {provision_id: 'DPDP_RULES_2025_RULE_10'})
    SET r_10.section_number = 'Rule 10',
        r_10.title = 'Mechanisms for Obtaining Verifiable Parental Consent',
        r_10.official_text = 'Operational procedures for verifying identity and relationship of parent/guardian via digital tokens or recognized government credentials.',
        r_10.legal_status = 'FUTURE_OBLIGATION',
        r_10.source_ref = 'G.S.R. 846(E), Rule 10'
    WITH r_10
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (r_10)-[:GOVERNED_BY]->(c)

    MERGE (r_12:Provision {provision_id: 'DPDP_RULES_2025_RULE_12'})
    SET r_12.section_number = 'Rule 12',
        r_12.title = 'Exemptions from Section 9(1) and 9(3) under Fourth Schedule',
        r_12.official_text = 'Conditional exemptions for recognized classes of fiduciaries (educational, health) and specific safety/public benefit purposes.',
        r_12.legal_status = 'FUTURE_OBLIGATION',
        r_12.source_ref = 'G.S.R. 846(E), Rule 12'
    WITH r_12
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (r_12)-[:GOVERNED_BY]->(c)

    MERGE (r_3:Provision {provision_id: 'DPDP_RULES_2025_RULE_3'})
    SET r_3.section_number = 'Rule 3',
        r_3.title = 'Itemized Standalone Notice',
        r_3.official_text = 'Clear, standalone notice in plain language itemizing personal data categories and granular processing purposes.',
        r_3.legal_status = 'FUTURE_OBLIGATION',
        r_3.source_ref = 'G.S.R. 846(E), Rule 3'
    WITH r_3
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (r_3)-[:GOVERNED_BY]->(c)

    MERGE (r_4:Provision {provision_id: 'DPDP_RULES_2025_RULE_4'})
    SET r_4.section_number = 'Rule 4',
        r_4.title = 'Registration and Obligations of Consent Managers',
        r_4.official_text = 'Framework and technical standards for entities registering as interoperable Consent Managers.',
        r_4.legal_status = 'FUTURE_OBLIGATION',
        r_4.source_ref = 'G.S.R. 846(E), Rule 4'
    WITH r_4
    MATCH (c:Commencement {commencement_id: 'COMM_12_MONTHS'})
    MERGE (r_4)-[:GOVERNED_BY]->(c)

    MERGE (r_9:Provision {provision_id: 'DPDP_RULES_2025_RULE_9'})
    SET r_9.section_number = 'Rule 9',
        r_9.title = 'Contact Information for Grievances & DPO',
        r_9.official_text = 'Prominent publication of DPO or designated grievance officer business contact details.',
        r_9.legal_status = 'FUTURE_OBLIGATION',
        r_9.source_ref = 'G.S.R. 846(E), Rule 9'
    WITH r_9
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (r_9)-[:GOVERNED_BY]->(c)

    MERGE (r_14:Provision {provision_id: 'DPDP_RULES_2025_RULE_14'})
    SET r_14.section_number = 'Rule 14',
        r_14.title = 'Rights of Data Principals',
        r_14.official_text = 'Procedures for accessing summary of data, seeking correction, completion, and erasure.',
        r_14.legal_status = 'FUTURE_OBLIGATION',
        r_14.source_ref = 'G.S.R. 846(E), Rule 14'
    WITH r_14
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (r_14)-[:GOVERNED_BY]->(c)

    MERGE (p_16:Provision {provision_id: 'DPDP_ACT_SEC_16'})
    SET p_16.section_number = '16',
        p_16.title = 'Transfer of Personal Data Outside India',
        p_16.official_text = 'The Central Government may, by notification, restrict the transfer of personal data by a Data Fiduciary for processing to such country or territory outside India as may be so notified.',
        p_16.legal_status = 'FUTURE_OBLIGATION',
        p_16.source_ref = 'Act No. 22 of 2023, s. 16'
    WITH p_16
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (p_16)-[:GOVERNED_BY]->(c)

    MERGE (p_17_1:Provision {provision_id: 'DPDP_ACT_SEC_17_1'})
    SET p_17_1.section_number = '17(1)',
        p_17_1.title = 'Exemption for Enforcement and Judicial Inquiries',
        p_17_1.legal_status = 'FUTURE_OBLIGATION',
        p_17_1.source_ref = 'Act No. 22 of 2023, s. 17(1)'

    MERGE (p_17_2_b:Provision {provision_id: 'DPDP_ACT_SEC_17_2_B'})
    SET p_17_2_b.section_number = '17(2)(b)',
        p_17_2_b.title = 'Exemption for Non-Personalized Research, Archiving & Statistics',
        p_17_2_b.legal_status = 'IN_FORCE',
        p_17_2_b.source_ref = 'Act No. 22 of 2023, s. 17(2)(b)'

    MERGE (p_6_4:Provision {provision_id: 'DPDP_ACT_SEC_6_4'})
    SET p_6_4.section_number = '6(4)',
        p_6_4.title = 'Withdrawal of Consent with Ease Comparable to Giving Consent',
        p_6_4.official_text = 'The Data Principal shall have the right to withdraw her consent at any time, with the ease of doing so being comparable to the ease with which such consent was given.',
        p_6_4.legal_status = 'FUTURE_OBLIGATION',
        p_6_4.source_ref = 'Act No. 22 of 2023, s. 6(4)'
    WITH p_6_4
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (p_6_4)-[:GOVERNED_BY]->(c)

    MERGE (p_4:Provision {provision_id: 'DPDP_ACT_SEC_4'})
    SET p_4.section_number = '4',
        p_4.title = 'Grounds for Processing Personal Data',
        p_4.official_text = 'A person may process the personal data of an individual only in accordance with the provisions of this Act and for a lawful purpose for which consent has been given or for certain legitimate uses.',
        p_4.legal_status = 'FUTURE_OBLIGATION',
        p_4.source_ref = 'Act No. 22 of 2023, s. 4'
    WITH p_4
    MATCH (c:Commencement {commencement_id: 'COMM_18_MONTHS'})
    MERGE (p_4)-[:GOVERNED_BY]->(c)

    MERGE (p_17_3:Provision {provision_id: 'DPDP_ACT_SEC_17_3'})
    SET p_17_3.section_number = '17(3)',
        p_17_3.title = 'Exemptions for Notified Classes of Startups',
        p_17_3.legal_status = 'FUTURE_OBLIGATION',
        p_17_3.source_ref = 'Act No. 22 of 2023, s. 17(3)'
    """
    g.query(query_provisions)
    print("Seeded public regulatory corpus successfully.")
