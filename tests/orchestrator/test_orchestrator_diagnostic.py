import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.orchestrator.pipeline import PipelineOrchestrator
from src.adapters.mock_adapter import MockAdapter
from src.adapters.base_adapter import BaseLLMAdapter
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.checkers.performance_checker import PerformanceChecker
from src.checkers.safety_checker import SafetyChecker
from src.checkers.bias_checker import BiasChecker
from src.checkers.pii_checker import PiiChecker
from src.cost.cost_monitor import CostMonitor

class BrokenAdapter(BaseLLMAdapter):
    """A weird edge case adapter that simulates a catastrophic crash during generation."""
    def generate_stream(self, prompt: str):
        yield "I am going to "
        raise RuntimeError("CATASTROPHIC LLM SERVER CRASH")

def run_diagnostic():
    print("--- Running Full Orchestrator End-to-End Diagnostic ---")
    
    # 1. Initialize all dependencies
    adapter = MockAdapter()
    broken_adapter = BrokenAdapter()
    
    risk_engine = RiskEngine()
    
    control_policy = ControlPolicy()
    
    # Use a test log file to avoid dirtying the real one
    test_log_path = "data/orchestrator_diagnostic.jsonl"
    if os.path.exists(test_log_path):
        os.remove(test_log_path)
    audit_logger = AuditLogger(log_file=test_log_path)
    
    # 2. Initialize the Orchestrators
    orchestrator = PipelineOrchestrator(adapter, risk_engine, control_policy, audit_logger)
    broken_orchestrator = PipelineOrchestrator(broken_adapter, risk_engine, control_policy, audit_logger)
    
    # 3. Define Use Cases
    standard_policy = UseCasePolicy(name="standard", max_overall_risk=0.8, block_on_overlap=True)
    strict_pii_policy = UseCasePolicy(name="strict", max_overall_risk=0.8, checker_thresholds={"pii": 0.0}, redact_pii=True)
    
    test_cases = [
        {
            "name": "Scenario 1: End-to-End Clean Allow",
            "prompt": "clean",
            "policy": standard_policy,
            "orchestrator": orchestrator,
            "expected_snippet": "This is a clean, helpful"
        },
        {
            "name": "Scenario 2: End-to-End Safety Block",
            "prompt": "unsafe",
            "policy": standard_policy,
            "orchestrator": orchestrator,
            "expected_snippet": "[BLOCKED BY POLICY] BLOCKED: Overall risk score (0.95) exceeds global threshold"
        },
        {
            "name": "Scenario 3: End-to-End PII Redaction",
            "prompt": "pii",
            "policy": strict_pii_policy,
            "orchestrator": orchestrator,
            "expected_snippet": "[BLOCKED BY POLICY]" # Wait, PII is 1.0 in mock, threshold is 0.0. BLOCK overrides REDACT!
        },
        {
            "name": "Scenario 4: Weird Edge Case - Catastrophic Exception Handling",
            # The adapter will crash midway through generation. The orchestrator must not crash the app.
            # It should gracefully catch, log a synthetic block, and return a SYSTEM ERROR string.
            "prompt": "anything",
            "policy": standard_policy,
            "orchestrator": broken_orchestrator,
            "expected_snippet": "[SYSTEM ERROR] Unable to process request safely."
        }
    ]
    
    cases_passed = 0
    
    for case in test_cases:
        print(f"\n--- {case['name']} ---")
        print(f"Prompt: '{case['prompt']}'")
        
        response_dict = case['orchestrator'].process_request(case['prompt'], case['policy'])
        final_output = response_dict["final_output"]
        print(f"Final E2E Output: {final_output}")
        
        if case['expected_snippet'] in final_output:
            print("PASS")
            cases_passed += 1
        else:
            print(f"FAIL (Expected snippet '{case['expected_snippet']}' not found in output)")
            
    # Verify Audit Log recorded 4 entries (including the synthetic exception block)
    with open(test_log_path, "r") as f:
        log_lines = f.readlines()
        
    print(f"\nAudit Log Verify: {len(log_lines)} entries recorded.")
    if len(log_lines) == 4:
        print("Audit Log Integrity: PASS")
        cases_passed += 1
    else:
        print("Audit Log Integrity: FAIL")
        
    # Cleanup
    if os.path.exists(test_log_path):
        os.remove(test_log_path)
        
    print(f"\n--- Diagnostic Summary: {cases_passed}/5 PASSED ---")

if __name__ == "__main__":
    run_diagnostic()
