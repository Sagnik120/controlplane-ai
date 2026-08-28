import sys
import os
import asyncio

# Ensure src/ is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.adapters.mock_adapter import MockAdapter
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.orchestrator.pipeline import PipelineOrchestrator

def main():
    print("\n" + "="*50)
    print("ControlPlane.ai - Diagnostic Test: Spec 01")
    print("="*50)

    # 1. Initialize components
    print("\n=> Initializing Pipeline Components...")
    adapter = MockAdapter()
    risk_engine = RiskEngine()
    control_policy = ControlPolicy()
    audit_logger = AuditLogger()
    pipeline = PipelineOrchestrator(adapter, risk_engine, control_policy, audit_logger)

    # 2. Setup mock policy
    print("=> Setting up Mock Policy (latency sensitive)...")
    policy = UseCasePolicy(
        name="test_policy",
        max_overall_risk=0.8,
        checker_thresholds={"performance": 0.60},
        performance_n_samples=2,
        performance_sampling_temperature=1.0,
        performance_nli_weight=0.7,
        performance_bertscore_weight=0.3
    )

    # 3. Test Cases
    test_cases = [
        {
            "name": "Test 1: Safe Prompt (No Hallucination)",
            "prompt": "What color is the sky?"
        },
        {
            "name": "Test 2: Hallucination Prompt (High Inconsistency)",
            "prompt": "hallucination test: what is the capital of France?"
        }
    ]

    for i, tc in enumerate(test_cases):
        print(f"\n--- {tc['name']} ---")
        print(f"Prompt: '{tc['prompt']}'")
        
        # Execute pipeline
        result = pipeline.process_request(prompt=tc['prompt'], policy=policy)
        
        # Output extraction
        print(f"\nFinal Output: {result['final_output']}")
        print(f"Control Decision Action: {result['control_decision']['action']}")
        print(f"Control Decision Rationale: {result['control_decision']['rationale']}")
        
        # Find performance checker results
        perf_result = None
        for checker in result['risk_report']['checker_results']:
            if checker['checker_name'] == "performance":
                perf_result = checker
                break
                
        if perf_result:
            print(f"Performance Risk Score: {perf_result['risk_score']}")
            print(f"Flagged Span: {perf_result.get('flagged_span', 'None')}")
            print(f"Explanation: {perf_result['explanation']}")
            print("Sentence Scores (SelfCheckGPT Details):")
            for ss in perf_result.get('sentence_scores', []):
                print(f"  - [{ss['inconsistency_score']:.2f}] '{ss['sentence']}'")
        else:
            print("Performance Checker did not return a result!")

    print("\n" + "="*50)
    print("Diagnostic Complete!")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
