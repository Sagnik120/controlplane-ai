import os
import sys
import subprocess
import glob

def run_deep_diagnostics():
    print("================================================================================")
    print("🚀 ControlPlane-AI: Master Deep Diagnostic Runner")
    print("================================================================================\n")
    print("Scanning for diagnostic scripts...\n")
    
    start_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Find all test scripts in the tests directory and its immediate subdirectories
    test_scripts = []
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                # Exclude this master script itself if it matched
                if file != "test_deep_diagnostic_master.py":
                    test_scripts.append(os.path.join(root, file))
                    
    total_scripts = len(test_scripts)
    scripts_passed = 0
    scripts_failed = 0
    
    print(f"Found {total_scripts} master diagnostic test suites. Executing...\n")
    
    for script_path in sorted(test_scripts):
        rel_path = os.path.relpath(script_path, os.getcwd())
        print(f"--- Running {rel_path} ---")
        
        try:
            # We run python -m unittest for scripts that might use unittest, 
            # but since some are custom scripts, running them directly as python scripts works for both 
            # (unittest.main() handles it if it's a unittest script).
            result = subprocess.run([sys.executable, script_path], capture_output=True, text=True, timeout=60)
            
            output = result.stdout + "\n" + result.stderr
            
            # Print the output indented
            for line in output.split('\n'):
                if line.strip():
                    print(f"    {line}")
                    
            if result.returncode == 0 and "FAIL:" not in output and "❌ FAIL" not in output:
                print(f"✅ {rel_path} PASSED\n")
                scripts_passed += 1
            else:
                print(f"❌ {rel_path} FAILED\n")
                scripts_failed += 1
                
        except subprocess.TimeoutExpired:
            print(f"❌ {rel_path} TIMED OUT\n")
            scripts_failed += 1
        except Exception as e:
            print(f"❌ {rel_path} ERRORED: {str(e)}\n")
            scripts_failed += 1

    print("================================================================================")
    print("📊 Master Diagnostic Summary")
    print("================================================================================")
    print(f"Total Test Suites Run: {total_scripts}")
    print(f"Suites Passed: {scripts_passed}")
    print(f"Suites Failed: {scripts_failed}")
    
    if scripts_failed == 0 and total_scripts > 0:
        print("\n✅ SYSTEM HEALTH: PERFECT. All modules, integrations, and edge cases passed.")
        sys.exit(0)
    else:
        print("\n❌ SYSTEM HEALTH: CRITICAL. Failures detected in the diagnostic run.")
        sys.exit(1)

if __name__ == '__main__':
    run_deep_diagnostics()
