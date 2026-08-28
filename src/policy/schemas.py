from pydantic import BaseModel, Field
from typing import Dict, Literal, Optional, Any

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
    
    # Spec 01 Config Knobs
    performance_n_samples: int = 3
    performance_sampling_temperature: float = 1.0
    performance_nli_weight: float = 0.7
    performance_bertscore_weight: float = 0.3
    
    # Spec 02 Config Knobs
    pii_entity_allowlist: Optional[list] = None
    pii_min_confidence: float = 0.5
    
    # Spec 03 Config Knobs (Conformal Calibration)
    alpha_low: float = 0.05
    alpha_high: float = 0.01
    modify_span_threshold_pct: float = 25.0
    calibrated_thresholds: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    
    # Spec 04 Config Knobs
    safety_checker_always_judge: bool = False
    bias_checker_always_judge: bool = False
    
    # Spec 06 Config Knobs
    session_drift_window_size: int = 5
    session_drift_threshold: float = 0.55
    session_require_monotonic_trend: bool = True
    session_cumulative_pii_threshold: int = 3
    session_escalation_action: str = "HUMAN"

class ControlDecision(BaseModel):
    """
    The final output of the ControlPolicy module.
    """
    action: Literal["ALLOW", "MODIFY", "REGENERATE", "HUMAN", "BLOCK", "REDACT"]
    triggering_dimension: Optional[str] = None
    calibration_metadata: Optional[Dict[str, Any]] = None
    target_spans: Optional[list] = None
    reasoning: str
