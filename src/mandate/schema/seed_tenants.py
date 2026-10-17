from src.mandate.schema.db import FalkorClientManager

def seed_flagship_aetherlearn(db_mgr: FalkorClientManager):
    """
    Seeds the Flagship Tenant (AetherLearn Labs) into 'mandate_aetherlearn'.
    Models:
    - Company, Products, DataFlows, Controls, Evidence
    - The planted conflict: POL-DPDP-2025-01 vs ENG-8419 Google SSO Quick Preview bypass
    - Claims, multi-premise dependencies, InvalidationEvent structures
    """
    g = db_mgr.get_tenant_graph("aetherlearn")
    
    query = """
    // 1. Company & Product
    MERGE (comp:Company {tenant_id: 'aetherlearn'})
    SET comp.name = 'AetherLearn Labs Pvt Ltd',
        comp.industry = 'EdTech / K-12 STEM Education',
        comp.jurisdiction = 'India'

    MERGE (prod:Product {product_id: 'PROD_STEM_ACADEMY', tenant_id: 'aetherlearn'})
    SET prod.name = 'AetherSTEM Academy',
        prod.target_audience = 'Students aged 8-18'
    MERGE (comp)-[:OFFERS_PRODUCT]->(prod)

    // 2. Data Categories
    MERGE (cat_child:DataCategory {category_id: 'CAT_CHILD_PROFILE', tenant_id: 'aetherlearn'})
    SET cat_child.name = 'Minor Student Profile & Educational Records',
        cat_child.is_child_data = true,
        cat_child.sensitivity = 'HIGH'

    MERGE (cat_parent:DataCategory {category_id: 'CAT_PARENT_CONTACT', tenant_id: 'aetherlearn'})
    SET cat_parent.name = 'Parent/Guardian Contact & Consent Proof',
        cat_parent.is_child_data = false,
        cat_parent.sensitivity = 'MEDIUM'

    MERGE (cat_telemetry:DataCategory {category_id: 'CAT_TELEMETRY', tenant_id: 'aetherlearn'})
    SET cat_telemetry.name = 'Course Telemetry & Keystroke Cadence',
        cat_telemetry.is_child_data = true,
        cat_telemetry.sensitivity = 'MEDIUM'

    MERGE (cat_billing:DataCategory {category_id: 'CAT_BILLING', tenant_id: 'aetherlearn'})
    SET cat_billing.name = 'Subscription Payment Records',
        cat_billing.is_child_data = false,
        cat_billing.sensitivity = 'HIGH'

    // 3. Systems & Vendors
    MERGE (sys_auth:System {system_id: 'SYS_AUTH_GATEWAY', tenant_id: 'aetherlearn'})
    SET sys_auth.name = 'Auth0 / Custom SSO Gateway',
        sys_auth.tier = 'TIER_1'

    MERGE (sys_analytics:System {system_id: 'SYS_ANALYTICS_PIPELINE', tenant_id: 'aetherlearn'})
    SET sys_analytics.name = 'ClickHouse Event Stream',
        sys_analytics.tier = 'TIER_2'

    MERGE (vnd_kiddcheck:Vendor {vendor_id: 'VND_01', tenant_id: 'aetherlearn'})
    SET vnd_kiddcheck.name = 'KiddCheck ID',
        vnd_kiddcheck.service_type = 'Verifiable Parental Consent (VPC) & Age Assurance',
        vnd_kiddcheck.enforce_strict_guardian_handshake = false

    MERGE (vnd_trackpulse:Vendor {vendor_id: 'VND_02', tenant_id: 'aetherlearn'})
    SET vnd_trackpulse.name = 'TrackPulse SDK',
        vnd_trackpulse.service_type = 'User Engagement & Behavioral Telemetry'

    // 4. Data Flows
    MERGE (df_signup:DataFlow {flow_id: 'DF_01', tenant_id: 'aetherlearn'})
    SET df_signup.endpoint = '/api/v2/auth/student-signup',
        df_signup.protocol = 'HTTPS/REST',
        df_signup.description = 'Student registration, age gating, and initial token issuance'
    MERGE (df_signup)-[:PROCESSES]->(cat_child)
    MERGE (df_signup)-[:DEPENDS_ON]->(sys_auth)
    MERGE (df_signup)-[:INTEGRATES_WITH]->(vnd_kiddcheck)

    MERGE (df_telemetry:DataFlow {flow_id: 'DF_02', tenant_id: 'aetherlearn'})
    SET df_telemetry.endpoint = '/api/v1/telemetry/events',
        df_telemetry.protocol = 'WSS/JSON',
        df_telemetry.description = 'Continuous tracking of interaction events, problem solve duration, keystrokes'
    MERGE (df_telemetry)-[:PROCESSES]->(cat_telemetry)
    MERGE (df_telemetry)-[:DEPENDS_ON]->(sys_analytics)
    MERGE (df_telemetry)-[:INTEGRATES_WITH]->(vnd_trackpulse)

    MERGE (df_billing:DataFlow {flow_id: 'DF_03', tenant_id: 'aetherlearn'})
    SET df_billing.endpoint = '/api/v2/parent/subscription',
        df_billing.protocol = 'HTTPS/REST',
        df_billing.description = 'Stripe webhook payment processing for annual parent subscription'
    MERGE (df_billing)-[:PROCESSES]->(cat_billing)

    MERGE (df_research:DataFlow {flow_id: 'DF_04', tenant_id: 'aetherlearn'})
    SET df_research.endpoint = '/api/v1/research/pedagogical-stats',
        df_research.protocol = 'HTTPS/BATCH',
        df_research.description = 'Aggregated learning efficacy research dataset with irreversible tokenization'

    // 5. Controls
    MERGE (ctl_vpc:Control {control_id: 'CTL_VPC_GATE', tenant_id: 'aetherlearn'})
    SET ctl_vpc.name = 'Guardian Verifiable Consent Gate',
        ctl_vpc.description = 'Mandatory parent verification before student profile activation',
        ctl_vpc.status = 'DEGRADED_BYPASSED'
    MERGE (ctl_vpc)-[:COVERS_FLOW]->(df_signup)

    MERGE (ctl_enc:Control {control_id: 'CTL_BILLING_ENCRYPTION', tenant_id: 'aetherlearn'})
    SET ctl_enc.name = 'Payment Card & Billing AES-256 GCM Encryption',
        ctl_enc.status = 'ACTIVE_VERIFIED'
    MERGE (ctl_enc)-[:COVERS_FLOW]->(df_billing)

    MERGE (ctl_research:Control {control_id: 'CTL_RESEARCH_ANONYMIZATION', tenant_id: 'aetherlearn'})
    SET ctl_research.name = 'Sec 17(2)(b) Pedagogical Research Anonymizer',
        ctl_research.status = 'ACTIVE_VERIFIED'
    MERGE (ctl_research)-[:COVERS_FLOW]->(df_research)

    // 6. Evidence: The Conflict and the Bypass
    MERGE (ev_policy:Evidence {evidence_id: 'EV_POL_01', tenant_id: 'aetherlearn'})
    SET ev_policy.type = 'POLICY_DOCUMENT',
        ev_policy.title = 'AetherLearn DPDP Policy POL-DPDP-2025-01',
        ev_policy.recorded_at = '2025-09-15T10:00:00Z',
        ev_policy.content_summary = 'Section 4.1: Strictly requires parent ID/SMS verification via KiddCheck ID prior to onboarding any user under 18.'
    MERGE (ev_policy)-[:SUPPORTS]->(ctl_vpc)

    MERGE (ev_ticket:Evidence {evidence_id: 'EV_TICKET_ENG_8419', tenant_id: 'aetherlearn'})
    SET ev_ticket.type = 'ENGINEERING_TICKET',
        ev_ticket.title = 'Jira ENG-8419: Add Quick Guest Preview via Google SSO',
        ev_ticket.recorded_at = '2026-03-10T14:30:00Z',
        ev_ticket.evidence_revision = 'REV_EV_ENG_8419_v1',
        ev_ticket.content_summary = 'Implemented bypass in student-signup route allowing users under 18 to skip guardian verification if registering via Google SSO.'
    MERGE (ev_ticket)-[:CONTRADICTS]->(ctl_vpc)
    MERGE (df_signup)-[:BYPASSES]->(ctl_vpc)

    // 7. Premises, Claims & Dependency Chains
    MERGE (prm_vpc:Premise {premise_id: 'PRM_001', tenant_id: 'aetherlearn'})
    SET prm_vpc.statement = 'All student registrations are strictly verified by KiddCheck ID before profile activation.',
        prm_vpc.status = 'VALID_ACTIVE'
    MERGE (ev_policy)-[:SUPPORTS_PREMISE]->(prm_vpc)

    MERGE (prm_enc:Premise {premise_id: 'PRM_004', tenant_id: 'aetherlearn'})
    SET prm_enc.statement = 'Stripe payment webhooks utilize AES-256 GCM authenticated payload encryption.',
        prm_enc.status = 'VALID_ACTIVE'

    // Root Claim: Verifiable Parental Consent
    MERGE (clm_vpc:Claim {claim_id: 'CLM_VPC_01', tenant_id: 'aetherlearn'})
    SET clm_vpc.provision_id = 'DPDP_ACT_SEC_9_1',
        clm_vpc.assertion = 'AetherLearn enforces Section 9(1) verifiable parental consent across all youth signups.',
        clm_vpc.status = 'VALID_ACTIVE',
        clm_vpc.is_stale = false
    MERGE (clm_vpc)-[:DEPENDS_ON_PREMISE]->(prm_vpc)

    // Independent Billing Claim
    MERGE (clm_enc:Claim {claim_id: 'CLM_ENC_04', tenant_id: 'aetherlearn'})
    SET clm_enc.provision_id = 'DPDP_ACT_SEC_8_5',
        clm_enc.assertion = 'Payment data flow DF_03 satisfies reasonable security safeguards.',
        clm_enc.status = 'VALID_ACTIVE',
        clm_enc.is_stale = false
    MERGE (clm_enc)-[:DEPENDS_ON_PREMISE]->(prm_enc)

    // 8. Invalidation History Event (Preserving Audit Trail)
    MERGE (inval_evt:InvalidationEvent {event_id: 'INVAL_EVT_001', tenant_id: 'aetherlearn'})
    SET inval_evt.timestamp = 1774880000000,
        inval_evt.triggered_by_premise = 'PRM_001',
        inval_evt.previous_status = 'VALID_ACTIVE',
        inval_evt.new_status = 'INVALIDATED_STALE',
        inval_evt.reason = 'Contradiction identified: ENG-8419 Google SSO Quick Preview bypass'
    MERGE (clm_vpc)-[:HAS_INVALIDATION_HISTORY]->(inval_evt)

    // 9. Initial Open Task & ActionProposal for Remediator
    MERGE (tsk_remed:Task {task_id: 'TSK_REMED_01', tenant_id: 'aetherlearn'})
    SET tsk_remed.type = 'APPLY_REMEDIATION',
        tsk_remed.status = 'OPEN',
        tsk_remed.lease_version = 0,
        tsk_remed.retry_count = 0,
        tsk_remed.max_retries = 3,
        tsk_remed.target_claim_id = 'CLM_VPC_01',
        tsk_remed.idempotency_key = null,
        tsk_remed.description = 'Draft remediation configuration removing Google SSO guest bypass and enforcing strict KiddCheck ID handshake.'

    // Stored ActionProposal with allowlisted configuration parameters
    MERGE (prop:ActionProposal {proposal_id: 'PROP_REMED_01', tenant_id: 'aetherlearn'})
    SET prop.target_claim_id = 'CLM_VPC_01',
        prop.target_vendor_id = 'VND_01',
        prop.target_flow_id = 'DF_01',
        prop.status = 'PENDING_APPROVAL',
        prop.enforce_strict_guardian_handshake = true,
        prop.remove_guest_bypass = true,
        prop.evidence_revision = 'REV_EV_ENG_8419_v1',
        prop.created_at = timestamp()
    MERGE (prop)-[:REMEDIES_CLAIM]->(clm_vpc)
    MERGE (prop)-[:BASED_ON_EVIDENCE]->(ev_ticket)
    MERGE (tsk_remed)-[:EXECUTES_PROPOSAL]->(prop)
    """
    g.query(query)
    print("Seeded AetherLearn flagship graph successfully.")

