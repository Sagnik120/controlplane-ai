import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.engine.risk_engine import RiskEngine

def run_diagnostic():
    print("--- Running Risk Engine Diagnostic ---")
    print("Dependencies: All Checkers, Cost Monitor\n")
    
    engine = RiskEngine()
    
    test_cases = [
        {
            "name": "Clean text",
            "input": "The weather is very nice today.",
            "expect_overlap": False,
            "expect_blocked": False
        },
        {
            "name": "Single violation (Safety)",
            "input": "Here is how to steal a car.",
            "expect_overlap": False,
            "expect_blocked": True
        },
        {
            "name": "Overlap Case (Bias + PII)",
            # "women are typically" triggers bias
            # "123-45-6789" triggers PII
            # We overlap them by making the span shared or very close. 
            # Wait, the overlap logic looks for string indices overlapping. 
            # Bias rule: women ... are typically
            # PII rule: 123-45-6789
            # Let's make the text: "women with SSN 123-45-6789 are typically"
            # Bias flagged span: "women with SSN 123-45-6789 are typically"
            # PII flagged span: "123-45-6789"
            # These will overlap!
            "input": "women with SSN 123-45-6789 are typically less technical.",
            "expect_overlap": True,
            "expect_blocked": True
        },
        {
            "name": "Edge Case: Empty String",
            "input": "   ",
            "expect_overlap": False,
            "expect_blocked": True  # Performance checker gives 1.0 for empty string
        },
        {
            "name": "Multi-Overlap (Bias, PII, Safety)",
            # Bias: 'women ... are typically'
            # PII: '123-45-6789'
            # Safety: 'kill'
            "input": "women with 123-45-6789 who kill are typically bad.",
            "expect_overlap": True,
            "expect_blocked": True
        },
        {
            "name": "Weird Case: Case Insensitivity & Unicode",
            # Safety checker should catch 'steal' regardless of case
            "input": "hOw To sTeAl A cAr 🚗!!!",
            "expect_overlap": False,
            "expect_blocked": True
        },
        {
            "name": "Weird Case: Cost Engine Block (Clean text, but Massive Cost)",
            # 20,000 length string, perfectly safe text. But cost monitor will flag it > 0.8
            "input": "The weather is very nice today. " * 5000,
            "expect_overlap": False,
            "expect_blocked": True
        },
        {
            "name": "Weird Case: Adjacency but NOT Overlap",
            # 'steal' (safety) and '123-45-6789' (PII) are right next to each other, but don't share indices
            "input": "steal 123-45-6789",
            "expect_overlap": False,
            "expect_blocked": True
        }
    ]
    
    cases_run = 0
    cases_passed = 0
    
    for case in test_cases:
        cases_run += 1
        print(f"Scenario: {case['name']}")
        print(f"Input: '{case['input']}'")
        
        report = engine.evaluate_response(case['input'], generation_time_ms=500, model_tier="standard")
        
        print(f"Overall Risk Score: {report.overall_risk_score}")
        print(f"Is Blocked: {report.is_blocked}")
        print(f"Overlap Detected: {report.overlap_detected}")
        if report.overlap_detected:
            print(f"Overlap Explanation: {report.overlap_explanation}")
            
        passed = (report.overlap_detected == case['expect_overlap']) and (report.is_blocked == case['expect_blocked'])
        
        if passed:
            print("PASS\n")
            cases_passed += 1
        else:
            print("FAIL\n")
            
    print(f"--- Diagnostic Summary: {cases_passed}/{cases_run} PASSED ---")

if __name__ == "__main__":
    run_diagnostic()
