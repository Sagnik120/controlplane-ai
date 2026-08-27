from pydantic import BaseModel, Field
from typing import List, Optional

class CheckerResult(BaseModel):
    """
    Standard output format for all risk checkers in ControlPlane.ai.
    """
    checker_name: str
    risk_score: float = Field(ge=0.0, le=1.0)
    flagged_span: Optional[str] = None
    overlaps_with: List[str] = Field(default_factory=list)
    explanation: str
