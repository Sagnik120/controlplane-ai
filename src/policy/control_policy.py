from typing import Optional, Any
from src.engine.risk_engine import FinalRiskReport
from src.policy.schemas import UseCasePolicy, ControlDecision
from src.session.session_state import SessionRiskState
from src.policy.adaptive_calibration import AdaptiveCalibrator

class ControlPolicy:
    """
    Takes a FinalRiskReport and a UseCasePolicy, and determines the final ControlDecision
    using Conformal-Prediction-Calibrated Tiered Routing.
    """
    
    def evaluate(self, report: FinalRiskReport, policy: UseCasePolicy, response_text: str = "", session_state: Optional[SessionRiskState] = None) -> ControlDecision:
        # Access live adaptive calibrator singleton
        calibrator = AdaptiveCalibrator()
        # Fallback static thresholds in case calibrator is missing data
        static_thresholds = policy.calibrated_thresholds
        
        highest_severity = "ALLOW"
        triggering_dim = None
        triggering_score = 0.0
        active_tau_low = 1.0
        active_tau_high = 1.0
        
        clean_prefix = None
        failed_span = None
        
        spans = []
        
            # 1. Check each dimension against its calibrated thresholds
        for checker_result in report.checker_results:
            dim = checker_result.checker_name
            score = checker_result.risk_score
            
            # Use live dynamic thresholds from ACI
            live_thresholds = calibrator.get_active_thresholds(policy.name, dim)
            
            # Default uncalibrated thresholds if not present
            tau_low = live_thresholds.get("tau_low", static_thresholds.get(dim, {}).get("tau_low", policy.max_overall_risk))
            tau_high = live_thresholds.get("tau_high", static_thresholds.get(dim, {}).get("tau_high", 1.0))
            
            severity = "ALLOW"
            if getattr(checker_result, 'is_error', False):
                severity = "BLOCK"
            elif score >= tau_high:
                severity = "HUMAN"
            elif score >= tau_low:
                severity = "NEEDS_REPAIR"
                
            # Promote severity
            if severity == "BLOCK":
                highest_severity = "BLOCK"
                triggering_dim = dim
                triggering_score = score
                active_tau_low = tau_low
                active_tau_high = tau_high
                break # BLOCK is max severity, short-circuit
            elif severity == "HUMAN" and highest_severity != "BLOCK":
                highest_severity = "HUMAN"
                triggering_dim = dim
                triggering_score = score
                active_tau_low = tau_low
                active_tau_high = tau_high
                break # HUMAN is max severity, we can short-circuit
            elif severity == "NEEDS_REPAIR" and highest_severity == "ALLOW":
                highest_severity = "NEEDS_REPAIR"
                triggering_dim = dim
                triggering_score = score
                active_tau_low = tau_low
                active_tau_high = tau_high
                
            # Collect spans for repair estimation
            if severity != "ALLOW":
                if getattr(checker_result, 'flagged_spans', None):
                    for fs in checker_result.flagged_spans:
                        spans.append({
                            "text": fs.text,
                            "char_start": fs.char_start,
                            "char_end": fs.char_end,
                            "entity_type": fs.risk_reason
                        })
                elif getattr(checker_result, 'entities', None):
                    spans.extend(checker_result.entities)
                elif getattr(checker_result, 'sentence_scores', None):
                    # For performance checker
                    for s in checker_result.sentence_scores:
                        if s.get("score", 0.0) >= tau_low:
                            spans.append({"text": s.get("sentence", "")})
                elif getattr(checker_result, 'flagged_span', None):
                    spans.append({"text": checker_result.flagged_span})
                    
        # SPEC 11: Handle under-verified circuit breaker timeouts
        if report.under_verified:
            if getattr(policy, 'consequence_level', 'medium') in ["medium", "high"]:
                if highest_severity == "ALLOW":
                    highest_severity = "HUMAN" if policy.consequence_level == "high" else "NEEDS_REPAIR"
                    triggering_dim = "timeout_circuit_breaker"
                    triggering_score = 1.0
                    
        # 2. Check Overlap policy (legacy support)
        if getattr(report, 'overlap_detected', False) and policy.block_on_overlap and highest_severity == "ALLOW":
            highest_severity = "NEEDS_REPAIR"
            triggering_dim = "overlap"
            
        # 3. Resolve NEEDS_REPAIR into MODIFY or REGENERATE
        action = highest_severity
        target_spans = None
        
        if action == "NEEDS_REPAIR":
            total_len = len(response_text) if response_text else 100
            span_len = sum(len(s.get("text", "")) for s in spans) if spans else 0
            
            coverage_pct = (span_len / total_len) * 100 if total_len > 0 else 100
            
            if coverage_pct < policy.modify_span_threshold_pct and spans:
                action = "MODIFY"
                target_spans = spans
            else:
                action = "REGENERATE"
                
            if action == "REGENERATE":
                if spans and response_text:
                    earliest_idx = len(response_text)
                    for s in spans:
                        span_text = s.get("text", "")
                        idx = response_text.find(span_text)
                        if idx != -1 and idx < earliest_idx:
                            earliest_idx = idx
                            failed_span = span_text
                    
                    if earliest_idx != -1 and earliest_idx != len(response_text):
                        clean_prefix = response_text[:earliest_idx]
                    else:
                        clean_prefix = ""
                        failed_span = ""
                else:
                    clean_prefix = ""
                    failed_span = ""
                
        reasoning = ""
        # 4. Check Session Signals (SPEC 06 Override)
        if session_state and action != "HUMAN":
            if session_state.cumulative_pii_exposure_score >= policy.session_cumulative_pii_threshold:
                action = policy.session_escalation_action
                triggering_dim = "session_cumulative_pii"
                triggering_score = session_state.cumulative_pii_exposure_score
                reasoning = (f"{action}: Cumulative PII Exposure ({triggering_score}) exceeded session limit of {policy.session_cumulative_pii_threshold}.")
            elif session_state.semantic_drift_score >= policy.session_drift_threshold:
                action = policy.session_escalation_action
                triggering_dim = "session_semantic_drift"
                triggering_score = session_state.semantic_drift_score
                reasoning = (f"{action}: Semantic Drift ({triggering_score}) exceeded session limit of {policy.session_drift_threshold}.")

        # 5. Construct response if not already set by session overrides
        if not reasoning:
            if action == "ALLOW":
                reasoning = "ALLOW: Request passed all calibrated thresholds."
            elif action == "HUMAN":
                reasoning = (f"HUMAN ESCALATION: {triggering_dim.capitalize()} risk score ({triggering_score}) "
                             f"exceeded calibrated τ_high={active_tau_high} (α_high={policy.alpha_high}).")
            elif action == "MODIFY":
                reasoning = (f"MODIFY: {triggering_dim.capitalize()} risk score ({triggering_score}) "
                             f"exceeded τ_low={active_tau_low}. Localized spans detected for repair.")
            elif action == "REGENERATE":
                reasoning = (f"REGENERATE: {triggering_dim.capitalize()} risk score ({triggering_score}) "
                             f"exceeded τ_low={active_tau_low}. Issues are too diffuse to modify in-place.")
            elif action == "BLOCK":
                reasoning = (f"BLOCK: Critical checker failure or API error in {triggering_dim.capitalize()}. "
                             f"Halting pipeline to prevent unverified response.")
                             
        if report.under_verified and action != "ALLOW":
            reasoning = f"[UNDER-VERIFIED] {reasoning} (Circuit breaker interrupted full checks due to latency constraints)."
                         
        calibration_meta = {
            "alpha_low": policy.alpha_low,
            "alpha_high": policy.alpha_high,
            "tau_low_used": active_tau_low,
            "tau_high_used": active_tau_high,
            "triggering_score": triggering_score,
            "calibration_n": getattr(policy, "calibration_n", 64)
        } if triggering_dim and not triggering_dim.startswith("session_") else None

        return ControlDecision(
            action=action,
            triggering_dimension=triggering_dim,
            calibration_metadata=calibration_meta,
            target_spans=target_spans,
            clean_prefix=clean_prefix,
            failed_span=failed_span,
            reasoning=reasoning
        )
