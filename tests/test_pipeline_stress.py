import sys
import os
import time
import json
from datetime import datetime

# Ensure src/ is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.adapters.mock_adapter import MockAdapter
from src.engine.risk_engine import RiskEngine
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy
from src.audit.audit_logger import AuditLogger
from src.orchestrator.pipeline import PipelineOrchestrator

def print_header(title):
    print("\n" + "="*80)
    print(f"🔥 {title}")
    print("="*80)

def main():
    print_header("Initializing Full Pipeline Stress Test (Adversarial & Edge Cases)")
    
    # 1. Setup minimal dependencies
    adapter = MockAdapter()
    risk_engine = RiskEngine()
    control_policy = ControlPolicy()
    
    # We use a temporary audit log for the stress test
    test_log_path = "data/stress_test_audit.jsonl"
    if os.path.exists(test_log_path):
        os.remove(test_log_path)
    audit_logger = AuditLogger(test_log_path)
    
    pipeline = PipelineOrchestrator(
        adapter=adapter,
        risk_engine=risk_engine,
        control_policy=control_policy,
        audit_logger=audit_logger
    )
    
    # Base Policy (with some missing or extreme values to test robustness)
    robust_policy = UseCasePolicy(
        name="stress_test",
        alpha_low=0.10,
        alpha_high=0.01,
        modify_span_threshold_pct=25.0,
        calibrated_thresholds={
            "pii": {"tau_low": 0.5, "tau_high": 0.9},
            # intentionally missing performance/safety/bias to see if fallbacks work
        }
    )

    # Missing thresholds completely
    broken_policy = UseCasePolicy(
        name="broken",
        calibrated_thresholds={}
    )

    test_cases = [
        {
            "name": "1. Massive Payload (10MB String)",
            "prompt": "GENERATE_MASSIVE_TEXT",
            "policy": robust_policy,
            "mock_response": "A" * 10_000_000, 
            "desc": "Testing if regex, NLP models, or memory limits crash on huge contiguous strings."
        },
        {
            "name": "2. Extreme Gibberish / Non-UTF8 / Emojis",
            "prompt": "GENERATE_EMOJIS",
            "policy": robust_policy,
            "mock_response": "🔥🔥🔥 👾 𐍈 𐍉 𐍊 𐍋 👨‍👩‍👧‍👦 \x00\x01\x02 \xff\xfe test phone 555-1234",
            "desc": "Testing how Presidio and HuggingFace NER handle surrogate pairs, null bytes, and emojis."
        },
        {
            "name": "3. Empty Response from LLM",
            "prompt": "GENERATE_EMPTY",
            "policy": robust_policy,
            "mock_response": "",
            "desc": "Does the pipeline crash if the LLM adapter returns an empty string or None?"
        },
        {
            "name": "4. Broken Policy (No Calibrated Thresholds)",
            "prompt": "Normal prompt",
            "policy": broken_policy,
            "mock_response": "The router issue was logged under ticket number 892-41-9921.",
            "desc": "Testing if control_policy safely falls back to defaults when tau_low/tau_high are missing."
        },
        {
            "name": "5. Exception in Adapter (Network Failure)",
            "prompt": "GENERATE_EXCEPTION",
            "policy": robust_policy,
            "mock_response": "EXCEPTION",
            "desc": "Testing the extreme edge-case handler in PipelineOrchestrator when generation completely fails."
        }
    ]

    passed = 0
    total = len(test_cases)
    
    for case in test_cases:
        print(f"\n▶️ Running: {case['name']}")
        print(f"  Description: {case['desc']}")
        
        # Monkeypatch the mock adapter for this specific test
        if case["mock_response"] == "EXCEPTION":
            def broken_generate(*args, **kwargs):
                raise ConnectionError("Mock Network Timeout!")
            adapter.generate_stream = broken_generate
        else:
            def static_generate(*args, **kwargs):
                yield case["mock_response"]
            adapter.generate_stream = static_generate
            
        start_time = time.time()
        
        try:
            result = pipeline.process_request(case["prompt"], case["policy"])
            
            elapsed = time.time() - start_time
            print(f"  Time taken    : {elapsed:.4f} seconds")
            print(f"  Action        : {result['control_decision']['action']}")
            print(f"  Reasoning     : {result['control_decision']['reasoning']}")
            
            if elapsed > 10.0 and case["name"].startswith("1."):
                print("  ⚠️ WARNING: Massive payload took > 10 seconds. Vulnerable to DoS attacks.")
                
            print("  ✅ SURVIVED without crashing.")
            passed += 1
            
        except Exception as e:
            print(f"  ❌ FATAL CRASH: Pipeline threw an unhandled exception!")
            print(f"     Exception: {str(e)}")
            import traceback
            traceback.print_exc()

    print_header(f"Stress Test Summary: {passed}/{total} Survived")
    if passed == total:
        print("🎉 The pipeline is extremely robust and handled all adversarial edge cases without crashing.")
    else:
        print("⚠️ SOME TESTS CRASHED. The pipeline has unhandled vulnerabilities.")

if __name__ == "__main__":
    main()
