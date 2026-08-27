import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.checkers.performance_checker import PerformanceChecker

def run_diagnostic():
    print("--- Running Performance Checker Diagnostic ---")
    print("Dependencies: None (Standard Library)\n")
    
    checker = PerformanceChecker()
    
    test_cases = [
        {"name": "Clearly clean", "input": "The capital of France is Paris.", "expected_risk": 0.0},
        {"name": "Clearly flagged (Hedging)", "input": "I am not sure, but I think the capital is Paris.", "expected_risk": 0.7},
        {"name": "Ambiguous/Borderline", "input": "It seems like this could be correct.", "expected_risk": 0.7},
        {"name": "Edge case (Empty)", "input": "   ", "expected_risk": 1.0},
        {"name": "Overlap case (Contradiction)", "input": "The answer is 5, but the answer is never 5.", "expected_risk": 0.9}
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
