from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from src.policy.schemas import FlaggedSpan
from abc import ABC, abstractmethod

class CheckerResult(BaseModel):
    """
    Standard output format for all risk checkers in ControlPlane.ai.
    """
    checker_name: str
    risk_score: float = Field(ge=0.0, le=1.0)
    flagged_span: Optional[str] = None
    flagged_spans: List[FlaggedSpan] = Field(default_factory=list)
    overlaps_with: List[str] = Field(default_factory=list)
    explanation: str
    
    # Extended fields for advanced Checkers (like PerformanceChecker with SelfCheckGPT)
    sentence_scores: Optional[List[Dict[str, Any]]] = None
    confidence: Optional[float] = None
    method: Optional[str] = None
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Extended fields for LLM-as-a-judge checkers (Bias, Safety)
    judge_category: Optional[str] = None
    judge_severity: Optional[str] = None
    
    # Extended fields for CBR (Spec 09)
    tier: Optional[int] = None
    ran_selfcheck: Optional[bool] = None

class Tier0Result(BaseModel):
    needs_tier1: bool
    risk: float = 0.0
    latency_ms: int = 0
    explanation: str = ""

class BaseChecker(ABC):
    name: str

    def run(self, window_text: str, context: dict) -> CheckerResult:
        """Synchronous entrypoint — called inside a thread/process pool."""
        tier0 = self.tier0_gate(window_text, context)
        if not tier0.needs_tier1:
            return CheckerResult(
                checker_name=self.name,
                risk_score=tier0.risk,
                explanation=tier0.explanation,
                tier=0,
                ran_selfcheck=False
            )
        
        # Heavy ML check
        return self.tier1_check(window_text, context)

    @abstractmethod
    def tier0_gate(self, window_text: str, context: dict) -> Tier0Result:
        pass

    @abstractmethod
    def tier1_check(self, window_text: str, context: dict) -> CheckerResult:
        pass
