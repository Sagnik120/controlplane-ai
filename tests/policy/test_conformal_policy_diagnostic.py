import sys
import os

# Ensure src/ is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.engine.risk_engine import FinalRiskReport
from src.checkers.base import CheckerResult
from src.policy.schemas import UseCasePolicy
from src.policy.control_policy import ControlPolicy

def print_header(title):
    print("\n" + "="*80)
    print(f"🔒 {title}")
    print("="*80)

def main():
    print_header("Initializing Conformal Tiered Routing Diagnostics...")
    
    # Mock Policy with Calibrated Thresholds
    policy = UseCasePolicy(
        name="test_conformal",
        alpha_low=0.10,
        alpha_high=0.01,
        modify_span_threshold_pct=25.0, # < 25% is MODIFY, else REGENERATE
        calibrated_thresholds={
            "pii": {"tau_low": 0.500, "tau_high": 0.850},
            "performance": {"tau_low": 0.600, "tau_high": 0.900}
        }
    )
    
    policy_controller = ControlPolicy()
    
    test_cases = [
        # 1. ALLOW (Below tau_low)
        {
            "name": "1. Tier 1 (ALLOW): Score below τ_low",
            "report": FinalRiskReport(
                overall_risk_score=0.4,
                is_blocked=False,
                overlap_detected=False,
                checker_results=[
                    CheckerResult(checker_name="pii", risk_score=0.4, explanation="Test")
                ]
            ),
            "response_text": "This is a clean response with no issues.",
            "expected_action": "ALLOW"
        },
        # 2. MODIFY (Between tau_low and tau_high, Localized)
        {
            "name": "2. Tier 2 (MODIFY): Mid-severity, localized spans",
            "report": FinalRiskReport(
                overall_risk_score=0.7,
                is_blocked=False,
                overlap_detected=False,
                checker_results=[
                    CheckerResult(
                        checker_name="pii", 
                        risk_score=0.7,
                        explanation="Test",
                        entities=[{"text": "John Doe", "entity_type": "PERSON"}]
                    )
                ]
            ),
            "response_text": "Here is the response. The customer's name is John Doe and he lives somewhere.",
            "expected_action": "MODIFY",
            "desc": "Score 0.7 is between 0.5 (low) and 0.85 (high). 'John Doe' is 8 chars. Response is ~77 chars. 8/77 = 10% (< 25%). Should route to MODIFY."
        },
        # 3. REGENERATE (Between tau_low and tau_high, Diffuse)
        {
            "name": "3. Tier 2 (REGENERATE): Mid-severity, diffuse spans",
            "report": FinalRiskReport(
                overall_risk_score=0.7,
                is_blocked=False,
                overlap_detected=False,
                checker_results=[
                    CheckerResult(
                        checker_name="performance", 
                        risk_score=0.7,
                        explanation="Test",
                        sentence_scores=[{"sentence": "The dog is blue.", "score": 0.75}]
                    )
                ]
            ),
            "response_text": "The dog is blue.",
            "expected_action": "REGENERATE",
            "desc": "Score 0.7 is between 0.6 (low) and 0.90 (high). 'The dog is blue.' is 16 chars. Response is 16 chars. 16/16 = 100% (> 25%). Should route to REGENERATE."
        },
        # 4. HUMAN (Above tau_high)
        {
            "name": "4. Tier 3 (HUMAN): High-severity",
            "report": FinalRiskReport(
                overall_risk_score=0.95,
                is_blocked=False,
                overlap_detected=False,
                checker_results=[
                    CheckerResult(
                        checker_name="pii", 
                        risk_score=0.95,
                        explanation="Test",
                        entities=[{"text": "555-1234", "entity_type": "PHONE"}]
                    )
                ]
            ),
            "response_text": "Call me at 555-1234.",
            "expected_action": "HUMAN",
            "desc": "Score 0.95 > tau_high (0.85). Should escalate immediately."
        },
        # 5. Overlap Promotion
        {
            "name": "5. Tier Promotion via Overlap",
            "report": FinalRiskReport(
                overall_risk_score=0.4, # Both below tau_low individually
                is_blocked=False,
                overlap_detected=True, # But overlap detected!
                checker_results=[
                    CheckerResult(checker_name="pii", risk_score=0.4, explanation="Test"),
                    CheckerResult(checker_name="safety", risk_score=0.4, explanation="Test")
                ]
            ),
            "response_text": "Short response.",
            "expected_action": "REGENERATE",
            "desc": "Overlap detected promotes ALLOW -> NEEDS_REPAIR. Since no valid spans collected (none crossed tau_low), coverage defaults to 0 spans -> REGENERATE."
        }
    ]

    passed = 0
    for case in test_cases:
        print(f"\n▶️ Running: {case['name']}")
        if "desc" in case:
            print(f"  Description: {case['desc']}")
            
        decision = policy_controller.evaluate(case["report"], policy, case["response_text"])
        
        print(f"  Action Result : {decision.action}")
        print(f"  Reasoning     : {decision.reasoning}")
        if decision.calibration_metadata:
            print(f"  Calibration   : α_low={decision.calibration_metadata['alpha_low']}, α_high={decision.calibration_metadata['alpha_high']}")
            
        if decision.action == case["expected_action"]:
            print("  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL (Expected {case['expected_action']}, got {decision.action})")

    print_header(f"Diagnostic Summary: {passed}/{len(test_cases)} Passed")
    if passed == len(test_cases):
        print("🎉 ALL EDGE CASES PASSED! The conformal tiered routing is fully operational.")

if __name__ == "__main__":
    main()
