import sys
import os
import traceback
from typing import Iterator

# Ensure src/ is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.adapters.mock_adapter import MockAdapter
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.orchestrator.pipeline import PipelineOrchestrator
from src.checkers.performance_checker import PerformanceChecker

# ---------------------------------------------------------
# Custom Faulty Adapters for Edge Case Testing
# ---------------------------------------------------------
class EmptyResponseAdapter(MockAdapter):
    def generate_stream(self, prompt: str) -> Iterator[str]:
        yield ""
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        return ""

class ExceptionThrowingAdapter(MockAdapter):
    def generate_stream(self, prompt: str) -> Iterator[str]:
        raise RuntimeError("Simulated API Crash during stream!")
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        raise RuntimeError("Simulated API Crash during generation!")

# ---------------------------------------------------------
# Diagnostic Helpers
# ---------------------------------------------------------
def print_header(title):
    print("\n" + "="*70)
    print(f"🔬 {title}")
    print("="*70)

def extract_perf_result(result):
    for checker in result['risk_report']['checker_results']:
        if checker['checker_name'] == "performance":
            return checker
    return None

def run_test(pipeline, policy, prompt, expected_action, test_name):
    print(f"\n▶️ Running: {test_name}")
    print(f"  Prompt: '{prompt}'")
    
    try:
        result = pipeline.process_request(prompt=prompt, policy=policy)
        perf_result = extract_perf_result(result)
        
        print(f"  Final Action: {result['control_decision']['action']}")
        print(f"  Rationale: {result['control_decision']['rationale']}")
        
        if perf_result:
            print(f"  Perf Risk Score: {perf_result['risk_score']} (Threshold: {policy.checker_thresholds.get('performance', 1.0)})")
            if 'sentence_scores' in perf_result and perf_result['sentence_scores']:
                print("  Sentence Scores:")
                for ss in perf_result['sentence_scores']:
                    print(f"    - [{ss['inconsistency_score']:.2f}] {ss['sentence'][:50]}...")
        
        if result['control_decision']['action'] == expected_action:
            print(f"  ✅ PASS (Got expected action: {expected_action})")
        else:
            print(f"  ❌ FAIL (Expected {expected_action}, got {result['control_decision']['action']})")
            
    except Exception as e:
        print(f"  ❌ UNHANDLED FATAL EXCEPTION: {e}")
        traceback.print_exc()

# ---------------------------------------------------------
# Main Diagnostic Suite
# ---------------------------------------------------------
def main():
    print_header("ControlPlane.ai - Deep Diagnostic: Performance Pipeline")
    
    # 1. Base Setup
    risk_engine = RiskEngine()
    control_policy = ControlPolicy()
    audit_logger = AuditLogger()
    
    # Policy A: Strict latency & accuracy (e.g. Customer Support)
    policy_strict = UseCasePolicy(
        name="strict_policy",
        max_overall_risk=0.8,
        checker_thresholds={"performance": 0.50}, # Very strict
        performance_n_samples=3,
        performance_sampling_temperature=1.0,
        performance_nli_weight=0.7,
        performance_bertscore_weight=0.3
    )
    
    # Policy B: Lenient (e.g. Creative Brainstorming)
    policy_lenient = UseCasePolicy(
        name="lenient_policy",
        max_overall_risk=1.0,
        checker_thresholds={"performance": 1.0}, # Will tolerate hallucinations
        performance_n_samples=2,
        performance_sampling_temperature=1.0,
        performance_nli_weight=0.7,
        performance_bertscore_weight=0.3
    )

    standard_pipeline = PipelineOrchestrator(MockAdapter(), risk_engine, control_policy, audit_logger)
    empty_pipeline = PipelineOrchestrator(EmptyResponseAdapter(), risk_engine, control_policy, audit_logger)
    crashing_pipeline = PipelineOrchestrator(ExceptionThrowingAdapter(), risk_engine, control_policy, audit_logger)

    print_header("Phase 1: Happy Paths & Core Logic Validation")
    run_test(standard_pipeline, policy_strict, "What color is the sky?", "ALLOW", "Safe prompt, should ALLOW.")
    run_test(standard_pipeline, policy_strict, "hallucination test: what is the capital of France?", "BLOCK", "Hallucination prompt under Strict Policy, should BLOCK.")
    run_test(standard_pipeline, policy_lenient, "hallucination test: what is the capital of France?", "ALLOW", "Hallucination prompt under Lenient Policy (Threshold 0.95), should ALLOW.")

    print_header("Phase 2: Edge Cases & Graceful Degradation")
    run_test(empty_pipeline, policy_strict, "Tell me a story", "BLOCK", "Empty LLM Response - Pipeline should block/handle empty gracefully.")
    run_test(crashing_pipeline, policy_strict, "Tell me a story", "BLOCK", "Total Adapter API Crash - Pipeline's extreme fallback should BLOCK.")

    print_header("Phase 3: Module-Level Isolation Checks")
    print("\n▶️ Running: Missing Adapter/Prompt direct check in PerformanceChecker")
    perf_checker = next((c for c in risk_engine.checkers if c.name == "performance"), None)
    if perf_checker:
        res = perf_checker.evaluate("Some text", prompt="", adapter=None, policy=policy_strict)
        print(f"  Result without Adapter/Prompt: Risk {res.risk_score}, Expl: {res.explanation}")
        if res.risk_score == 0.0:
             print("  ✅ PASS (Checker bypassed elegantly when missing dependencies)")
        else:
             print("  ❌ FAIL (Checker did not bypass properly)")
    else:
        print("  ❌ FAIL (PerformanceChecker not found in RiskEngine)")

    print_header("Diagnostic Complete!")

if __name__ == "__main__":
    main()
