import asyncio
import json
import os
import sys

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.agent.action_gate import ActionRiskChecker
from src.engine.semantic_overlap import SemanticOverlapDetector
from src.engine.embedding_registry import EmbeddingRegistry
from src.policy.schemas import ProposedAction, FinalRiskReport
from src.checkers.base import CheckerResult
from src.adapters.base_adapter import BaseLLMAdapter

class MockJudgeAdapter(BaseLLMAdapter):
    def generate_once(self, prompt: str) -> str:
        print("\n[MockJudgeAdapter] Received Prompt:")
        print("-" * 50)
        print(prompt)
        print("-" * 50)
        return json.dumps({"decision": "BLOCK", "rationale": "Blocked due to severe overlap mismatch with hallucinated amounts."})
        
    def generate_stream(self, prompt: str):
        yield ""

async def run_demos():
    print("Initializing components...")
    embedder = EmbeddingRegistry.get_embedder()
    overlap_detector = SemanticOverlapDetector(embedder=embedder)
    action_checker = ActionRiskChecker(overlap_detector=overlap_detector)
    adapter = MockJudgeAdapter()

    print("\n=======================================================")
    print("SCENARIO 1: Overlap-Driven Escalation (Refund Mismatch)")
    print("=======================================================")
    
    proposed_action = ProposedAction(
        name="update_record",
        arguments={"account_id": "cust_4471", "field": "refund_status", "value": {"amount": 340.00, "ref": "RF-88213"}}
    )
    
    # Simulate a FinalRiskReport from the RiskEngine where Performance Checker caught a hallucination
    report = FinalRiskReport(
        checker_results=[
            CheckerResult(
                checker_name="performance",
                risk_score=0.81,
                explanation="The refund amount $340.00 and reference RF-88213 are not supported by the retrieved context.",
            )
        ]
    )
    
    # Run the action gate
    decision1 = await action_checker.run(proposed_action, report, adapter)
    print(f"\n[Result 1] Decision: {decision1.action}")
    print(f"[Result 1] Reasoning: {decision1.reasoning}")


    print("\n=======================================================")
    print("SCENARIO 2: Catalog-Driven Escalation (Blast Radius)")
    print("=======================================================")
    
    proposed_action_bulk = ProposedAction(
        name="update_record_bulk",
        arguments={"status": "approved", "target": "all_pending_users"}
    )
    
    # A totally clean report, no flagged spans at all
    clean_report = FinalRiskReport(checker_results=[])
    
    decision2 = await action_checker.run(proposed_action_bulk, clean_report, adapter)
    print(f"\n[Result 2] Decision: {decision2.action}")
    print(f"[Result 2] Reasoning: {decision2.reasoning}")

if __name__ == "__main__":
    asyncio.run(run_demos())