def seed_isolated_nexusops(db_mgr: FalkorClientManager):
    """
    Seeds Tenant 2 (NexusOps Cloud) into 'mandate_nexusops'.
    Demonstrates multi-tenant isolation and subtle flow handling.
    """
    g = db_mgr.get_tenant_graph("nexusops")
    
    query = """
    MERGE (comp:Company {tenant_id: 'nexusops'})
    SET comp.name = 'NexusOps Cloud Inc',
        comp.industry = 'B2B Cloud Observability & APM',
        comp.jurisdiction = 'India & Global'

    MERGE (df_syslog:DataFlow {flow_id: 'DF_101', tenant_id: 'nexusops'})
    SET df_syslog.endpoint = '/v1/ingest/syslog',
        df_syslog.protocol = 'TCP/TLS',
        df_syslog.description = 'Enterprise cluster log ingestion'

    MERGE (df_intern:DataFlow {flow_id: 'DF_103', tenant_id: 'nexusops'})
    SET df_intern.endpoint = '/api/v1/intern-seats',
        df_intern.protocol = 'HTTPS/REST',
        df_intern.description = 'Enterprise customer FinCorp high-school apprentice user provisioning'

    MERGE (cat_apprentice:DataCategory {category_id: 'CAT_APPRENTICE', tenant_id: 'nexusops'})
    SET cat_apprentice.name = 'Minor Apprentice Corporate Account',
        cat_apprentice.is_child_data = true
    MERGE (df_intern)-[:PROCESSES]->(cat_apprentice)

    MERGE (clm_b2b:Claim {claim_id: 'CLM_NEXUS_01', tenant_id: 'nexusops'})
    SET clm_b2b.provision_id = 'DPDP_ACT_SEC_4',
        clm_b2b.status = 'VALID_ACTIVE',
        clm_b2b.assertion = 'NexusOps standard log processing is lawful under enterprise customer contracts.'
    """
    g.query(query)
    print("Seeded NexusOps isolated graph successfully.")
