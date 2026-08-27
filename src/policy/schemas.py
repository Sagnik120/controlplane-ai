from pydantic import BaseModel, Field
from typing import Dict, Literal, Optional

class UseCasePolicy(BaseModel):
    """
    Defines the acceptable risk thresholds for a specific application/use-case.
    """
    name: str
    description: Optional[str] = None
    
    # Global threshold: if the FinalRiskReport's overall_risk_score > this, block it.
    max_overall_risk: float = 0.8
    
    # Specific thresholds per checker (overrides max_overall_risk if stricter)
    # e.g., {"safety": 0.1, "pii": 0.0} (0 tolerance for PII)
    checker_thresholds: Dict[str, float] = Field(default_factory=dict)
    
    # Behaviors
    block_on_overlap: bool = True
    redact_pii: bool = False

class ControlDecision(BaseModel):
    """
    The final output of the ControlPolicy module.
    """
    action: Literal["ALLOW", "BLOCK", "REDACT"]
    rationale: str
