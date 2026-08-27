from src.engine.risk_engine import FinalRiskReport
from src.policy.schemas import UseCasePolicy, ControlDecision

class ControlPolicy:
    """
    Takes a FinalRiskReport and a UseCasePolicy, and determines the final ControlDecision.
    """
    
    def evaluate(self, report: FinalRiskReport, policy: UseCasePolicy) -> ControlDecision:
        # 1. Check strict checker-specific thresholds first
        for checker_result in report.checker_results:
            checker_name = checker_result.checker_name
            score = checker_result.risk_score
            
            # If the policy defines a specific threshold for this checker, use it. 
            # Otherwise fallback to 1.0 (meaning only the global overall_risk_score applies)
            threshold = policy.checker_thresholds.get(checker_name, 1.0)
            
            if score > threshold:
                return ControlDecision(
                    action="BLOCK",
                    rationale=f"BLOCKED: {checker_name.capitalize()} risk score ({score}) exceeds use-case threshold ({threshold})."
                )
                
        # 2. Check Overlap policy
        if report.overlap_detected and policy.block_on_overlap:
            return ControlDecision(
                action="BLOCK",
                rationale=f"BLOCKED: Policy forbids overlapping risk spans. {report.overlap_explanation}"
            )
            
        # 3. Check Global Overall Risk
        if report.overall_risk_score > policy.max_overall_risk:
            return ControlDecision(
                action="BLOCK",
                rationale=f"BLOCKED: Overall risk score ({report.overall_risk_score}) exceeds global threshold ({policy.max_overall_risk})."
            )
            
        # 4. Check Redact flag
        if policy.redact_pii:
            # Look to see if PII was flagged but didn't hit a block threshold
            for checker_result in report.checker_results:
                if checker_result.checker_name == "pii" and checker_result.risk_score > 0.0:
                    return ControlDecision(
                        action="REDACT",
                        rationale="REDACT: PII detected and redaction policy is active."
                    )
                    
        # 5. Default Allow
        return ControlDecision(
            action="ALLOW",
            rationale="ALLOW: Request passed all use-case policy thresholds."
        )
