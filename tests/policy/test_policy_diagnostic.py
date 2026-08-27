import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.engine.risk_engine import FinalRiskReport
from src.checkers.base import CheckerResult
from src.policy.schemas import UseCasePolicy
from src.policy.control_policy import ControlPolicy

def run_diagnostic():
    print("--- Running Policy Layer Diagnostic ---")
    
    control = ControlPolicy()
    
    # We construct mock FinalRiskReports and Test Policies
    
    test_cases = [
        {
            "name": "Standard Allow (Below global threshold)",
            "report": FinalRiskReport(
                overall_risk_score=0.5,
                is_blocked=False,
                overlap_detected=False,
                checker_results=[CheckerResult(checker_name="performance", risk_score=0.5, explanation="")]
            ),
            "policy": UseCasePolicy(name="standard", max_overall_risk=0.8),
            "expected_action": "ALLOW"
        },
        {
            "name": "Global Block (Exceeds global threshold)",
            "report": FinalRiskReport(
                overall_risk_score=0.9,
                is_blocked=True,
                overlap_detected=False,
                checker_results=[CheckerResult(checker_name="bias", risk_score=0.9, explanation="")]
            ),
            "policy": UseCasePolicy(name="standard", max_overall_risk=0.8),
            "expected_action": "BLOCK"
        },
        {
            "name": "Strict Checker Override Block (Zero Tolerance PII)",
            "report": FinalRiskReport(
                overall_risk_score=0.4, # Very low global risk
                is_blocked=False,
                overlap_detected=False,
                checker_results=[CheckerResult(checker_name="pii", risk_score=0.4, explanation="")]
            ),
            # But the policy has a 0.1 threshold for PII!
            "policy": UseCasePolicy(name="medical", max_overall_risk=0.9, checker_thresholds={"pii": 0.1}),
            "expected_action": "BLOCK"
        },
        {
            "name": "Overlap Block (Policy strictly forbids overlap)",
            "report": FinalRiskReport(
                overall_risk_score=0.5,
                is_blocked=False,
                overlap_detected=True,
                overlap_explanation="overlapping spans",
                checker_results=[]
            ),
            "policy": UseCasePolicy(name="strict", max_overall_risk=0.8, block_on_overlap=True),
            "expected_action": "BLOCK"
        },
        {
            "name": "Overlap Allowed (Policy permits overlap)",
            "report": FinalRiskReport(
                overall_risk_score=0.5,
                is_blocked=False,
                overlap_detected=True,
                overlap_explanation="overlapping spans",
                checker_results=[]
            ),
            "policy": UseCasePolicy(name="lenient", max_overall_risk=0.8, block_on_overlap=False),
            "expected_action": "ALLOW"
        },
        {
            "name": "Redaction Mode (PII flagged but below block threshold)",
            "report": FinalRiskReport(
                overall_risk_score=0.5,
                is_blocked=False,
                overlap_detected=False,
                checker_results=[CheckerResult(checker_name="pii", risk_score=0.5, explanation="")]
            ),
            "policy": UseCasePolicy(name="redact_app", max_overall_risk=0.8, redact_pii=True),
            "expected_action": "REDACT"
        },
        {
            "name": "Weird Edge Case: Empty Report",
            "report": FinalRiskReport(
                overall_risk_score=0.0,
                is_blocked=False,
                overlap_detected=False,
                checker_results=[]
            ),
            "policy": UseCasePolicy(name="empty_test", max_overall_risk=0.1),
            "expected_action": "ALLOW"
        },
        {
            "name": "Priority Edge Case: BLOCK overrides REDACT",
            "report": FinalRiskReport(
                overall_risk_score=0.9,
                is_blocked=True,
                overlap_detected=False,
                # PII score is 0.9
                checker_results=[CheckerResult(checker_name="pii", risk_score=0.9, explanation="SSN Found")]
            ),
            # Policy says redact PII, BUT the PII threshold is 0.5. 
            # Because 0.9 > 0.5, it must BLOCK instead of REDACT.
            "policy": UseCasePolicy(name="strict_redact", max_overall_risk=1.0, checker_thresholds={"pii": 0.5}, redact_pii=True),
            "expected_action": "BLOCK"
        }
    ]
    
    cases_run = 0
    cases_passed = 0
    
    for case in test_cases:
        cases_run += 1
        print(f"\nScenario: {case['name']}")
        print(f"Policy: {case['policy'].model_dump()}")
        
        decision = control.evaluate(case['report'], case['policy'])
        
        print(f"Decision Action: {decision.action}")
        print(f"Rationale: {decision.rationale}")
        
        if decision.action == case['expected_action']:
            print("PASS")
            cases_passed += 1
        else:
            print(f"FAIL (Expected {case['expected_action']})")
            
    print(f"\n--- Diagnostic Summary: {cases_passed}/{cases_run} PASSED ---")

if __name__ == "__main__":
    run_diagnostic()
