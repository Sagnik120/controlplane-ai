import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.orchestrator.pipeline import PipelineOrchestrator
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.checkers.base import CheckerResult
from src.adapters.base_adapter import BaseLLMAdapter

class DeepMockAdapter(BaseLLMAdapter):
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        if "Flawed sentence to fix" in prompt:
            return "This is a surgically repaired, safe sentence."
        return "Initial mock response"
        
    def generate_stream(self, prompt: str, temperature: float = 1.0):
        yield "Initial mock response"

class DeepMockRiskEngine(RiskEngine):
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

    async def evaluate_response_async(self, response_text: str, **kwargs):
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
    print(f"🚀 {title}")
    print("="*80)

def main():
    print_header("ControlPlane-AI: Ultimate End-to-End Pipeline Verification")
    
    adapter = DeepMockAdapter()
    risk_engine = DeepMockRiskEngine()
    policy_engine = ControlPolicy()
    logger = AuditLogger("data/e2e_pipeline_log.jsonl")
    
    class MockCalibrator:
        def get_active_thresholds(self):
            return None # Force ControlPolicy to use policy.calibrated_thresholds
    
    policy_engine.calibrator = None
    orchestrator = PipelineOrchestrator(adapter, risk_engine, policy_engine, logger)
    
    # We create a comprehensive policy covering all bounds
    policy = UseCasePolicy(
        name="e2e_policy",
        max_overall_risk=0.1,
        calibrated_thresholds={
            "safety": {"tau_low": 0.3, "tau_high": 0.8},
            "pii": {"tau_low": 0.3, "tau_high": 0.8},
            "performance": {"tau_low": 0.3, "tau_high": 0.8}
        },
        modify_span_threshold_pct=101,
        session_drift_window_size=3,
        session_drift_threshold=0.5,
        session_require_monotonic_trend=True,
        session_cumulative_pii_threshold=2,
        session_escalation_action="HUMAN"
    )

    
    # Force the calibrator to return exactly what the policy defines
    from src.policy.adaptive_calibration import AdaptiveCalibrator
    calibrator = AdaptiveCalibrator()
    calibrator.get_active_thresholds = lambda use_case, dim: policy.calibrated_thresholds.get(dim, {})

    tests_passed = 0
    tests_total = 0

    # -------------------------------------------------------------------------
    # Test 1: Clean Request -> ALLOW
    # -------------------------------------------------------------------------
    tests_total += 1
    print("\n▶️ Case 1: Clean Request (Risk < tau_low)")
    risk_engine.mock_results = []
    res = orchestrator.process_request("What is 2+2?", policy)
    if res["control_decision"]["action"] == "ALLOW":
        print("  ✅ PASS: Request correctly allowed.")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: Expected ALLOW, got {res['control_decision']['action']}")

    # -------------------------------------------------------------------------
    # Test 2: Moderate Risk -> MODIFY (LLM Repair)
    # -------------------------------------------------------------------------
    tests_total += 1
    print("\n▶️ Case 2: Moderate Safety Risk -> MODIFY -> SILENT REPAIR")
    risk_engine.eval_count = 0
    risk_engine.mock_results = [
        CheckerResult(checker_name="safety", risk_score=0.5, explanation="Toxicity", entities=[{"text": "Initial mock response"}])
    ]
    async def eval_override_modify(response_text, **kwargs):
        risk_engine.eval_count += 1
        from src.engine.risk_engine import FinalRiskReport
        if risk_engine.eval_count == 1:
            return FinalRiskReport(overall_risk_score=0.5, is_blocked=False, checker_results=risk_engine.mock_results, overlap_detected=False)
        else: # Repair succeeds
            return FinalRiskReport(overall_risk_score=0.0, is_blocked=False, checker_results=[], overlap_detected=False)
            
    risk_engine.evaluate_response_async = eval_override_modify
    res = orchestrator.process_request("Tell me a toxic joke", policy)
    
    if res["control_decision"]["action"] == "ALLOW" and "surgically repaired" in res["final_output"]:
        print("  ✅ PASS: Successfully sliced out toxic text, repaired via LLM, and safely released.")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: Expected SILENT REPAIR to ALLOW, got {res['control_decision']['action']} | Reason: {res.get('risk_report', {}).get('checker_results', [{}])[0].get('explanation')}")

    # -------------------------------------------------------------------------
    # Test 3: Moderate PII Risk -> MODIFY (Presidio Anonymizer)
    # -------------------------------------------------------------------------
    tests_total += 1
    print("\n▶️ Case 3: Moderate PII Risk -> MODIFY -> PRESIDIO ANONYMIZATION")
    risk_engine.eval_count = 0
    risk_engine.mock_results = [
        CheckerResult(checker_name="pii", risk_score=0.5, explanation="PII", entities=[{"text": "Initial mock response", "entity_type": "SSN"}])
    ]
    async def eval_override_pii(response_text, **kwargs):
        risk_engine.eval_count += 1
        from src.engine.risk_engine import FinalRiskReport
        if risk_engine.eval_count == 1:
            return FinalRiskReport(overall_risk_score=0.5, is_blocked=False, checker_results=risk_engine.mock_results, overlap_detected=False)
        else:
            return FinalRiskReport(overall_risk_score=0.0, is_blocked=False, checker_results=[], overlap_detected=False)
            
    risk_engine.evaluate_response_async = eval_override_pii
    res = orchestrator.process_request("Here is my SSN", policy)
    
    if res["control_decision"]["action"] == "ALLOW" and "<SSN>" in res["final_output"]:
        print("  ✅ PASS: Successfully routed PII to deterministic AnonymizerEngine and released.")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: Expected SILENT REPAIR to ALLOW with <SSN>, got {res['final_output']} | Reason: {res['control_decision'].get('reasoning')}")

    # -------------------------------------------------------------------------
    # Test 4: Failed Repair -> REGENERATE
    # -------------------------------------------------------------------------
    tests_total += 1
    print("\n▶️ Case 4: Repair Fails Re-verification -> REGENERATE")
    risk_engine.eval_count = 0
    risk_engine.mock_results = [
        CheckerResult(checker_name="safety", risk_score=0.5, explanation="Toxicity", entities=[{"text": "Initial mock response"}])
    ]
    async def eval_override_fail(response_text, **kwargs):
        from src.engine.risk_engine import FinalRiskReport
        # Always return risk (simulate LLM failing to repair properly)
        return FinalRiskReport(overall_risk_score=0.5, is_blocked=False, checker_results=risk_engine.mock_results, overlap_detected=False)
            
    risk_engine.evaluate_response_async = eval_override_fail
    res = orchestrator.process_request("Toxic request", policy)
    
    if res["control_decision"]["action"] == "REGENERATE" and "REPAIR FAILED RE-VERIFICATION" in res["control_decision"]["reasoning"]:
        print("  ✅ PASS: Pipeline safely caught a failed repair and escalated to REGENERATE.")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: Expected REGENERATE, got {res['control_decision']['action']}")

    # -------------------------------------------------------------------------
    # Test 5: High Risk -> HUMAN Escalation (Conformal Bound Breached)
    # -------------------------------------------------------------------------
    tests_total += 1
    print("\n▶️ Case 5: High Risk (Risk >= tau_high) -> HUMAN ESCALATION")
    async def eval_override_human(response_text, **kwargs):
        from src.engine.risk_engine import FinalRiskReport
        return FinalRiskReport(
            overall_risk_score=0.9, 
            is_blocked=False, 
            checker_results=[CheckerResult(checker_name="safety", risk_score=0.9, explanation="Extreme Risk")], 
            overlap_detected=False
        )
    risk_engine.evaluate_response_async = eval_override_human
    res = orchestrator.process_request("Extreme toxic request", policy)
    
    if res["control_decision"]["action"] == "HUMAN" and "calibrated τ_high" in res["control_decision"]["reasoning"]:
        print("  ✅ PASS: Conformal bounds correctly triggered HUMAN escalation.")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: Expected HUMAN, got {res['control_decision']['action']}")

    # -------------------------------------------------------------------------
    # Test 6: Multi-Turn Session -> Cumulative PII Breached -> HUMAN
    # -------------------------------------------------------------------------
    tests_total += 1
    print("\n▶️ Case 6: Multi-Turn Session State -> Cumulative PII > 2 -> HUMAN")
    sid = "e2e_session_test"
    
    # Clean up evaluation override so we just inject PII
    async def eval_override_session(response_text, **kwargs):
        from src.engine.risk_engine import FinalRiskReport
        return FinalRiskReport(overall_risk_score=0.1, is_blocked=False, checker_results=risk_engine.mock_results, overlap_detected=False)
    risk_engine.evaluate_response_async = eval_override_session
    
    # Turn 1: PERSON
    risk_engine.mock_results = [CheckerResult(checker_name="pii", risk_score=0.1, explanation="low", entities=[{"entity_type": "PERSON", "text": "John"}])]
    res1 = orchestrator.process_request("Hello", policy, session_id=sid)
    
    # Turn 2: LOCATION (Threshold is 2 distinct types, so >= 2 triggers it)
    risk_engine.mock_results = [CheckerResult(checker_name="pii", risk_score=0.1, explanation="low", entities=[{"entity_type": "LOCATION", "text": "Paris"}])]
    res2 = orchestrator.process_request("Location", policy, session_id=sid)
    
    if res1["control_decision"]["action"] == "ALLOW" and res2["control_decision"]["action"] == "HUMAN" and "Cumulative PII" in res2["control_decision"]["reasoning"]:
        print("  ✅ PASS: Session permanently retained state and correctly escalated on slow-burn PII accumulation.")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: Session logic failed. T1: {res1['control_decision']['action']}, T2: {res2['control_decision']['action']}")

    print_header(f"End-to-End Pipeline Summary: {tests_passed}/{tests_total} Passed")

if __name__ == "__main__":
    main()
