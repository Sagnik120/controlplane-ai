from pydantic import BaseModel, Field

class CostMonitorResult(BaseModel):
    checker_name: str = "cost"
    risk_score: float = Field(ge=0.0, le=1.0)
    flagged_span: None = None
    overlaps_with: list = Field(default_factory=list)
    explanation: str
    tokens_estimated: int
    time_ms: int

class CostMonitor:
    """
    Evaluates cost risk based on generation time and estimated token count.
    """
    
    def evaluate(self, response_text: str, generation_time_ms: int, model_tier: str = "standard") -> CostMonitorResult:
        try:
            # Naive token estimation: ~4 chars per token
            tokens = len(response_text) // 4
            
            # Risk formula: high token count + expensive model + long time = high risk
            # Let's say 2000 tokens is threshold for score=1.0 on standard model
            base_risk = min(tokens / 2000.0, 1.0)
            
            # Model tier multiplier
            tier_mult = 1.5 if model_tier == "premium" else 1.0
            
            # Time penalty (if it took > 5000ms, increase risk slightly)
            time_penalty = 0.1 if generation_time_ms > 5000 else 0.0
            
            final_risk = min(base_risk * tier_mult + time_penalty, 1.0)
            
            return CostMonitorResult(
                risk_score=final_risk,
                explanation=f"Estimated {tokens} tokens generated in {generation_time_ms}ms on {model_tier} tier.",
                tokens_estimated=tokens,
                time_ms=generation_time_ms
            )
            
        except Exception as e:
            return CostMonitorResult(
                risk_score=1.0,
                explanation=f"Checker failed: {str(e)}",
                tokens_estimated=0,
                time_ms=0
            )
