import unittest
from src.adapters.mock_adapter import MockAdapter
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.orchestrator.pipeline import PipelineOrchestrator
from src.checkers.base import CheckerResult

class MockRegeneratingAdapter(MockAdapter):
    """
    Mocks the LLM adapter to simulate:
    1. Initial generation that returns a long string with a clear failure point.
    2. A regeneration attempt that succeeds.
    """
    def __init__(self):
        self.call_count = 0
        
    def generate_stream(self, prompt: str, temperature: float = 1.0):
        # We simulate a 3-sentence response. The third sentence will be flagged.
        yield "Sentence 1 is perfectly safe and clean. "
        yield "Sentence 2 is also verified and fine. "
        yield "Sentence 3 contains dangerous hallucinated instructions."
        
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        self.call_count += 1
        # The CBR prompt will pass the clean prefix and ask for a continuation.
        # We just return a safe continuation.
        if "Sentence 1" in prompt and "Sentence 3 contains" in prompt:
            return "Sentence 3 is now a safe and verified conclusion."
        return "Fallback safe text."


class MockCBRRiskEngine(RiskEngine):
    def __init__(self):
        self.eval_count = 0
        
    def evaluate_response(self, response_text: str, **kwargs):
        self.eval_count += 1
        
        # Pass 1: Flag the bad sentence
        if self.eval_count == 1:
            from src.engine.risk_engine import FinalRiskReport
            return FinalRiskReport(
                overall_risk_score=0.9,
                is_blocked=False,
                overlap_detected=False,
                checker_results=[CheckerResult(
                    checker_name="safety", 
                    risk_score=0.9, 
                    explanation="Hallucinated instructions detected.",
                    entities=[{"text": "Sentence 3 contains dangerous hallucinated instructions."}]
                )]
            )
        # Pass 2: Re-verify of the regenerated text
        else:
            from src.engine.risk_engine import FinalRiskReport
            return FinalRiskReport(
                overall_risk_score=0.0,
                is_blocked=False,
                overlap_detected=False,
                checker_results=[]
            )

class TestSpec09CBR(unittest.TestCase):
    def setUp(self):
        self.adapter = MockRegeneratingAdapter()
        self.risk_engine = MockCBRRiskEngine()
        self.control_policy = ControlPolicy()
        self.audit_logger = AuditLogger("data/test_cbr_log.jsonl")
        self.orchestrator = PipelineOrchestrator(
            self.adapter, self.risk_engine, self.control_policy, self.audit_logger
        )
        
        # We need a policy where tau_low is exceeded, and the span is > modify threshold OR it just escalates.
        # We'll set modify_span_threshold_pct to 10% so that the span (which is ~33% of the text) triggers REGENERATE immediately.
        self.policy = UseCasePolicy(
            name="cbr_test_policy",
            max_overall_risk=0.1,
            calibrated_thresholds={
                "safety": {"tau_low": 0.3, "tau_high": 0.95}, # high enough so it doesn't instantly HUMAN
            },
            modify_span_threshold_pct=10.0 # Force REGENERATE
        )

    def test_checkpoint_backtrack_regeneration(self):
        res = self.orchestrator.process_request("Test CBR", self.policy)
        
        # The expected final text should contain the original prefix + the regenerated tail
        expected_prefix = "Sentence 1 is perfectly safe and clean. Sentence 2 is also verified and fine. "
        expected_tail = "Sentence 3 is now a safe and verified conclusion."
        
        self.assertEqual(res["control_decision"]["action"], "ALLOW")
        self.assertTrue(expected_prefix in res["final_output"], "Clean prefix was not preserved!")
        self.assertTrue(expected_tail in res["final_output"], "Regenerated tail was not appended!")
        self.assertFalse("Sentence 3 contains dangerous" in res["final_output"], "The dangerous sentence leaked!")
        self.assertEqual(self.adapter.call_count, 1, "Should have attempted regeneration exactly once.")

if __name__ == '__main__':
    unittest.main()
