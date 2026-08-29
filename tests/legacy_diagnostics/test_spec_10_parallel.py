import os
import sys
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.engine.risk_engine import RiskEngine
from src.checkers.base import CheckerResult, BaseChecker, Tier0Result
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy

class SlowMockChecker(BaseChecker):
    def __init__(self, name, sleep_time, fails=False):
        self.name = name
        self.sleep_time = sleep_time
        self.fails = fails
        
    def tier0_gate(self, window_text: str, context: dict) -> Tier0Result:
        return Tier0Result(needs_tier1=True)
        
    def tier1_check(self, window_text: str, context: dict) -> CheckerResult:
        time.sleep(self.sleep_time)
        if self.fails:
            raise RuntimeError(f"Mock crash in {self.name}")
        return CheckerResult(
            checker_name=self.name,
            risk_score=0.1,
            explanation=f"Took {self.sleep_time}s"
        )

def print_header(title):
    print("\n" + "="*80)
    print(f"🚀 {title}")
    print("="*80)

def main():
    print_header("SPEC 10: Parallel + Conditional Checkers Latency Test")
    
    # -------------------------------------------------------------------------
    # Test 1: Parallel Execution (Latency = Max, not Sum)
    # -------------------------------------------------------------------------
    print("\n▶️ Case 1: Testing Concurrency (Wall-clock time should be ~300ms, not 600ms)")
    
    checkers = [
        SlowMockChecker("performance", 0.1),
        SlowMockChecker("pii", 0.2),
        SlowMockChecker("safety", 0.3)
    ]
    
    engine = RiskEngine()
    engine.checkers = checkers
    
    start_time = time.time()
    report = engine.evaluate_response("Parallel test", policy=UseCasePolicy(name="test", max_overall_risk=0.5))
    end_time = time.time()
    
    elapsed_ms = (end_time - start_time) * 1000
    
    # It should be ~300ms. If it ran sequentially, it would be 100+200+300 = 600ms.
    # Allowing some overhead up to 400ms.
    if elapsed_ms < 450:
        print(f"  ✅ PASS: Parallel execution confirmed. Total time: {elapsed_ms:.2f}ms (Max was 300ms)")
    else:
        print(f"  ❌ FAIL: Execution took too long ({elapsed_ms:.2f}ms). Checkers are likely running sequentially.")
        
    # -------------------------------------------------------------------------
    # Test 2: Checker Exception Isolation
    # -------------------------------------------------------------------------
    print("\n▶️ Case 2: Checker Crash -> Isolated and Escalated (No Pipeline Crash)")
    
    checkers_crash = [
        SlowMockChecker("performance", 0.1),
        SlowMockChecker("pii", 0.1, fails=True), # This one crashes
        SlowMockChecker("safety", 0.1)
    ]
    engine.checkers = checkers_crash
    
    try:
        report_crash = engine.evaluate_response("Crash test", policy=UseCasePolicy(name="test", max_overall_risk=0.5))
        
        # We expect PII to return a CheckerResult with risk=1.0 and FATAL explanation
        pii_res = next((r for r in report_crash.checker_results if r.checker_name == "pii"), None)
        
        if pii_res and pii_res.risk_score == 1.0 and "FATAL" in pii_res.explanation:
            print("  ✅ PASS: Checker crash successfully isolated, converted to max risk, and returned to pipeline.")
        else:
            print("  ❌ FAIL: Crash was swallowed incorrectly.")
    except Exception as e:
        print(f"  ❌ FAIL: Pipeline crashed entirely because of a single checker failure: {e}")

    # -------------------------------------------------------------------------
    # Test 3: PII Tier-0 Gate (Regex Bypass)
    # -------------------------------------------------------------------------
    print("\n▶️ Case 3: PII Tier-0 Gate (Skipping NER)")
    try:
        from src.checkers.pii_checker import PiiChecker
        pii = PiiChecker()
        
        policy = UseCasePolicy(name="test", max_overall_risk=0.5, pii_tier0_mode="pattern_only_unless_hit")
        context = {"policy": policy}
        
        # Should skip
        gate_clean = pii.tier0_gate("This is a totally normal sentence with no numbers.", context)
        # Should trigger
        gate_dirty = pii.tier0_gate("My email is test@example.com", context)
        
        if not gate_clean.needs_tier1 and gate_dirty.needs_tier1:
            print("  ✅ PASS: PII Tier-0 regex cascade correctly gates expensive NER model.")
        else:
            print("  ❌ FAIL: PII Tier-0 did not properly route based on regex heuristics.")
    except ImportError:
        print("  ⚠️ SKIP: Presidio not installed or PiiChecker broken.")

    print_header("SPEC 10 Test Summary Completed")

if __name__ == "__main__":
    main()
