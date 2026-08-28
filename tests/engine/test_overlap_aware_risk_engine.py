import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.engine.risk_engine import RiskEngine
from src.checkers.base import CheckerResult
from src.policy.schemas import UseCasePolicy

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
    print_header("Overlap-Aware Risk Engine Diagnostics (SPEC 05)")
    
    engine = RiskEngine()
    # Mock the cost monitor to avoid unnecessary output
    engine.cost_monitor = MockCostMonitor()
    
    test_cases = [
        {
            "name": "1. Clean Case (No overlaps)",
            "text": "The quick brown fox.",
            "mock_checkers": [
                MockChecker("performance", CheckerResult(checker_name="performance", risk_score=0.1, explanation="clean")),
                MockChecker("safety", CheckerResult(checker_name="safety", risk_score=0.2, explanation="clean")),
                MockChecker("bias", CheckerResult(checker_name="bias", risk_score=0.1, flagged_span="brown fox", explanation="clean")),
                MockChecker("pii", CheckerResult(checker_name="pii", risk_score=0.0, explanation="clean"))
            ],
            "expected_overlap": False
        },
        {
            "name": "2. Low-severity overlap (Bias + Safety)",
            "text": "This is a slightly biased and unsafe sentence.",
            "mock_checkers": [
                MockChecker("performance", CheckerResult(checker_name="performance", risk_score=0.0, explanation="clean")),
                MockChecker("safety", CheckerResult(checker_name="safety", risk_score=0.3, flagged_span="slightly biased and unsafe", explanation="warn")),
                MockChecker("bias", CheckerResult(checker_name="bias", risk_score=0.3, flagged_span="slightly biased and unsafe", explanation="warn")),
                MockChecker("pii", CheckerResult(checker_name="pii", risk_score=0.0, explanation="clean"))
            ],
            "expected_overlap": True,
            "expected_max_mult": 1.3, # bias_safety
            "expected_noisy_or": 1.0 - (0.7 * 0.7) # 1 - 0.49 = 0.51
        },
        {
            "name": "3. The Paradigm Case (Performance + PII)",
            "text": "John Doe was arrested yesterday.",
            "mock_checkers": [
                MockChecker("performance", CheckerResult(checker_name="performance", risk_score=0.6, flagged_span="John Doe was arrested", explanation="hallucinated fact")),
                MockChecker("safety", CheckerResult(checker_name="safety", risk_score=0.0, explanation="clean")),
                MockChecker("bias", CheckerResult(checker_name="bias", risk_score=0.0, explanation="clean")),
                # Mock a PII entity format result
                MockChecker("pii", CheckerResult(
                    checker_name="pii", 
                    risk_score=0.9, 
                    explanation="Found Person", 
                    entities=[{"entity_type": "PERSON", "span_start": 0, "span_end": 8, "confidence": 0.9}]
                ))
            ],
            "expected_overlap": True,
            "expected_max_mult": 1.8, # performance_pii
            "expected_noisy_or": 1.0 - (0.4 * 0.1) # 1 - 0.04 = 0.96
        }
    ]
    
    passed = 0
    for case in test_cases:
        print(f"\n▶️ Running: {case['name']}")
        
        # Inject mock checkers
        engine.checkers = case["mock_checkers"]
        
        report = engine.evaluate_response(case["text"])
        
        print(f"  Overlap Detected: {report.overlap_detected}")
        print(f"  Overall Risk    : {report.overall_risk_score}")
        
        success = True
        
        if report.overlap_detected != case["expected_overlap"]:
            print(f"  ❌ FAIL: Expected overlap_detected={case['expected_overlap']}")
            success = False
            
        if report.overlap_detected:
            rec = report.overlap_records[0]
            print(f"  Multiplier      : {rec.multiplier_applied} ({rec.multiplier_reason})")
            print(f"  Base Noisy-OR   : {rec.base_noisy_or}")
            print(f"  Final Span Risk : {rec.final_span_risk}")
            
            if rec.multiplier_applied != case["expected_max_mult"]:
                print(f"  ❌ FAIL: Expected multiplier {case['expected_max_mult']}, got {rec.multiplier_applied}")
                success = False
                
            expected_or = round(case["expected_noisy_or"], 3)
            if rec.base_noisy_or != expected_or:
                print(f"  ❌ FAIL: Expected Noisy-OR {expected_or}, got {rec.base_noisy_or}")
                success = False
                
        if success:
            print("  ✅ PASS")
            passed += 1
            
    print_header(f"Diagnostic Summary: {passed}/{len(test_cases)} Passed")

if __name__ == "__main__":
    main()
