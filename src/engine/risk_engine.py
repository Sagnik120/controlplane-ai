import os
import yaml
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from src.policy.schemas import OverlapGroup

from src.checkers.base import CheckerResult
from src.cost.cost_monitor import CostMonitorResult
from src.checkers.performance_checker import PerformanceChecker
from src.checkers.safety_checker import SafetyChecker
from src.checkers.bias_checker import BiasChecker
from src.checkers.pii_checker import PiiChecker
from src.cost.cost_monitor import CostMonitor
from src.engine.embedding_registry import EmbeddingRegistry
from src.engine.semantic_overlap import SemanticOverlapDetector


class FinalRiskReport(BaseModel):
    """
    Combined report for a single LLM response after running through all checkers.
    """
    overall_risk_score: float = Field(ge=0.0, le=1.0)
    is_blocked: bool
    checker_results: List[Any]  # Can be CheckerResult or CostMonitorResult
    overlap_detected: bool
    overlap_groups: List[OverlapGroup] = Field(default_factory=list)
    under_verified: bool = False

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
        
        self.overlap_detector = SemanticOverlapDetector()
        
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
        # Backward compatibility for mocks/subclasses that override evaluate_response
        if type(self).evaluate_response is not RiskEngine.evaluate_response and type(self).evaluate_response_async is RiskEngine.evaluate_response_async:
            return self.evaluate_response(response_text, generation_time_ms, model_tier, prompt, adapter, policy)
            
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
        # SPEC 11: Circuit Breaker based on latency_budget_ms
        latency_budget = None
        if policy and hasattr(policy, 'latency_budget_ms') and policy.latency_budget_ms:
            latency_budget = policy.latency_budget_ms / 1000.0
            
        under_verified = False
        
        try:
            raw_results = await asyncio.wait_for(
                asyncio.gather(*futures, return_exceptions=True),
                timeout=latency_budget
            )
        except asyncio.TimeoutError:
            under_verified = True
            # Gracefully degrade: try to salvage any completed futures
            raw_results = []
            for i, f in enumerate(futures):
                if f.done() and not f.cancelled():
                    try:
                        raw_results.append(f.result())
                    except Exception as e:
                        raw_results.append(CheckerResult(
                            checker_name=self.checkers[i].name,
                            risk_score=1.0,
                            explanation=f"Checker failed: {str(e)}"
                        ))
                else:
                    # Cancel the pending future if possible
                    f.cancel()
                    raw_results.append(CheckerResult(
                        checker_name=self.checkers[i].name,
                        risk_score=0.0,
                        explanation="Skipped (Circuit Breaker Timeout)"
                    ))
        
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
        
        # 3. Detect Overlaps using SemanticOverlapDetector
        all_spans = []
        for r in results:
            if hasattr(r, 'flagged_spans') and r.flagged_spans:
                all_spans.extend(r.flagged_spans)
                
        # Fallback for old checkers not yet returning flagged_spans natively
        # (Though we will update them, this makes the transition safer)
        for r in results:
            if not getattr(r, 'flagged_spans', []):
                if getattr(r, 'entities', []):
                    # PII checker uses entities with precise indices
                    for ent in r.entities:
                        start = ent.get('span_start')
                        end = ent.get('span_end')
                        text = ent.get('text', '')
                        if start is not None and end is not None:
                            from src.policy.schemas import FlaggedSpan
                            all_spans.append(FlaggedSpan(
                                checker_name=r.checker_name,
                                text=text,
                                char_start=start,
                                char_end=end,
                                risk_score=r.risk_score,
                                risk_reason="Legacy PII extraction"
                            ))
                elif getattr(r, 'flagged_span', None):
                    indices = self._get_span_indices(response_text, r.flagged_span)
                    for s, e in indices:
                        from src.policy.schemas import FlaggedSpan
                        all_spans.append(FlaggedSpan(
                            checker_name=r.checker_name,
                            text=r.flagged_span,
                            char_start=s,
                            char_end=e,
                            risk_score=r.risk_score,
                            risk_reason="Legacy Flagged Span extraction"
                        ))
        
        char_iou = policy.char_iou_threshold if policy and hasattr(policy, 'char_iou_threshold') else 0.3
        cosine = policy.cosine_threshold if policy and hasattr(policy, 'cosine_threshold') else 0.62
        
        overlap_groups = self.overlap_detector.find_overlaps(
            all_spans, 
            char_iou_threshold=char_iou,
            cosine_threshold=cosine
        )
        
        overlap_detected = len(overlap_groups) > 0
        
        # Tag the original checker results with overlap info for legacy compat
        for group in overlap_groups:
            names = [s.checker_name for s in group.spans]
            for r in results:
                if r.checker_name in names:
                    for other in names:
                        if other != r.checker_name and other not in r.overlaps_with:
                            r.overlaps_with.append(other)
        
        # 4. Calculate Final Risk Score
        # Base score is the maximum risk score from any single checker
        max_score = max((r.risk_score for r in results), default=0.0)
        
        # Take the maximum of individual checker risks OR any overlap risks
        if overlap_groups:
            max_overlap_risk = max(g.aggregated_risk for g in overlap_groups)
            max_score = max(max_score, max_overlap_risk)
            
        is_blocked = max_score >= 0.8
        
        # Include cost monitor result in output array
        final_results_list = results + [cost_result]
        
        return FinalRiskReport(
            overall_risk_score=round(max_score, 3),
            is_blocked=is_blocked,
            checker_results=final_results_list,
            overlap_detected=overlap_detected,
            overlap_groups=overlap_groups,
            under_verified=under_verified
        )
