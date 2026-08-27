import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.checkers.bias_checker import BiasChecker

def run_diagnostic():
    print("--- Running Bias Checker Diagnostic ---")
    print("Dependencies: None (Standard Library)\n")
    
    checker = BiasChecker()
    
    test_cases = [
        {"name": "Clearly clean", "input": "Women and men both participate in the marathon.", "expected_risk": 0.0},
        {"name": "Clearly flagged", "input": "Women are typically less interested in coding.", "expected_risk": 0.85},
        {"name": "Ambiguous/Borderline", "input": "Immigrants are usually the ones moving.", "expected_risk": 0.85},
        {"name": "Edge case (Empty)", "input": "   ", "expected_risk": 0.0},
        {"name": "Overlap case", "input": "I am not sure if asians are always good at math.", "expected_risk": 0.85}
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
