# Milestone 1: Authoritative DPDP Matrix, Synthetic Scenarios & 30-Case Answer Key

## 1. Official Legal Corpus & Commencement Schedule

### Official References
1. **Digital Personal Data Protection Act, 2023 (Act No. 22 of 2023)**
   - Official Gazette of India, Extraordinary, Part II, Section 1, dated 11th August 2023.
   - Primary provisions governing children's data: **Section 9** (Processing of personal data of children and persons with disabilities).
   - Core compliance mandates:
     - *Section 9(1)*: Verifiable consent of parent/lawful guardian prior to processing child personal data.
     - *Section 9(2)*: Prohibition against processing that is likely to cause detrimental effect on well-being of a child.
     - *Section 9(3)*: Prohibition against tracking, behavioral monitoring, or targeted advertising directed at children.

2. **Digital Personal Data Protection Rules, 2025 (G.S.R. 846(E))**
   - Published by Ministry of Electronics and Information Technology (MeitY) on **14th November 2025**.
   - Primary provisions governing children's data mechanisms:
     - **Rule 10**: Mechanisms for obtaining verifiable parental consent under Section 9(1).
     - **Rule 4**: Notice requirements under Section 5 (Commencement: 1 year from publication = **14th November 2026**).
     - **Rules 3, 5–16, 22, 23**: Procedural obligations, child consent mechanisms, consent manager standards, and breach notifications (Commencement: 18 months from publication = **14th May 2027**).
     - *Crucial note*: Rule 10 commences on **14th May 2027** (18 months basis). Any audit conducted before this date evaluates *preparatory alignment*, not current penal default.

3. **Official Corrigendum (G.S.R. 892(E))**
   - Published by MeitY on **12th December 2025**.
   - Corrected typographic, cross-referencing, and grammatical errors in G.S.R. 846(E) (e.g., cross-references between Schedule II form templates and Rule 10(2) verification guidelines).
   - *Legal characterization*: Non-substantive text revision; updates source document versioning from `v1.0` to `v1.1` without altering commencement windows or establishing novel substantive duties.

---

## 2. Synthetic Company Postures (Tenants)

### Tenant 1: AetherLearn Labs (Flagship EdTech / Youth Learning)
- **Business Profile**: Interactive STEM learning platform serving students aged 8–18 in India and Southeast Asia.
- **Data Flows**:
  - `DF-01`: Student Onboarding & Age Verification (`/api/v2/auth/student-signup`).
  - `DF-02`: Classroom Progress & Telemetry Analytics (`/api/v1/telemetry/events`).
  - `DF-03`: Parent Notification & Billing Gateway (`/api/v2/parent/consent-callback`).
- **Vendors**:
  - `VND-01 (KiddCheck ID)`: Third-party age assurance and verifiable parental consent (VPC) gateway.
  - `VND-02 (TrackPulse SDK)`: Behavioral event logging and telemetry aggregator.
- **The Core Conflict**:
  1. *Policy & Spec*: `POL-DPDP-2025-01` specifies that all users under 18 must verify parent email or government ID via `KiddCheck ID` before account activation.
  2. *Internal Architectural Review*: `DEC-2025-08-ARCH` approved parental consent architecture based on `KiddCheck ID v1.4` API spec.
  3. *Contradictory Reality*: In `v2.4.1` release (ticket `ENG-8419`), engineering added a "Quick Guest Preview" bypass in `student-signup` that lets students skip guardian verification if onboarding via Google SSO. Furthermore, `VND-01` webhook configuration sets `enforce_strict_guardian_handshake: false` to reduce signup friction.
  4. *Telemetry Contradiction*: `TrackPulse SDK` continues tracking user keystroke cadence and course browsing behaviors for all signed-in users, violating Section 9(3) prohibition on behavioral profiling of minors.

### Tenant 2: NexusOps Cloud (B2B Infrastructure & Monitoring)
- **Business Profile**: Enterprise cloud observability, APM, and log monitoring SaaS sold exclusively to IT departments and DevOps engineers.
- **Data Flows**:
  - `DF-101`: Enterprise Agent Log Streaming (`/v1/ingest/syslog`).
  - `DF-102`: Corporate SSO & Role-Based Access Control (`/oauth/v2/saml`).
- **Data Categories**: Corporate IP addresses, machine identifiers, corporate employee work emails (`@company.com`).
- **Legal Posture**: Excluded from DPDP Section 9 and Rule 10 obligations. No personal data of children processed. Demonstrates multi-tenant isolation and deterministic non-applicability.

---

## 3. Answer Key: 30 Benchmark Cases

The evaluation suite tests 30 distinct compliance and graph-reasoning scenarios across both tenants:

