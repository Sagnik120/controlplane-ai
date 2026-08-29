import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.policy.control_policy import ControlPolicy
from src.engine.risk_engine import FinalRiskReport
from src.checkers.base import CheckerResult
from src.policy.schemas import UseCasePolicy

def main():
    print("Isolating ALLOW bug...")
    policy_engine = ControlPolicy()
    
    # Same policy as in e2e test
    policy = UseCasePolicy(
        name="e2e_policy",
        max_overall_risk=0.1,
        calibrated_thresholds={
            "safety": {"tau_low": 0.3, "tau_high": 0.8},
            "pii": {"tau_low": 0.3, "tau_high": 0.8},
            "performance": {"tau_low": 0.3, "tau_high": 0.8}
        },
        modify_span_threshold_pct=101
    )
    
    # Create a dummy risk report like Case 2
    mock_results = [
        CheckerResult(checker_name="safety", risk_score=0.5, explanation="Toxicity")
    ]
    report = FinalRiskReport(overall_risk_score=0.5, is_blocked=False, checker_results=mock_results, overlap_detected=False)
    
    decision = policy_engine.evaluate(report, policy)
    print("Decision Action:", decision.action)
    print("Decision Reason:", decision.reasoning)
    print("Calibration Meta:", decision.calibration_metadata)
    
if __name__ == "__main__":
    main()
