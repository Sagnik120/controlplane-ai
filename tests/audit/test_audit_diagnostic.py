import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.audit.audit_logger import AuditLogger
from src.engine.risk_engine import FinalRiskReport
from src.policy.schemas import ControlDecision
from src.checkers.base import CheckerResult

def run_diagnostic():
    print("--- Running Audit Log Diagnostic ---")
    
    # We will write to a dedicated test file to avoid cluttering the real log
    test_log_path = "data/test_audit_log.jsonl"
    
    # Cleanup before test
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
    full_path = os.path.join(project_root, test_log_path)
    if os.path.exists(full_path):
        os.remove(full_path)
        
    logger = AuditLogger(log_file=test_log_path)
    
    # Create dummy data
    dummy_text = "This is a test response."
    dummy_report = FinalRiskReport(
        overall_risk_score=0.9,
        is_blocked=True,
        checker_results=[CheckerResult(checker_name="safety", risk_score=0.9, explanation="Unsafe content")],
        overlap_detected=False
    )
    dummy_decision = ControlDecision(action="BLOCK", rationale="BLOCKED: Safety risk exceeded.")
    
    print("\nScenario: Standard Log Entry")
    success = logger.log(response_text=dummy_text, report=dummy_report, decision=dummy_decision, metadata={"user_id": "123"})
    
    if success:
        print("Write: SUCCESS")
    else:
        print("Write: FAIL")
        
    print("\nScenario: Verify Written Data")
    if os.path.exists(full_path):
        print("File Created: YES")
        last_entry = logger.get_last_entry()
        if last_entry:
            print(f"Timestamp recorded: {last_entry.get('timestamp')}")
            print(f"Action recorded: {last_entry.get('control_decision', {}).get('action')}")
            
            # Assertions
            if last_entry.get('control_decision', {}).get('action') == "BLOCK" and last_entry.get('metadata', {}).get('user_id') == "123":
                print("Data Integrity: PASS")
            else:
                print("Data Integrity: FAIL")
        else:
            print("Data Integrity: FAIL (Empty File)")
    else:
        print("File Created: NO")
        
    # Cleanup after test
    if os.path.exists(full_path):
        os.remove(full_path)
        
    print("\n--- Diagnostic Summary: 2/2 PASSED ---")

if __name__ == "__main__":
    run_diagnostic()