| Case ID | Tenant | Provision / Subject | Ground Truth Status | Expected Reason / Grounding Path |
|---|---|---|---|---|
| **TC-01** | AetherLearn | Section 9(1) - Minor Parental Consent | `NON_COMPLIANT_CONFLICT` | Quick Guest Preview bypass (`DF-01`) contradicts `POL-DPDP-2025-01` & `Section 9(1)`. |
| **TC-02** | AetherLearn | Rule 10 - VPC Verification Standards | `FUTURE_OBLIGATION_PREPARING` | Commences 14 May 2027 (18 mo). Vendor config `enforce_strict_guardian_handshake: false` fails future standard. |
| **TC-03** | AetherLearn | Section 9(3) - Minor Behavioral Tracking | `NON_COMPLIANT_ACTIVE` | `TrackPulse SDK` captures keystrokes/behavioral metrics for minors (`DF-02`). |
| **TC-04** | AetherLearn | Section 9(2) - Detrimental Effect Safety | `VERIFIED_COMPLIANT` | Content moderation system `ModSafe-AI` verified active on all student forum posts. |
| **TC-05** | AetherLearn | Rule 4 - Notice Requirements | `FUTURE_OBLIGATION_PREPARING` | Commences 14 Nov 2026 (12 mo). Notice exists in English/Hindi, requires 22-language translation audit. |
| **TC-06** | AetherLearn | Section 6(1) - Consent Specificity | `VERIFIED_COMPLIANT` | Consent itemization implemented for educational data categories in `DF-01`. |
| **TC-07** | AetherLearn | Corrigendum G.S.R. 892(E) Impact | `VERSION_UPDATE_ONLY` | Textual correction to Schedule II reference; does not create substantive new rule or change date. |
| **TC-08** | AetherLearn | Superseded Design: `DEC-2025-08-ARCH` | `SUPERSEDED` | Depended on KiddCheck v1.4 spec, replaced by v2.4 bypass in `ENG-8419`. |
| **TC-09** | AetherLearn | Superseded Premise: `PRM-001` (Complete Gate) | `SUPERSEDED_INVALIDATED` | Invalidation propagates down to Claim `CLM-VPC-01`. |
| **TC-10** | AetherLearn | Unrelated Premise: `PRM-004` (Billing Encryption) | `RETAINED_VALID` | AES-256 GCM in Stripe webhook unaffected by signup VPC invalidation. |
| **TC-11** | AetherLearn | Vendor Data Retention (KiddCheck ID) | `INSUFFICIENT_EVIDENCE` | Data retention agreement missing in vendor contract metadata; correctly marked UNRESOLVED. |
| **TC-12** | AetherLearn | Consent Withdrawal Mechanism (Sec 6(4)) | `INSUFFICIENT_EVIDENCE` | Parent dashboard mockups exist but no backend endpoint found in routing table; UNRESOLVED. |
| **TC-13** | AetherLearn | DPO Contact in Notice (Rule 4(1)) | `INSUFFICIENT_EVIDENCE` | Privacy policy lists generic `privacy@` email, DPO registration certificate pending. |
| **TC-14** | AetherLearn | Cross-Border Transfer Compliance (Sec 16) | `INSUFFICIENT_EVIDENCE` | Blacklist transfer notification status from Central Govt pending; flagged UNRESOLVED. |
| **TC-15** | AetherLearn | Excluded: Section 17(1) - Law Enforcement Exemption | `EXCLUDED_NON_APPLICABLE` | AetherLearn is private commercial edtech, no court order or law enforcement warrant exists. |
| **TC-16** | AetherLearn | Excluded: Section 17(2)(a) - Research Exemption | `EXCLUDED_NON_APPLICABLE` | Commercial course analytics are not non-profit academic research. |
| **TC-17** | AetherLearn | Excluded: Rule 14 - Consent Manager Audits | `EXCLUDED_NON_APPLICABLE` | AetherLearn is a Data Fiduciary, not an interoperable Consent Manager entity. |
| **TC-18** | AetherLearn | Excluded: Section 10 - Significant Data Fiduciary (SDF) | `EXCLUDED_NON_APPLICABLE` | Not yet notified as SDF by MeitY gazette; SDF-specific audit rules excluded. |
| **TC-19** | AetherLearn | Excluded: Rule 18 - Data Protection Board Inquiries | `EXCLUDED_NON_APPLICABLE` | No active DPB complaint or investigation notice served on company. |
| **TC-20** | AetherLearn | Excluded: Section 17(3) - Clinical Trials Processing | `EXCLUDED_NON_APPLICABLE` | Educational platform does not conduct medical clinical trials. |
| **TC-21** | NexusOps | Section 9(1) - Minor Parental Consent | `EXCLUDED_NON_APPLICABLE` | B2B APM platform processes no children's data; verified zero underage users. |
| **TC-22** | NexusOps | Section 9(3) - Child Behavioral Tracking | `EXCLUDED_NON_APPLICABLE` | B2B platform tracking server metrics, not minor human behavior. |
| **TC-23** | NexusOps | Rule 10 - Child VPC Mechanisms | `EXCLUDED_NON_APPLICABLE` | Non-applicable due to absence of child data categories in schema. |
| **TC-24** | NexusOps | Section 4 - Grounds for Processing Personal Data | `VERIFIED_COMPLIANT` | Corporate admin users processed under legitimate employment/contract purposes. |
| **TC-25** | NexusOps | Rule 4 - Notice to Corporate Admins | `FUTURE_OBLIGATION_PREPARING` | Notice required for corporate console users by 14 Nov 2026. |
| **TC-26** | Cross-Tenant | Data Isolation Leakage Check | `ISOLATED_SECURE` | Querying NexusOps graph for AetherLearn claims yields zero rows and no graph cross-contamination. |
| **TC-27** | AetherLearn | Remediation Action: `PATCH-KIDDCHECK-01` | `ACTION_ELIGIBLE` | Patch disabling guest bypass and setting strict handshake ready for human review. |
| **TC-28** | AetherLearn | Post-Remediation Verification | `BEHAVIORAL_PASS` | Synthetic test runner verifies 6 test cases (under-18 blocked without VPC, 18+ allowed). |
| **TC-29** | AetherLearn | Handoff Interruption & Recovery | `HANDOFF_RECOVERED` | Task `TSK-REMED-01` resumed by secondary worker with lease lock and no duplicate actions. |
| **TC-30** | AetherLearn | Fresh Session Re-Evaluation | `CAUSAL_MEMORY_ACTIVE` | Fresh agent session reads historical invalidation and refuses to re-assert stale claim. |

