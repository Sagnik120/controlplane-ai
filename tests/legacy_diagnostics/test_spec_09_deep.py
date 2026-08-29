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

class DeepRegenAdapter(BaseLLMAdapter):
    def __init__(self):
        self.next_resample = " Safely regenerated suffix."
        
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        prompt_lower = prompt.lower()
        if "generate 2-4 short, independent, checkable" in prompt_lower:
            return "Diagnosed question 1?\nDiagnosed question 2?"
        if "answer the following question" in prompt_lower:
            return "Verified answer 1.\nVerified answer 2."
        if "continue the response below" in prompt_lower:
            return self.next_resample
        return "Initial bad response."
        
    def generate_stream(self, prompt: str, temperature: float = 1.0):
        yield "Prefix looks good... "
        yield "Wait, here is a massive hallucination about Paris being in Germany."

class DeepRegenRiskEngine(RiskEngine):
    def __init__(self):
        super().__init__()
        self.eval_count = 0
        self.force_fail_count = 0
        
    def evaluate_response(self, response_text: str, **kwargs):
        self.eval_count += 1
        from src.engine.risk_engine import FinalRiskReport
        
        # Check if this is a verification of the regenerated text
        is_regenerated = "Safely regenerated" in response_text or "Bad regenerated" in response_text
        
        if is_regenerated:
            if self.force_fail_count > 0:
                self.force_fail_count -= 1
                return FinalRiskReport(
                    overall_risk_score=0.6,
                    is_blocked=False,
                    checker_results=[CheckerResult(checker_name="performance", risk_score=0.6, explanation="Still bad", entities=[{"text": response_text}])],
                    overlap_detected=False
                )
            else:
                return FinalRiskReport(
                    overall_risk_score=0.1,
                    is_blocked=False,
                    checker_results=[],
                    overlap_detected=False
                )
        else:
            # Initial run, fail it to trigger REGENERATE
            # The flagged span must be large enough to trigger REGENERATE over MODIFY.
            return FinalRiskReport(
                overall_risk_score=0.6,
                is_blocked=False,
                checker_results=[
                    CheckerResult(
                        checker_name="performance", 
                        risk_score=0.6, 
                        explanation="Hallucination", 
                        entities=[{"text": "Wait, here is a massive hallucination about Paris being in Germany."}]
                    )
                ],
                overlap_detected=False
            )

def print_header(title):
    print("\n" + "="*80)
    print(f"🚀 {title}")
    print("="*80)

def main():
    print_header("SPEC 09 (CBR): Deep Real-World Regeneration Pipeline Tests")
    
    adapter = DeepRegenAdapter()
    risk_engine = DeepRegenRiskEngine()
    policy_engine = ControlPolicy()
    
    # We will log to dev/null equivalent for testing
    if not os.path.exists("data"):
        os.makedirs("data")
    logger = AuditLogger("data/test_cbr_deep.jsonl")
    
    orchestrator = PipelineOrchestrator(adapter, risk_engine, policy_engine, logger)
    
    # Policy designed to easily trigger REGENERATE. 
    # tau_low = 0.3, tau_high = 0.8
    # modify_span_threshold_pct = 50% (if flawed text is > 50% of total text, it triggers REGENERATE)
    policy = UseCasePolicy(
        name="cbr_policy",
        max_overall_risk=0.1,
        calibrated_thresholds={
            "performance": {"tau_low": 0.3, "tau_high": 0.8}
        },
        modify_span_threshold_pct=50,
        max_regenerate_attempts=2
    )

    tests_passed = 0
    tests_total = 0

    # -------------------------------------------------------------------------
    # Test 1: Regeneration Succeeds on 1st Attempt
    # -------------------------------------------------------------------------
    tests_total += 1
    print("\n▶️ Case 1: Hallucination Detected -> REGENERATE -> Fixes on 1st attempt")
    risk_engine.eval_count = 0
    risk_engine.force_fail_count = 0
    adapter.next_resample = " Safely regenerated suffix."
    
    res = orchestrator.process_request("Tell me about Paris.", policy)
    
    # The final output should be the clean prefix + the safe resample
    expected_output = "Prefix looks good...  Safely regenerated suffix."
    if res["control_decision"]["action"] == "ALLOW" and res["final_output"] == expected_output:
        print("  ✅ PASS: Successfully backtracked, regenerated, verified, and spliced!")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: Expected ALLOW with spliced text, got {res['control_decision']['action']} - Output: {res['final_output']}")

    # -------------------------------------------------------------------------
    # Test 2: Regeneration Fails once, succeeds on 2nd Attempt
    # -------------------------------------------------------------------------
    tests_total += 1
    print("\n▶️ Case 2: Hallucination Detected -> REGENERATE -> Fails 1st verify -> Succeeds 2nd verify")
    risk_engine.eval_count = 0
    risk_engine.force_fail_count = 1  # Force the FIRST verification to fail
    adapter.next_resample = " Safely regenerated suffix."
    
    res = orchestrator.process_request("Tell me about Paris.", policy)
    
    if res["control_decision"]["action"] == "ALLOW" and res["final_output"] == expected_output:
        print("  ✅ PASS: Successfully looped through regeneration twice before allowing!")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: Expected ALLOW after retry, got {res['control_decision']['action']}")

    # -------------------------------------------------------------------------
    # Test 3: Regeneration exhausts max_regenerate_attempts -> HUMAN Escalation
    # -------------------------------------------------------------------------
    tests_total += 1
    print("\n▶️ Case 3: Hallucination Detected -> REGENERATE -> Exhausts all retries (2) -> HUMAN")
    risk_engine.eval_count = 0
    risk_engine.force_fail_count = 5  # Force all verifications to fail
    adapter.next_resample = " Bad regenerated suffix."
    
    res = orchestrator.process_request("Tell me about Paris.", policy)
    
    if res["control_decision"]["action"] == "HUMAN":
        print("  ✅ PASS: Regeneration hit max retries and safely escalated to HUMAN!")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: Expected HUMAN, got {res['control_decision']['action']}")

    print_header(f"Deep Regeneration Pipeline Summary: {tests_passed}/{tests_total} Passed")

if __name__ == "__main__":
    main()
