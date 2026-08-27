import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.cost.cost_monitor import CostMonitor

def run_diagnostic():
    print("--- Running Cost Monitor Diagnostic ---")
    print("Dependencies: None (Standard Library)\n")
    
    checker = CostMonitor()
    
    test_cases = [
        {"name": "Clearly clean (Short, standard, fast)", "input": "Hello", "time": 500, "tier": "standard", "expected_risk_less_than": 0.1},
        {"name": "Clearly flagged (Long, premium, slow)", "input": "A" * 8000, "time": 6000, "tier": "premium", "expected_risk_greater_than": 0.9},
        {"name": "Ambiguous/Borderline", "input": "A" * 4000, "time": 2000, "tier": "standard", "expected_risk_approx": 0.5},
        {"name": "Edge case (Empty)", "input": "", "time": 100, "tier": "standard", "expected_risk_approx": 0.0},
        {"name": "Overlap case", "input": "A" * 2000, "time": 5500, "tier": "standard", "expected_risk_approx": 0.35} # 500 tokens = 0.25 + 0.1 time penalty
    ]
    
    cases_run = 0
    cases_passed = 0
    
    for case in test_cases:
        cases_run += 1
        print(f"Scenario: {case['name']}")
        print(f"Input len: {len(case['input'])}, Time: {case['time']}ms, Tier: {case['tier']}")
        
        result = checker.evaluate(case['input'], case['time'], case['tier'])
        
        print(f"Actual Score: {result.risk_score:.2f} (Tokens: {result.tokens_estimated})")
        
        passed = False
        if "expected_risk_less_than" in case:
            passed = result.risk_score < case["expected_risk_less_than"]
        elif "expected_risk_greater_than" in case:
            passed = result.risk_score > case["expected_risk_greater_than"]
        else:
            passed = abs(result.risk_score - case["expected_risk_approx"]) < 0.05
            
        if passed:
            print("PASS\n")
            cases_passed += 1
        else:
            print("FAIL\n")
            
    print(f"--- Diagnostic Summary: {cases_passed}/{cases_run} PASSED ---")

if __name__ == "__main__":
    run_diagnostic()