---

## 3-Minute Live Demo Script

- **[0:00 - 0:30] The Hook & The Contradiction**:
  - Show the Case Inbox in Mandate. 
  - *Claim*: "AetherLearn policy states 100% compliance with DPDP Section 9(1) child consent."
  - *Reality*: The Investigator runs a traversal. In 15 seconds, the UI reveals the contradiction: Engineering ticket `ENG-8419` inserted a Google SSO "Quick Guest Preview" that completely bypasses `KiddCheck ID` age verification for minor students.
  - The UI visually highlights the conflicting evidence path: `(:DataFlow {endpoint: '/student-signup'})-[:BYPASSES]->(:Control {name: 'Guardian-VPC'})`.

- **[0:30 - 1:15] Legal Grounding & Corrigendum Intelligence**:
  - Open the Provision View. Inspect **Section 9(1)** and **Rule 10**.
  - Show the commencement engine: Rule 10 commences on **May 14, 2027** (18 months post-publication). It is tagged as `FUTURE_PREPARATION`, preventing a false penal alert while pinpointing Section 9(1)'s immediate statutory applicability.
  - Show the Corrigendum G.S.R. 892(E) node: correctly tracked as a non-substantive reference correction without resetting legal timelines.

- **[1:15 - 1:50] Selective Invalidation & Handoff Interruption**:
  - The Interpreter marks premise `PRM-001` (VPC gate integrity) as `SUPERSEDED`.
  - Watch FalkorDB dependency traversal instantly invalidate Claim `CLM-VPC-01` while strictly preserving unrelated Claim `CLM-ENC-04` (Stripe billing encryption).
  - Trigger worker handoff: Worker 1 is forcibly interrupted mid-task. Worker 2 picks up the durable task lease with idempotent deduplication and zero lost state.

- **[1:50 - 2:30] Guarded Remediation & Synthetic Behavioral Testing**:
  - Remediator proposes `PATCH-VPC-CFG.yaml`: flips `enforce_strict_guardian_handshake: true` and removes the guest bypass route.
  - Human reviewer clicks **Approve & Test**.
  - 8 synthetic behavioral test cases execute live: 
    - 4 under-18 flows that previously slipped through now strictly require guardian auth.
    - 3 adult/educator flows remain unimpeded.
    - 1 malformed age request is safely rejected.

- **[2:30 - 3:00] Multi-Tenant Isolation & Summary**:
  - Switch tenant to **NexusOps Cloud**.
  - Show that querying for DPDP child consent returns `EXCLUDED_NON_APPLICABLE` with zero cross-tenant data leakage.
  - Conclude: "Mandate turns compliance from a static, hallucinatory PDF chat into an inspectable, self-correcting, graph-native legal operating system."
