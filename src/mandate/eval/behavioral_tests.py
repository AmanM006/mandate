import json
from typing import Dict, Any, List

class SyntheticBehavioralTestRunner:
    """
    Executes an 8-case behavioral test suite against synthetic signup endpoints
    to verify configuration remediation before and after patch application.
    """
    def __init__(self):
        # 8 Behavioral Test Cases:
        # 4 minor student flows (under 18)
        # 3 adult/educator flows (18+)
        # 1 malformed age request
        self.test_cases = [
            {"id": "TC-B01", "age": 12, "provider": "google_sso", "has_guardian_consent": False, "expect_allow": False, "desc": "12yo student Google SSO without guardian consent"},
            {"id": "TC-B02", "age": 15, "provider": "email_password", "has_guardian_consent": False, "expect_allow": False, "desc": "15yo student email/pwd without guardian consent"},
            {"id": "TC-B03", "age": 16, "provider": "google_sso", "has_guardian_consent": True, "expect_allow": True, "desc": "16yo student Google SSO with verified guardian consent"},
            {"id": "TC-B04", "age": 9, "provider": "apple_sso", "has_guardian_consent": False, "expect_allow": False, "desc": "9yo student Apple SSO without guardian consent"},
            {"id": "TC-B05", "age": 24, "provider": "email_password", "has_guardian_consent": False, "expect_allow": True, "desc": "Adult student registration (24yo)"},
            {"id": "TC-B06", "age": 35, "provider": "google_sso", "has_guardian_consent": False, "expect_allow": True, "desc": "Adult educator registration (35yo)"},
            {"id": "TC-B07", "age": 18, "provider": "email_password", "has_guardian_consent": False, "expect_allow": True, "desc": "Legal age threshold boundary user (18yo)"},
            {"id": "TC-B08", "age": -1, "provider": "google_sso", "has_guardian_consent": False, "expect_allow": False, "desc": "Malformed negative age payload"}
        ]

    def evaluate(self, vendor_strict_handshake: bool, guest_sso_bypass: bool) -> Dict[str, Any]:
        """
        Simulates endpoint behavior under given configuration parameters.
        Returns detailed before/after behavioral report.
        """
        results = []
        passed_cases = 0

        for tc in self.test_cases:
            age = tc["age"]
            is_minor = (0 <= age < 18)
            
            # Simulated System Logic:
            if age < 0:
                allowed = False
                reason = "REJECTED_MALFORMED_AGE"
            elif is_minor:
                # If guest bypass is enabled AND Google SSO, unverified student slips through!
                if guest_sso_bypass and tc["provider"] == "google_sso":
                    allowed = True
                    reason = "ALLOWED_VIA_QUICK_GUEST_BYPASS"
                elif vendor_strict_handshake:
                    allowed = tc["has_guardian_consent"]
                    reason = "ALLOWED_GUARDIAN_VERIFIED" if allowed else "BLOCKED_AWAITING_GUARDIAN_HANDSHAKE"
                else:
                    # Non-strict vendor config allows self-declaration
                    allowed = True
                    reason = "ALLOWED_VIA_UNVERIFIED_SELF_DECLARATION"
            else:
                allowed = True
                reason = "ALLOWED_ADULT_USER"

            # Check if actual behavior matches desired compliance expectation
            case_passed = (allowed == tc["expect_allow"])
            if case_passed:
                passed_cases += 1

            results.append({
                "case_id": tc["id"],
                "description": tc["desc"],
                "age": tc["age"],
                "allowed": allowed,
                "expected_allow": tc["expect_allow"],
                "passed": case_passed,
                "reason": reason
            })

        return {
            "total_cases": len(self.test_cases),
            "passed_cases": passed_cases,
            "failed_cases": len(self.test_cases) - passed_cases,
            "all_passed": (passed_cases == len(self.test_cases)),
            "details": results
        }
