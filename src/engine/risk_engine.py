import os
import yaml
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from src.checkers.base import CheckerResult
from src.cost.cost_monitor import CostMonitorResult
from src.checkers.performance_checker import PerformanceChecker
from src.checkers.safety_checker import SafetyChecker
from src.checkers.bias_checker import BiasChecker
from src.checkers.pii_checker import PiiChecker
from src.cost.cost_monitor import CostMonitor

class OverlapRecord(BaseModel):
    span_start: int
    span_end: int
    overlapping_checkers: List[str]
    individual_scores: Dict[str, float]
    base_noisy_or: float
    multiplier_applied: float
    multiplier_reason: str
    final_span_risk: float

class FinalRiskReport(BaseModel):
    """
    Combined report for a single LLM response after running through all checkers.
    """
    overall_risk_score: float = Field(ge=0.0, le=1.0)
    is_blocked: bool
    checker_results: List[Any]  # Can be CheckerResult or CostMonitorResult
    overlap_detected: bool
    overlap_records: List[OverlapRecord] = Field(default_factory=list)

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
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # Load severity matrix
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        matrix_path = os.path.join(project_root, 'configs', 'overlap_severity_matrix.yaml')
        if os.path.exists(matrix_path):
            with open(matrix_path, 'r') as f:
                data = yaml.safe_load(f)
                self.overlap_multipliers = data.get('overlap_multipliers', {})
        else:
            self.overlap_multipliers = {'default': 1.1}
            
    def _normalize_pair(self, c1: str, c2: str) -> str:
        """Sorts category names alphabetically so performance_pii == pii_performance."""
        sorted_pair = sorted([c1.lower(), c2.lower()])
        return f"{sorted_pair[0]}_{sorted_pair[1]}"
        
    def _get_multiplier(self, c1: str, c2: str) -> float:
        pair = self._normalize_pair(c1, c2)
        return self.overlap_multipliers.get(pair, self.overlap_multipliers.get('default', 1.1))
        
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
        
    def evaluate_response(self, response_text: str, generation_time_ms: int = 0, model_tier: str = "standard", prompt: str = "", adapter=None, policy=None) -> FinalRiskReport:
        """Synchronous wrapper for the parallel evaluate."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            # If we are already inside an event loop (e.g. testing with pytest-asyncio),
            # we need to handle this carefully. For the hackathon, we can use a new thread or nested loop.
            import threading
            result = None
            def run_in_thread():
                nonlocal result
                result = asyncio.run(self.evaluate_response_async(response_text, generation_time_ms, model_tier, prompt, adapter, policy))
            t = threading.Thread(target=run_in_thread)
            t.start()
            t.join()
            return result
        else:
            return asyncio.run(self.evaluate_response_async(response_text, generation_time_ms, model_tier, prompt, adapter, policy))

    async def evaluate_response_async(self, response_text: str, generation_time_ms: int = 0, model_tier: str = "standard", prompt: str = "", adapter=None, policy=None) -> FinalRiskReport:
        
        # 1. Dispatch Checkers in Parallel
        loop = asyncio.get_running_loop()
        futures = []
        context = {
            'prompt': prompt,
            'adapter': adapter,
            'policy': policy
        }
        
        for checker in self.checkers:
            # We use the new BaseChecker run method which is synchronous.
            # We run it in the thread pool to avoid blocking the event loop.
            if checker.name in ["performance", "bias", "safety", "pii"]:
                futures.append(loop.run_in_executor(self.thread_pool, checker.run, response_text, context))
            else:
                # Fallback for any checkers not yet updated
                futures.append(loop.run_in_executor(self.thread_pool, checker.evaluate, response_text))
                
        # Wait for all checkers to complete concurrently
        # return_exceptions=True prevents a single crashed checker from killing the pipeline
        raw_results = await asyncio.gather(*futures, return_exceptions=True)
        
        results = []
        for i, res in enumerate(raw_results):
            if isinstance(res, Exception):
                # Checker failed entirely (e.g., OOM, network timeout)
                # We escalate to HUMAN via a max risk score on this dimension
                failed_checker_name = self.checkers[i].name
                results.append(CheckerResult(
                    checker_name=failed_checker_name,
                    risk_score=1.0,
                    explanation=f"FATAL: Checker {failed_checker_name} raised exception during parallel execution: {str(res)}",
                    flagged_span=None
                ))
            else:
                results.append(res)
            
        # 2. Run cost monitor (fast, synchronous)
        cost_result = self.cost_monitor.evaluate(response_text, generation_time_ms, model_tier)
        
        # 3. Detect Overlaps using Interval Merging
        # Extract all spans: list of (start, end, checker_name, risk_score)
        all_spans = []
        for r in results:
            if getattr(r, 'entities', []):
                # PII checker uses entities with precise indices
                for ent in r.entities:
                    start = ent.get('span_start')
                    end = ent.get('span_end')
                    if start is not None and end is not None:
                        all_spans.append((start, end, r.checker_name, r.risk_score))
            elif getattr(r, 'flagged_span', None):
                indices = self._get_span_indices(response_text, r.flagged_span)
                for s, e in indices:
                    all_spans.append((s, e, r.checker_name, r.risk_score))
                    
        # Sort intervals by start index
        all_spans.sort(key=lambda x: x[0])
        
        merged_intervals = []
        for span in all_spans:
            s, e, name, score = span
            if not merged_intervals:
                merged_intervals.append({'start': s, 'end': e, 'checkers': {name: score}})
            else:
                last = merged_intervals[-1]
                # Check for overlap: max(s1, s2) < min(e1, e2)
                # Since sorted by start, s is always >= last['start']
                if s < last['end']:
                    # Overlap found!
                    last['end'] = max(last['end'], e)
                    # Use max risk score if same checker flagged multiple times in same span
                    if name in last['checkers']:
                        last['checkers'][name] = max(last['checkers'][name], score)
                    else:
                        last['checkers'][name] = score
                else:
                    merged_intervals.append({'start': s, 'end': e, 'checkers': {name: score}})
                    
        overlap_records = []
        overlap_detected = False
        
        for interval in merged_intervals:
            checkers_dict = interval['checkers']
            if len(checkers_dict) > 1:
                overlap_detected = True
                names = list(checkers_dict.keys())
                
                # Calculate Noisy-OR
                prob_safe = 1.0
                for score in checkers_dict.values():
                    prob_safe *= (1.0 - score)
                base_noisy_or = 1.0 - prob_safe
                
                # Find max pair multiplier
                max_mult = 1.0
                max_pair = None
                for i in range(len(names)):
                    for j in range(i + 1, len(names)):
                        m = self._get_multiplier(names[i], names[j])
                        if m > max_mult:
                            max_mult = m
                            max_pair = (names[i], names[j])
                            
                final_span_risk = min(1.0, base_noisy_or * max_mult)
                
                if max_pair:
                    reason = f"{max_pair[0]}+{max_pair[1]} pair detected ({max_mult}x)"
                else:
                    reason = "default overlap multiplier applied"
                    
                overlap_records.append(OverlapRecord(
                    span_start=interval['start'],
                    span_end=interval['end'],
                    overlapping_checkers=names,
                    individual_scores=checkers_dict,
                    base_noisy_or=round(base_noisy_or, 3),
                    multiplier_applied=max_mult,
                    multiplier_reason=reason,
                    final_span_risk=round(final_span_risk, 3)
                ))
                
                # Tag the original checker results with overlap info for legacy compat
                for r in results:
                    if r.checker_name in names:
                        for other in names:
                            if other != r.checker_name and other not in r.overlaps_with:
                                r.overlaps_with.append(other)
        
        # 4. Calculate Final Risk Score
        # Base score is the maximum risk score from any single checker
        max_score = max((r.risk_score for r in results), default=0.0)
        
        # Take the maximum of individual checker risks OR any overlap risks
        if overlap_records:
            max_overlap_risk = max(rec.final_span_risk for rec in overlap_records)
            max_score = max(max_score, max_overlap_risk)
            
        is_blocked = max_score >= 0.8
        
        # Include cost monitor result in output array
        final_results_list = results + [cost_result]
        
        return FinalRiskReport(
            overall_risk_score=round(max_score, 3),
            is_blocked=is_blocked,
            checker_results=final_results_list,
            overlap_detected=overlap_detected,
            overlap_records=overlap_records
        )
