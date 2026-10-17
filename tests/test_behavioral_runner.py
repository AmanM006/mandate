import pytest
from src.mandate.eval.behavioral_tests import SyntheticBehavioralTestRunner

def test_behavioral_runner_pre_patch_failure():
    """
    Before remediation: guest_sso_bypass is TRUE and vendor strict handshake is FALSE.
    Fails on minor bypass cases.
    """
    runner = SyntheticBehavioralTestRunner()
    res = runner.evaluate(vendor_strict_handshake=False, guest_sso_bypass=True)
    assert res["all_passed"] is False
    assert res["failed_cases"] > 0
    # Specifically, TC-B01 (12yo Google SSO) slipped through
    tc_b01 = next(c for c in res["details"] if c["case_id"] == "TC-B01")
    assert tc_b01["passed"] is False
    assert tc_b01["reason"] == "ALLOWED_VIA_QUICK_GUEST_BYPASS"

def test_behavioral_runner_post_patch_success():
    """
    After remediation: guest_sso_bypass is FALSE and vendor strict handshake is TRUE.
    All 8 cases must pass.
    """
    runner = SyntheticBehavioralTestRunner()
    res = runner.evaluate(vendor_strict_handshake=True, guest_sso_bypass=False)
    assert res["all_passed"] is True
    assert res["passed_cases"] == 8
    assert res["failed_cases"] == 0
    
    # 12yo Google SSO blocked awaiting guardian handshake
    tc_b01 = next(c for c in res["details"] if c["case_id"] == "TC-B01")
    assert tc_b01["passed"] is True
    assert tc_b01["allowed"] is False
    assert tc_b01["reason"] == "BLOCKED_AWAITING_GUARDIAN_HANDSHAKE"

    # Adult educator allowed
    tc_b06 = next(c for c in res["details"] if c["case_id"] == "TC-B06")
    assert tc_b06["passed"] is True
    assert tc_b06["allowed"] is True
