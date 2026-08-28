import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.orchestrator.pipeline import PipelineOrchestrator
from src.engine.risk_engine import RiskEngine, FinalRiskReport
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.checkers.base import CheckerResult
from src.adapters.base_adapter import BaseLLMAdapter

class MatrixMockAdapter(BaseLLMAdapter):
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        return "Repaired text"
        
    def generate_stream(self, prompt: str, temperature: float = 1.0):
        yield "Initial text"

class MatrixRiskEngine(RiskEngine):
    def __init__(self):
        super().__init__()
        self.pass1_score = 0.0
        self.pass2_score = 0.0
        self.eval_count = 0
        
    def evaluate_response(self, response_text: str, **kwargs):
        self.eval_count += 1
        score = self.pass1_score if self.eval_count == 1 else self.pass2_score
        
        # If score is > 0, generate a mock span to trigger MODIFY
        results = []
        if score > 0:
            results.append(CheckerResult(
                checker_name="safety", 
                risk_score=score, 
                explanation="Matrix Test", 
                entities=[{"text": "Initial text"}] if self.eval_count == 1 else []
            ))
            
        return FinalRiskReport(
            overall_risk_score=score,
            is_blocked=False,
            checker_results=results,
            overlap_detected=False
        )

def print_header(title):
    print("\n" + "="*80)
    print(f"🧩 {title}")
    print("="*80)

def main():
    print_header("State Transition Matrix: Re-verification Safety")
    print("Testing every possible outcome of a Repair Re-verification pass to guarantee")
    print("no toxic text ever leaks through the PipelineOrchestrator.")
    
    adapter = MatrixMockAdapter()
    risk_engine = MatrixRiskEngine()
    policy_engine = ControlPolicy()
    logger = AuditLogger("data/matrix_log.jsonl")
    
    orchestrator = PipelineOrchestrator(adapter, risk_engine, policy_engine, logger)
    
    # Define thresholds
    # tau_low = 0.3 -> Below is ALLOW
    # tau_high = 0.8 -> Below is MODIFY
    # Above tau_high is HUMAN
    policy = UseCasePolicy(
        name="matrix_policy",
        max_overall_risk=0.1,
        calibrated_thresholds={
            "safety": {"tau_low": 0.3, "tau_high": 0.8},
        },
        modify_span_threshold_pct=101
    )

    # Matrix: (Pass 1 Risk, Pass 2 Risk, Expected Final Action)
    # Pass 1 is fixed at 0.5 (Triggers MODIFY)
    # Pass 2 tests every possible boundary condition
    matrix_tests = [
        # Pass 1 triggers MODIFY, Pass 2 is completely clean
        (0.5, 0.0, "ALLOW", "Clean repair"), 
        
        # Pass 1 triggers MODIFY, Pass 2 is slightly risky but below tau_low (0.3)
        (0.5, 0.25, "ALLOW", "Acceptable repair (under tau_low)"),
        
        # Pass 1 triggers MODIFY, Pass 2 is STILL exactly at tau_low -> triggers MODIFY again
        (0.5, 0.35, "REGENERATE", "Repair failed to drop below tau_low"),
        
        # Pass 1 triggers MODIFY, Pass 2 actually made it WORSE (0.7) -> triggers MODIFY again
        (0.5, 0.7, "REGENERATE", "Repair hallucinated worse text"),
        
        # Pass 1 triggers MODIFY, Pass 2 is horribly toxic (> tau_high 0.8) -> triggers HUMAN usually, but because it's a re-verify failure, it escalates to REGENERATE
        (0.5, 0.9, "REGENERATE", "Repair went completely rogue (extreme risk)")
    ]
    
    passed = 0
    total = len(matrix_tests)
    
    for pass1_score, pass2_score, expected_action, description in matrix_tests:
        print(f"\n▶️ Test: {description}")
        print(f"   Pass 1 Risk: {pass1_score} | Pass 2 Risk: {pass2_score}")
        
        # Reset state
        risk_engine.eval_count = 0
        risk_engine.pass1_score = pass1_score
        risk_engine.pass2_score = pass2_score
        
        res = orchestrator.process_request("Prompt", policy)
        actual_action = res["control_decision"]["action"]
        
        if actual_action == expected_action:
            print(f"  ✅ PASS: Pipeline safely routed to {expected_action}.")
            passed += 1
        else:
            print(f"  ❌ FAIL: Expected {expected_action}, but Pipeline leaked and output {actual_action}!")
            
    print_header(f"Matrix Safety Summary: {passed}/{total} Passed")

if __name__ == "__main__":
    main()
