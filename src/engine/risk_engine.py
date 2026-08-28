from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from src.checkers.base import CheckerResult
from src.cost.cost_monitor import CostMonitorResult
from src.checkers.performance_checker import PerformanceChecker
from src.checkers.safety_checker import SafetyChecker
from src.checkers.bias_checker import BiasChecker
from src.checkers.pii_checker import PiiChecker
from src.cost.cost_monitor import CostMonitor

class FinalRiskReport(BaseModel):
    """
    Combined report for a single LLM response after running through all checkers.
    """
    overall_risk_score: float = Field(ge=0.0, le=1.0)
    is_blocked: bool
    checker_results: List[Any]  # Can be CheckerResult or CostMonitorResult
    overlap_detected: bool
    overlap_explanation: Optional[str] = None

class RiskEngine:
    def __init__(self):
        # Initialize all available checkers
        self.checkers = [
            PerformanceChecker(),
            SafetyChecker(),
            BiasChecker(),
            PiiChecker()
        ]
        self.cost_monitor = CostMonitor()
        
    def _get_span_indices(self, text: str, span: str) -> List[tuple]:
        """Finds all (start, end) indices of a span within the text."""
        if not span:
            return []
        indices = []
        start = 0
        while True:
            idx = text.lower().find(span.lower(), start)
            if idx == -1:
                break
            indices.append((idx, idx + len(span)))
            start = idx + len(span)
        return indices
        
    def _check_overlap(self, ranges1: List[tuple], ranges2: List[tuple]) -> bool:
        """Returns True if any range in ranges1 overlaps with any range in ranges2."""
        for s1, e1 in ranges1:
            for s2, e2 in ranges2:
                if max(s1, s2) < min(e1, e2):  # True overlap condition
                    return True
        return False

    def evaluate_response(self, response_text: str, generation_time_ms: int = 0, model_tier: str = "standard") -> FinalRiskReport:
        results = []
        
        # 1. Run standard checkers
        for checker in self.checkers:
            results.append(checker.evaluate(response_text))
            
        # 2. Run cost monitor
        results.append(self.cost_monitor.evaluate(response_text, generation_time_ms, model_tier))
        
        # 3. Detect Overlaps between any two flagged spans
        overlap_detected = False
        overlap_pairs = []
        
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                r1 = results[i]
                r2 = results[j]
                
                # Only check for overlap if both have flagged spans
                if getattr(r1, 'flagged_span', None) and getattr(r2, 'flagged_span', None):
                    idx1 = self._get_span_indices(response_text, r1.flagged_span)
                    idx2 = self._get_span_indices(response_text, r2.flagged_span)
                    
                    if self._check_overlap(idx1, idx2):
                        overlap_detected = True
                        r1.overlaps_with.append(r2.checker_name)
                        r2.overlaps_with.append(r1.checker_name)
                        overlap_pairs.append(f"{r1.checker_name} & {r2.checker_name}")
                        
        # 4. Calculate Final Risk Score
        # Base score is the maximum risk score from any single checker
        max_score = max((r.risk_score for r in results), default=0.0)
        
        # Escalation logic: If multiple risk categories overlap on the same text snippet,
        # it compounds the risk. (e.g., PII that is also unsafe/biased)
        if overlap_detected:
            # Compound risk penalty
            max_score = min(max_score + 0.15, 1.0)
            overlap_explanation = f"Risk score escalated due to overlapping flagged spans between: {', '.join(overlap_pairs)}."
        else:
            overlap_explanation = None
            
        # 5. Is Blocked? (For Phase 4 policy we might make this dynamic, but for now hardcode threshold > 0.8)
        is_blocked = max_score >= 0.8
        
        return FinalRiskReport(
            overall_risk_score=round(max_score, 2),
            is_blocked=is_blocked,
            checker_results=results,
            overlap_detected=overlap_detected,
            overlap_explanation=overlap_explanation
        )
