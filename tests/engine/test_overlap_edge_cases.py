import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.engine.risk_engine import RiskEngine
from src.checkers.base import CheckerResult

class MockCostMonitor:
    def evaluate(self, *args, **kwargs):
        from src.cost.cost_monitor import CostMonitorResult
        return CostMonitorResult(
            risk_score=0.0,
            explanation="Mock cost",
            tokens_estimated=0,
            time_ms=0
        )

class MockChecker:
    def __init__(self, name, result):
        self.name = name
        self.result = result
        
    def evaluate(self, *args, **kwargs):
        return self.result

def print_header(title):
    print("\n" + "="*80)
    print(f"🔬 {title}")
    print("="*80)

def main():
    print_header("Overlap Engine Boundary & Edge Cases (SPEC 05)")
    
    engine = RiskEngine()
    engine.cost_monitor = MockCostMonitor()
    
    # We will manually craft CheckerResults with explicit entity spans to bypass text search
    # This lets us forcefully simulate precise mathematical intersections.
    
    test_cases = [
        {
            "name": "1. The 3-Way Partial Overlap (Venn Diagram)",
            "desc": "A[0,10] intersects B[5,15], which intersects C[12,20]. Should merge into a single [0,20] cluster with {A, B, C}.",
            "text": "12345678901234567890", # 20 chars
            "mock_checkers": [
                MockChecker("performance", CheckerResult(checker_name="performance", risk_score=0.5, explanation="A", entities=[{"span_start":0, "span_end":10}])),
                MockChecker("bias", CheckerResult(checker_name="bias", risk_score=0.5, explanation="B", entities=[{"span_start":5, "span_end":15}])),
                MockChecker("safety", CheckerResult(checker_name="safety", risk_score=0.5, explanation="C", entities=[{"span_start":12, "span_end":20}])),
                MockChecker("pii", CheckerResult(checker_name="pii", risk_score=0.0, explanation="clean"))
            ],
            "expected_overlap": True,
            "expected_records": 1,
            "expected_checkers": {"performance", "bias", "safety"}
        },
        {
            "name": "2. Multiple Separate Overlaps in Same Text",
            "desc": "A+B overlap at [0,10]. A+C overlap at [30,40]. Should produce TWO distinct OverlapRecords.",
            "text": "1234567890123456789012345678901234567890",
            "mock_checkers": [
                MockChecker("performance", CheckerResult(checker_name="performance", risk_score=0.5, explanation="A", entities=[
                    {"span_start":0, "span_end":10}, {"span_start":30, "span_end":40}
                ])),
                MockChecker("bias", CheckerResult(checker_name="bias", risk_score=0.5, explanation="B", entities=[{"span_start":0, "span_end":10}])),
                MockChecker("safety", CheckerResult(checker_name="safety", risk_score=0.5, explanation="C", entities=[{"span_start":30, "span_end":40}])),
                MockChecker("pii", CheckerResult(checker_name="pii", risk_score=0.0, explanation="clean"))
            ],
            "expected_overlap": True,
            "expected_records": 2,
            "expected_checkers": None # Checked custom below
        },
        {
            "name": "3. Same Checker Flags Multiple Times in Same Region",
            "desc": "Performance flags [0,100]. PII flags 'John'[10,14] at 0.9 and 'Smith'[20,25] at 0.8. Should merge into ONE cluster, and NOT multiply PII by itself (takes max PII score 0.9).",
            "text": "This is a long sentence where John and Smith were arrested.",
            "mock_checkers": [
                MockChecker("performance", CheckerResult(checker_name="performance", risk_score=0.4, explanation="A", entities=[{"span_start":0, "span_end":100}])),
                MockChecker("pii", CheckerResult(checker_name="pii", risk_score=0.9, explanation="B", entities=[
                    {"span_start":10, "span_end":14}, {"span_start":20, "span_end":25}
                ])),
                MockChecker("safety", CheckerResult(checker_name="safety", risk_score=0.0, explanation="clean")),
                MockChecker("bias", CheckerResult(checker_name="bias", risk_score=0.0, explanation="clean"))
            ],
            "expected_overlap": True,
            "expected_records": 1,
            "expected_checkers": {"performance", "pii"},
            "expected_noisy_or": 1.0 - ( (1-0.4) * (1-0.9) ) # Takes max PII score (0.9), ignores the 0.8.
        },
        {
            "name": "4. Directly Adjacent Spans (NO Overlap)",
            "desc": "A[0,5] and B[5,10]. Should NOT overlap because they touch but don't intersect.",
            "text": "1234567890",
            "mock_checkers": [
                MockChecker("performance", CheckerResult(checker_name="performance", risk_score=0.5, explanation="A", entities=[{"span_start":0, "span_end":5}])),
                MockChecker("pii", CheckerResult(checker_name="pii", risk_score=0.5, explanation="B", entities=[{"span_start":5, "span_end":10}])),
                MockChecker("safety", CheckerResult(checker_name="safety", risk_score=0.0, explanation="clean")),
                MockChecker("bias", CheckerResult(checker_name="bias", risk_score=0.0, explanation="clean"))
            ],
            "expected_overlap": False,
            "expected_records": 0,
            "expected_checkers": set()
        }
    ]
    
    passed = 0
    for case in test_cases:
        print(f"\n▶️ Running: {case['name']}")
        print(f"  Desc: {case['desc']}")
        
        engine.checkers = case["mock_checkers"]
        report = engine.evaluate_response(case["text"])
        
        print(f"  Overlap Detected : {report.overlap_detected}")
        print(f"  Records Created  : {len(report.overlap_records)}")
        
        success = True
        
        if report.overlap_detected != case["expected_overlap"]:
            print(f"  ❌ FAIL: Expected overlap_detected={case['expected_overlap']}")
            success = False
            
        if len(report.overlap_records) != case["expected_records"]:
            print(f"  ❌ FAIL: Expected {case['expected_records']} records, got {len(report.overlap_records)}")
            success = False
            
        if success and report.overlap_records:
            if case["name"].startswith("2."):
                # Custom check for Case 2
                rec1_checkers = set(report.overlap_records[0].overlapping_checkers)
                rec2_checkers = set(report.overlap_records[1].overlapping_checkers)
                valid = (rec1_checkers == {"performance", "bias"} and rec2_checkers == {"performance", "safety"}) or \
                        (rec1_checkers == {"performance", "safety"} and rec2_checkers == {"performance", "bias"})
                if not valid:
                    print(f"  ❌ FAIL: Expected records for {{perf, bias}} and {{perf, safety}}. Got {rec1_checkers} and {rec2_checkers}")
                    success = False
            else:
                rec = report.overlap_records[0]
                rec_checkers = set(rec.overlapping_checkers)
                if rec_checkers != case["expected_checkers"]:
                    print(f"  ❌ FAIL: Expected checkers {case['expected_checkers']}, got {rec_checkers}")
                    success = False
                    
                if "expected_noisy_or" in case:
                    expected_or = round(case["expected_noisy_or"], 3)
                    if rec.base_noisy_or != expected_or:
                        print(f"  ❌ FAIL: Expected Noisy-OR {expected_or}, got {rec.base_noisy_or}")
                        success = False

        if success:
            print("  ✅ PASS")
            passed += 1
            
    print_header(f"Edge Case Summary: {passed}/{len(test_cases)} Passed")

if __name__ == "__main__":
    main()
