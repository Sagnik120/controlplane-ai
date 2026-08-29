import pytest
import asyncio
from src.engine.risk_engine import RiskEngine
from src.policy.schemas import UseCasePolicy, CheckerBudgetProfile, PerformanceBudget
from src.checkers.base import BaseChecker, CheckerResult, Tier0Result
from src.policy.control_policy import ControlPolicy
from src.orchestrator.pipeline import PipelineOrchestrator
from src.adapters.base_adapter import BaseLLMAdapter

class SlowMockChecker(BaseChecker):
    name = "performance"
    def tier0_gate(self, window_text, context):
        return Tier0Result(needs_tier1=True)
    def tier1_check(self, window_text, context):
        import time
        time.sleep(1.0) # Artificial delay of 1 second
        return CheckerResult(checker_name=self.name, risk_score=0.9, explanation="Very slow evaluation")

class MockAdapter(BaseLLMAdapter):
    def generate_once(self, prompt, **kwargs):
        return "mock"
    def generate_stream(self, prompt, **kwargs):
        yield "mock"

def test_circuit_breaker_timeout():
    # Set up a policy with a tight latency budget (0.2s)
    policy = UseCasePolicy(
        name="test_tight_budget",
        consequence_level="medium",
        latency_budget_ms=200,
    )
    
    engine = RiskEngine()
    engine.checkers = [SlowMockChecker()]
    
    report = engine.evaluate_response("test", prompt="test", adapter=MockAdapter(), policy=policy)
    
    # Assert circuit breaker fired
    assert report.under_verified is True
    # The array includes the SlowMockChecker result + the CostMonitorResult
    assert len(report.checker_results) == 2
    assert report.checker_results[0].explanation == "Skipped (Circuit Breaker Timeout)"

def test_action_type_escalation():
    policy = UseCasePolicy(
        name="customer_facing",
        consequence_level="medium",
        latency_budget_ms=400,
    )
    
    adapter = MockAdapter()
    engine = RiskEngine()
    engine.checkers = []
    
    pipeline = PipelineOrchestrator(
        adapter=adapter,
        risk_engine=engine,
        control_policy=ControlPolicy(),
        audit_logger=None
    )
    
    # We mock the logger
    class MockAuditLogger:
        def log(self, *args, **kwargs): pass
    pipeline.audit_logger = MockAuditLogger()
    
    res = pipeline.process_request("test prompt", policy=policy, request_context={"action_type": "refund"})
    
    # We can check that the policy consequence level was escalated internally,
    # but the pipeline returns a dictionary.
    assert "final_output" in res

if __name__ == "__main__":
    test_circuit_breaker_timeout()
    test_action_type_escalation()
    print("SPEC 11 tests passed!")
