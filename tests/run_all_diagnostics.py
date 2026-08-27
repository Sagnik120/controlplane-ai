import subprocess
import sys

def main():
    print("========================================")
    print("      DEEP SYSTEM-LEVEL DIAGNOSTICS      ")
    print("========================================")
    
    scripts = [
        ("Adapters", "tests/adapters/test_adapters_diagnostic.py"),
        ("Performance Checker", "tests/performance_checker/test_performance_diagnostic.py"),
        ("Safety Checker", "tests/responsibility_checkers/test_safety_diagnostic.py"),
        ("Bias Checker", "tests/responsibility_checkers/test_bias_diagnostic.py"),
        ("PII Checker", "tests/responsibility_checkers/test_pii_diagnostic.py"),
        ("Cost Monitor", "tests/cost_monitor/test_cost_diagnostic.py"),
        ("Risk Engine", "tests/engine/test_risk_engine_diagnostic.py"),
        ("Policy Layer", "tests/policy/test_policy_diagnostic.py"),
    ]
    
    all_passed = True
    
    for name, script in scripts:
        print(f"\n>>> Running {name} Diagnostics...")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True)
        print(result.stdout)
        
        if result.returncode != 0 or "FAIL" in result.stdout:
            all_passed = False
            print(f"[!] {name} Diagnostics FAILED.")
        else:
            print(f"[*] {name} Diagnostics PASSED.")
            
    print("\n========================================")
    if all_passed:
        print("SYSTEM STATUS: STABLE")
    else:
        print("SYSTEM STATUS: NOT STABLE — DO NOT PROCEED TO NEXT PHASE")
        sys.exit(1)

if __name__ == "__main__":
    main()
