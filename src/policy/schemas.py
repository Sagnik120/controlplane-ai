from pydantic import BaseModel, Field
from typing import Dict, Literal, Optional, Any, List, Tuple

class PerformanceBudget(BaseModel):
    tier0_uncertain_band: Tuple[float, float] = (0.20, 0.80)
    selfcheck_num_samples: int = 3
    max_tier1_calls_per_response: Optional[int] = None
    allow_best_of_n_regenerate: bool = False
    best_of_n: int = 3

class PiiBudget(BaseModel):
    tier0_mode: str = "always_full_ner"

class BiasBudget(BaseModel):
    check_frequency: str = "every_window"

class SafetyBudget(BaseModel):
    check_frequency: str = "every_window"

class RegenerateBudget(BaseModel):
    max_attempts: int = 2

class CheckerBudgetProfile(BaseModel):
    performance: PerformanceBudget = Field(default_factory=PerformanceBudget)
    pii: PiiBudget = Field(default_factory=PiiBudget)
    bias: BiasBudget = Field(default_factory=BiasBudget)
    safety: SafetyBudget = Field(default_factory=SafetyBudget)
    regenerate: RegenerateBudget = Field(default_factory=RegenerateBudget)

class UseCasePolicy(BaseModel):
    """
    Defines the acceptable risk thresholds for a specific application/use-case.
    """
    name: str
    description: Optional[str] = None
    
    # SPEC 11
    consequence_level: str = "medium"
    latency_budget_ms: Optional[int] = None
    checker_budget: CheckerBudgetProfile = Field(default_factory=CheckerBudgetProfile)
    
    # SPEC 12 Overlap Thresholds
    char_iou_threshold: float = 0.3
    cosine_threshold: float = 0.62
    
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
    
    # Spec 10 Config Knobs
    pii_tier0_mode: str = "always_full_ner"
    bias_check_frequency: str = "every_window"
    
    # Spec 06 Config Knobs
    session_drift_window_size: int = 5
    session_drift_threshold: float = 0.55
    session_require_monotonic_trend: bool = True
    session_cumulative_pii_threshold: int = 3
    session_escalation_action: str = "HUMAN"
    
    # Spec 09 Config Knobs (Checkpoint-Backtrack Resampling)
    max_regenerate_attempts: int = 2
    tier0_uncertain_band_low: float = 0.20
    tier0_uncertain_band_high: float = 0.80
    regenerate_temperature: float = 0.2

class FlaggedSpan(BaseModel):
    checker_name: str
    text: str
    char_start: int
    char_end: int
    risk_score: float
    risk_reason: str
    embedding: Optional[List[float]] = None

class OverlapGroup(BaseModel):
    spans: List[FlaggedSpan]
    aggregated_risk: float
    multiplier_applied: float
    reason: str

class FinalRiskReport(BaseModel):
    overall_risk_score: float = 0.0
    is_blocked: bool = False
    checker_results: List[Any] = Field(default_factory=list)
    overlap_detected: bool = False
    overlap_groups: List[OverlapGroup] = Field(default_factory=list)
    action: str = "ALLOW"
    under_verified: bool = False

class ControlDecision(BaseModel):
    """
    The final output of the ControlPolicy module.
    """
    action: Literal["ALLOW", "MODIFY", "REGENERATE", "HUMAN", "BLOCK", "REDACT"]
    triggering_dimension: Optional[str] = None
    calibration_metadata: Optional[Dict[str, Any]] = None
    target_spans: Optional[list] = None
    clean_prefix: Optional[str] = None
    failed_span: Optional[str] = None
    reasoning: str
