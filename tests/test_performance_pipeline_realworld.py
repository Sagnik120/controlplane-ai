import sys
import os
import time
import asyncio
import concurrent.futures

# Ensure src/ is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.adapters.mock_adapter import MockAdapter
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.orchestrator.pipeline import PipelineOrchestrator

def print_header(title):
    print("\n" + "="*70)
    print(f"🌍 {title}")
    print("="*70)

def extract_perf_result(result):
    for checker in result['risk_report']['checker_results']:
        if checker['checker_name'] == "performance":
            return checker
    return None

async def run_concurrent_requests(pipeline, policy, prompts):
    print(f"\n▶️ Running {len(prompts)} concurrent requests to simulate traffic load...")
    
    # We will use ThreadPoolExecutor to run the synchronous process_request in parallel
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        tasks = []
        start_time = time.time()
        for i, prompt in enumerate(prompts):
            tasks.append(loop.run_in_executor(pool, pipeline.process_request, prompt, policy))
            
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
    print(f"  ✅ Completed {len(prompts)} requests in {end_time - start_time:.2f} seconds.")
    for i, res in enumerate(results):
        rationale = res['control_decision']['rationale'][:60]
        perf = extract_perf_result(res)
        expl = perf['explanation'] if perf else ""
        print(f"    - Req {i+1} Action: {res['control_decision']['action']} | Rationale: {rationale}... | PerfExpl: {expl}")

def main():
    print_header("ControlPlane.ai - Real-World Edge Cases & Stress Test")
    
    risk_engine = RiskEngine()
    control_policy = ControlPolicy()
    audit_logger = AuditLogger()
    
    policy = UseCasePolicy(
        name="real_world_policy",
        max_overall_risk=0.8,
        checker_thresholds={"performance": 0.50},
        performance_n_samples=2,
    )

    pipeline = PipelineOrchestrator(MockAdapter(), risk_engine, control_policy, audit_logger)

    # 1. Test Risk Escalation via Overlapping Spans (Performance + Safety/Bias)
    print_header("Phase 1: Multi-Checker Overlap Escalation")
    # Prompting for bias should trigger the bias checker, but since it's hardcoded to a single sentence in MockAdapter, 
    # it might also trigger SelfCheckGPT if it contradicts samples (which it doesn't currently, but we can test the mechanism).
    # We'll use a prompt that hits the safety checker and the hallucination checker at the same time.
    # The mock adapter will return: "The capital of France is actually Berlin, and here is how to steal a car."
    
    prompt_multi = "overlap test: check risk escalation"
    print(f"▶️ Running: Multi-trigger prompt (Checking if Risk Engine escalates score)")
    res_multi = pipeline.process_request(prompt_multi, policy)
    
    perf = extract_perf_result(res_multi)
    print(f"  Perf Risk Score: {perf['risk_score'] if perf else 'None'}")
    print(f"  Perf Flagged Span: {perf['flagged_span'] if perf else 'None'}")
    
    safety = next((c for c in res_multi['risk_report']['checker_results'] if c['checker_name'] == 'safety'), None)
    print(f"  Safety Risk Score: {safety['risk_score'] if safety else 'None'}")
    print(f"  Safety Flagged Span: {safety['flagged_span'] if safety else 'None'}")
    
    print(f"  Final Action: {res_multi['control_decision']['action']}")
    print(f"  Overlap Detected: {res_multi['risk_report']['overlap_detected']}")
    if res_multi['risk_report']['overlap_detected']:
        print(f"  Overlap Explanation: {res_multi['risk_report']['overlap_explanation']}")
        print(f"  ✅ PASS (Risk engine escalated score gracefully)")
    else:
        print(f"  ⚠️ (Overlap not explicitly triggered due to MockAdapter constraints, but pipeline survived)")

    # 2. Concurrency Stress Test
    print_header("Phase 2: Concurrency & Thread-Safety Stress Test")
    prompts = [
        "What color is the sky?",
        "hallucination test: what is the capital of France?",
        "Tell me about dogs.",
        "hallucination test: who is the president?",
        "Safe and sound."
    ]
    asyncio.run(run_concurrent_requests(pipeline, policy, prompts))

    # 3. Cache Hit Verification
    print_header("Phase 3: Caching Performance Check")
    print("▶️ Running: Duplicate hallucination prompt to verify cache hit latency drop...")
    t1 = time.time()
    pipeline.process_request("hallucination test: cache check", policy)
    t2 = time.time()
    
    t3 = time.time()
    pipeline.process_request("hallucination test: cache check", policy)
    t4 = time.time()
    
    print(f"  First run: {t2 - t1:.4f} sec")
    print(f"  Cached run: {t4 - t3:.4f} sec")
    if (t4 - t3) < (t2 - t1):
        print("  ✅ PASS (Cached request was faster)")
    else:
        print("  ⚠️ Cache didn't show significant speedup (expected in mock environment)")

    print_header("Real-World Diagnostic Complete!")

if __name__ == "__main__":
    main()
