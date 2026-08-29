import pytest
import json
import asyncio
from unittest.mock import AsyncMock

from src.adapters.base_adapter import BaseLLMAdapter
from src.policy.schemas import ProposedAction, FinalRiskReport, UseCasePolicy
from src.checkers.base import CheckerResult
from src.agent.action_gate import ActionRiskChecker
from src.engine.semantic_overlap import SemanticOverlapDetector
from src.orchestrator.pipeline import PipelineOrchestrator
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.audit.audit_logger import AuditLogger

def make_mock_adapter(decision: str, rationale: str):
    mock_adapter = AsyncMock(spec=BaseLLMAdapter)
    # The ActionRiskChecker calls generate_once
    mock_adapter.generate_once.return_value = json.dumps({
        "decision": decision,      
        "rationale": rationale
    })
    # the pipeline might call generate_stream or other things
    # We provide a dummy generator for generate_stream so the pipeline doesn't crash if used
    async def dummy_gen(*args, **kwargs):
        yield "I processed your refund of $340."
    
    mock_adapter.generate_stream = dummy_gen
    
    # We must implement generate_stream synchronously if pipeline expects it synchronously
    def sync_dummy_gen(*args, **kwargs):
        yield "I processed your refund of $340."
    mock_adapter.generate_stream = sync_dummy_gen
        
    return mock_adapter

# Dummy embedder for the overlap detector
class MockEmbedder:
    def encode(self, texts, **kwargs):
        import numpy as np
        # Return dummy embeddings (all 1s) to force a cosine match when texts exist
        return np.ones((len(texts), 384))

@pytest.fixture
def action_gate():
    overlap_detector = SemanticOverlapDetector(embedder=MockEmbedder())
    return ActionRiskChecker(
        catalog_path="src/agent/action_catalog.yaml", 
        overlap_detector=overlap_detector
    )

@pytest.mark.anyio
async def test_catalog_only_escalation(action_gate):
    # update_record_bulk -> many_entities -> tier 0 flags it automatically
    proposed_action = ProposedAction(name="update_record_bulk", arguments={})
    report = FinalRiskReport(checker_results=[])
    
    # Should flag at tier0 without any overlap
    t0_res = action_gate.tier0_gate(proposed_action, report)
    assert t0_res.needs_tier1 is True
    assert "many_entities" in t0_res.trigger_reason
    
    mock_adapter = make_mock_adapter("HOLD", "Bulk updates require confirmation.")
    decision = await action_gate.tier1_check(proposed_action, report, mock_adapter, t0_res)
    assert decision.action == "HOLD"

@pytest.mark.anyio
async def test_overlap_driven_escalation(action_gate):
    # refund scenario -> update_record with overlap
    proposed_action = ProposedAction(
        name="update_record", 
        arguments={"amount": 340.00, "ref": "RF-88213"}
    )
    
    # Context has a flagged hallucination from performance checker
    report = FinalRiskReport(checker_results=[
        CheckerResult(
            checker_name="performance", 
            risk_score=0.8, 
            explanation="Hallucinated refund amount $340.00"
        )
    ])
    
    t0_res = action_gate.tier0_gate(proposed_action, report)
    assert t0_res.needs_tier1 is True
    assert "semantically overlap" in t0_res.trigger_reason
    
    mock_adapter = make_mock_adapter("BLOCK", "Hallucinated argument detected.")
    decision = await action_gate.tier1_check(proposed_action, report, mock_adapter, t0_res)
    assert decision.action == "BLOCK"

def test_pipeline_decision_separation(tmp_path):
    # Full pipeline test
    mock_adapter = make_mock_adapter("BLOCK", "Blocked by tool monitor.")
    
    class DummyRiskEngine:
        def evaluate_response(self, text, *args, **kwargs):
            return FinalRiskReport(
                overall_risk_score=0.8,
                checker_results=[
                    CheckerResult(checker_name="performance", risk_score=0.8, explanation="$340.00 not found")
                ]
            )
            
    class DummyControlPolicy:
        def __init__(self):
            self.evals = 0
        def evaluate(self, report, *args, **kwargs):
            self.evals += 1
            from src.policy.schemas import ControlDecision
            if self.evals == 1:
                return ControlDecision(action="REGENERATE", reasoning="Regenerating text", clean_prefix="Sorry", failed_span="$340")
            else:
                return ControlDecision(action="ALLOW", reasoning="Text is now clean")
            
    class DummyCheckpointMgr:
        def commit(self, *args, **kwargs): pass
        
    class DummyRegenEngine:
        def regenerate(self, *args, **kwargs): return "Let me check that for you."

    # Using standard classes except for our mocks
    pipeline = PipelineOrchestrator(
        adapter=mock_adapter,
        risk_engine=DummyRiskEngine(),
        control_policy=DummyControlPolicy(),
        audit_logger=AuditLogger(log_file=str(tmp_path / "audit.jsonl"))
    )
    
    # Override checkpoint/regen with dummies
    pipeline.checkpoint_mgr = DummyCheckpointMgr()
    pipeline.regeneration_engine = DummyRegenEngine()
    
    # Also override ActionRiskChecker's embedder so it triggers overlap
    pipeline.action_checker.overlap_detector.embedder = MockEmbedder()
    
    policy = UseCasePolicy(name="customer_facing_chat")
    
    request_context = {
        "proposed_action": {
            "name": "update_record",
            "arguments": {"amount": 340.00}
        }
    }
    
    result = pipeline.process_request("Refund my $340", policy, request_context=request_context)
    
    # Decision separation!
    assert result["control_decision"]["action"] == "ALLOW" # It regenerated successfully and allowed the new text
    assert "action_decision" in result
    assert result["action_decision"]["action"] == "BLOCK" # The action was strictly blocked
    assert result["action_decision"]["reasoning"] == "Blocked by tool monitor."
