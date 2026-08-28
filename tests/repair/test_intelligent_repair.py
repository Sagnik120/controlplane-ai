import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.orchestrator.pipeline import PipelineOrchestrator
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.checkers.base import CheckerResult
from src.adapters.base_adapter import BaseLLMAdapter

class MockAdapter(BaseLLMAdapter):
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        if "Flawed sentence to fix" in prompt:
            # Simulated micro-repair
            return "This is a safely repaired sentence."
        return "Here is a response. This is a very toxic and unsafe sentence. And here is a safe sentence."
        
    def generate_stream(self, prompt: str, temperature: float = 1.0):
        yield "Here is a response. This is a very toxic and unsafe sentence. And here is a safe sentence."

class MockRiskEngine(RiskEngine):
    def __init__(self):
        super().__init__()
        self.mock_results = []
        self.eval_count = 0
        
    def evaluate_response(self, response_text: str, **kwargs):
        self.eval_count += 1
        from src.engine.risk_engine import FinalRiskReport
        return FinalRiskReport(
            overall_risk_score=0.9 if self.mock_results else 0.0,
            is_blocked=False,
            checker_results=self.mock_results,
            overlap_detected=False
        )

def print_header(title):
    print("\n" + "="*80)
    print(f"🔬 {title}")
    print("="*80)

def main():
    print_header("Deep Integration Tests for SPEC 08 (Intelligent Repair)")
    
    adapter = MockAdapter()
    risk_engine = MockRiskEngine()
    policy_engine = ControlPolicy()
    logger = AuditLogger("data/test_repair_log.jsonl")
    
    orchestrator = PipelineOrchestrator(adapter, risk_engine, policy_engine, logger)
    
    # We create a strict policy where tau_low is very low, ensuring it hits MODIFY
    policy = UseCasePolicy(
        name="repair_policy",
        max_overall_risk=0.1,
        calibrated_thresholds={
            "safety": {"tau_low": 0.2, "tau_high": 0.99},
            "pii": {"tau_low": 0.2, "tau_high": 0.99}
        },
        modify_span_threshold_pct=50 # Allow up to 50% of the text to be spliced
    )

    total = 0
    passed = 0

    # -------------------------------------------------------------------------
    # Scenario 1: LLM Micro-Repair (Safety)
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 1: LLM Micro-Repair (Hallucination/Safety)")
    
    risk_engine.eval_count = 0
    risk_engine.mock_results = [
        CheckerResult(
            checker_name="safety", 
            risk_score=0.8, 
            explanation="Toxic sentence detected.", 
            entities=[{"text": "This is a very toxic and unsafe sentence."}]
        )
    ]
    
    # We must reset the mock results for the re-verify pass to succeed
    original_eval = risk_engine.evaluate_response
    def eval_override(response_text, **kwargs):
        risk_engine.eval_count += 1
        from src.engine.risk_engine import FinalRiskReport
        if risk_engine.eval_count == 1:
            # First pass: returns the risk
            return FinalRiskReport(overall_risk_score=0.8, is_blocked=False, checker_results=risk_engine.mock_results, overlap_detected=False)
        else:
            # Second pass (re-verify): returns clean
            return FinalRiskReport(overall_risk_score=0.0, is_blocked=False, checker_results=[], overlap_detected=False)
    
    risk_engine.evaluate_response = eval_override
    
    result = orchestrator.process_request("Write something", policy)
    
    if result["control_decision"]["action"] == "ALLOW" and "SILENT REPAIR SUCCESS" in result["control_decision"]["reasoning"]:
        if "This is a safely repaired sentence." in result["final_output"]:
            print(f"  ✅ PASS: Successfully sliced out toxic sentence and replaced with LLM repair.")
            passed += 1
        else:
            print(f"  ❌ FAIL: Action was ALLOW, but repaired text not found: {result['final_output']}")
    else:
        print(f"  ❌ FAIL: Expected ALLOW via SILENT REPAIR, got {result['control_decision']['action']}")

    # -------------------------------------------------------------------------
    # Scenario 2: Presidio PII Redaction
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 2: Presidio PII Redaction")
    
    risk_engine.eval_count = 0
    risk_engine.mock_results = [
        CheckerResult(
            checker_name="pii", 
            risk_score=0.8, 
            explanation="PII detected.", 
            entities=[{"text": "This is a very toxic and unsafe sentence.", "entity_type": "PHONE_NUMBER"}]
        )
    ]
    
    # Reset evaluator for this test
    def eval_override_pii(response_text, **kwargs):
        risk_engine.eval_count += 1
        from src.engine.risk_engine import FinalRiskReport
        if risk_engine.eval_count == 1:
            return FinalRiskReport(overall_risk_score=0.8, is_blocked=False, checker_results=risk_engine.mock_results, overlap_detected=False)
        else:
            return FinalRiskReport(overall_risk_score=0.0, is_blocked=False, checker_results=[], overlap_detected=False)
            
    risk_engine.evaluate_response = eval_override_pii
    
    result = orchestrator.process_request("Write something", policy)
    
    if result["control_decision"]["action"] == "ALLOW" and "SILENT REPAIR SUCCESS" in result["control_decision"]["reasoning"]:
        if "<PHONE_NUMBER>" in result["final_output"]:
            print(f"  ✅ PASS: Successfully routed PII through Presidio Anonymizer engine.")
            passed += 1
        else:
            print(f"  ❌ FAIL: Action was ALLOW, but <PHONE_NUMBER> not found: {result['final_output']}")
    else:
        print(f"  ❌ FAIL: Expected ALLOW via SILENT REPAIR, got {result['control_decision']['action']}")

    # -------------------------------------------------------------------------
    # Scenario 3: Repair Fails Re-verification (Escalate to REGENERATE)
    # -------------------------------------------------------------------------
    total += 1
    print("\n▶️ Scenario 3: Repair Fails Re-verification (Escalation to REGENERATE)")
    
    risk_engine.eval_count = 0
    risk_engine.mock_results = [
        CheckerResult(
            checker_name="safety", 
            risk_score=0.8, 
            explanation="Toxic sentence detected.", 
            entities=[{"text": "This is a very toxic and unsafe sentence."}]
        )
    ]
    
    # We simulate a failure in the re-verify pass (e.g. the LLM hallucinated again)
    def eval_override_fail(response_text, **kwargs):
        risk_engine.eval_count += 1
        from src.engine.risk_engine import FinalRiskReport
        # Always return risk, even on pass 2
        return FinalRiskReport(overall_risk_score=0.8, is_blocked=False, checker_results=risk_engine.mock_results, overlap_detected=False)
            
    risk_engine.evaluate_response = eval_override_fail
    
    result = orchestrator.process_request("Write something", policy)
    
    if result["control_decision"]["action"] == "REGENERATE" and "REPAIR FAILED RE-VERIFICATION" in result["control_decision"]["reasoning"]:
        print(f"  ✅ PASS: Successfully caught a failed repair and escalated to REGENERATE.")
        passed += 1
    else:
        print(f"  ❌ FAIL: Expected REGENERATE, got {result['control_decision']['action']} | {result['control_decision']['reasoning']}")

    print_header(f"Intelligent Edit Summary: {passed}/{total} Passed")

if __name__ == "__main__":
    main()
