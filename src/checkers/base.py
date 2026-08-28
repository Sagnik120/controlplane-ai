from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class CheckerResult(BaseModel):
    """
    Standard output format for all risk checkers in ControlPlane.ai.
    """
    checker_name: str
    risk_score: float = Field(ge=0.0, le=1.0)
    flagged_span: Optional[str] = None
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
