import pytest
import asyncio
import time
from src.orchestrator.pipeline import PipelineOrchestrator
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.policy.control_policy import ControlPolicy
from src.engine.risk_engine import RiskEngine
from src.checkers.base import CheckerResult
from src.adapters.base_adapter import BaseLLMAdapter

class DelayMockAdapter(BaseLLMAdapter):
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        return "Async response"
        
    def generate_stream(self, prompt: str, temperature: float = 1.0):
        yield "Async response"

class DelayMockRiskEngine(RiskEngine):
    async def evaluate_response_async(self, response_text: str, **kwargs):
        # Simulate network delay to prove concurrency
        await asyncio.sleep(0.5)
        from src.engine.risk_engine import FinalRiskReport
        return FinalRiskReport(
            overall_risk_score=0.1,
            is_blocked=False,
            checker_results=[],
            overlap_detected=False
        )
        
    def evaluate_response(self, response_text: str, **kwargs):
        raise NotImplementedError("Sync evaluate_response should not be called in async pipeline")

def test_async_pipeline_concurrency():
    """
    Test that the async pipeline orchestrator properly handles multiple concurrent requests
    and doesn't block the event loop.
    """
    adapter = DelayMockAdapter()
    risk_engine = DelayMockRiskEngine()
    policy_engine = ControlPolicy()
    
    # Mock calibrator to bypass ACI
    class MockCalibrator:
        def get_active_thresholds(self, use_case, dim):
            return {"tau_low": 0.3, "tau_high": 0.8}
    policy_engine.calibrator = MockCalibrator()
    
    logger = AuditLogger("data/async_test.jsonl")
    
    orchestrator = PipelineOrchestrator(
        adapter=adapter,
        risk_engine=risk_engine,
        control_policy=policy_engine,
        audit_logger=logger
    )
    
    policy = UseCasePolicy(
        name="test_policy",
        max_overall_risk=0.2,
        calibrated_thresholds={"safety": {"tau_low": 0.3, "tau_high": 0.8}}
    )
    
    start_time = time.time()
    
    async def run_concurrent():
        # Run 5 concurrent requests
        tasks = [
            orchestrator.process_request_async(f"Prompt {i}", policy)
            for i in range(5)
        ]
        return await asyncio.gather(*tasks)
    
    results = asyncio.run(run_concurrent())
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    assert len(results) == 5
    for res in results:
        assert res["control_decision"]["action"] == "ALLOW"
        
    # If it was synchronous, it would take 5 * 0.5 = 2.5 seconds
    # With async concurrency, it should take just slightly over 0.5 seconds
    assert elapsed < 1.5, f"Concurrency test failed: took {elapsed}s, expected < 1.5s"

def test_sync_wrapper_equivalence():
    """
    Ensure the synchronous wrapper process_request still functions exactly as expected
    without throwing event loop errors.
    """
    adapter = DelayMockAdapter()
    risk_engine = DelayMockRiskEngine()
    policy_engine = ControlPolicy()
    
    class MockCalibrator:
        def get_active_thresholds(self, use_case, dim):
            return {"tau_low": 0.3, "tau_high": 0.8}
    policy_engine.calibrator = MockCalibrator()
    logger = AuditLogger("data/async_test.jsonl")
    
    orchestrator = PipelineOrchestrator(
        adapter=adapter,
        risk_engine=risk_engine,
        control_policy=policy_engine,
        audit_logger=logger
    )
    
    policy = UseCasePolicy(
        name="test_policy",
        max_overall_risk=0.2,
        calibrated_thresholds={"safety": {"tau_low": 0.3, "tau_high": 0.8}}
    )
    
    res = orchestrator.process_request("Sync Prompt", policy)
    assert res["control_decision"]["action"] == "ALLOW"
