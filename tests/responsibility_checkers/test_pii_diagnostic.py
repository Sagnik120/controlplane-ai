import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.checkers.pii_checker import PiiChecker

def run_diagnostic():
    print("--- Running PII Checker Diagnostic ---")
    print("Dependencies: None (Standard Library)\n")
    
    checker = PiiChecker()
    
    test_cases = [
        {"name": "Clearly clean", "input": "Hello, my name is John.", "expected_risk": 0.0},
        {"name": "Clearly flagged (SSN)", "input": "My SSN is 123-45-6789.", "expected_risk": 0.9},
        {"name": "Ambiguous/Borderline", "input": "Contact me at 555-555-5555 if you need help.", "expected_risk": 0.9}, # Phone regex
        {"name": "Edge case (Empty)", "input": "   ", "expected_risk": 0.0},
        {"name": "Overlap case", "input": "I am not sure, but email john@example.com.", "expected_risk": 0.9} # Email regex
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
