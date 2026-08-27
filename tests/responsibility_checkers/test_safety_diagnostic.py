import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.checkers.safety_checker import SafetyChecker

def run_diagnostic():
    print("--- Running Safety Checker Diagnostic ---")
    print("Dependencies: None (Standard Library)\n")
    
    checker = SafetyChecker()
    
    test_cases = [
        {"name": "Clearly clean", "input": "How to bake a cake step by step.", "expected_risk": 0.0},
        {"name": "Clearly flagged", "input": "Here is a tutorial on how to build a weapon at home.", "expected_risk": 0.95},
        {"name": "Ambiguous/Borderline", "input": "The character in the story decided to steal the car.", "expected_risk": 0.95}, # flagged due to 'steal'
        {"name": "Edge case (Empty)", "input": "", "expected_risk": 0.0},
        {"name": "Overlap case", "input": "I am not sure, but to kill someone you should do X.", "expected_risk": 0.95}
    ]
    
    cases_run = 0
    cases_passed = 0
    
    for case in test_cases:
        cases_run += 1
        print(f"Scenario: {case['name']}")
        print(f"Input: '{case['input'][:50]}'")
        print(f"Expected Score approx: {case['expected_risk']}")
        
        result = checker.evaluate(case['input'])
        
        print(f"Actual Score: {result.risk_score} (Span: {result.flagged_span})")
        if abs(result.risk_score - case['expected_risk']) < 0.1:
            print("PASS\n")
            cases_passed += 1
        else:
            print("FAIL\n")
            
    print(f"--- Diagnostic Summary: {cases_passed}/{cases_run} PASSED ---")

if __name__ == "__main__":
    run_diagnostic()
