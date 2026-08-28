from typing import Optional
from src.adapters.base_adapter import BaseLLMAdapter
from src.engine.risk_engine import RiskEngine, FinalRiskReport
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy, ControlDecision
from src.audit.audit_logger import AuditLogger
from src.checkers.base import CheckerResult
from src.session.session_state import SessionStore
from src.repair.span_repair import SpanRepairEngine

class PipelineOrchestrator:
    """
    The central nervous system of ControlPlane-AI.
    Coordinates the LLM generation, risk evaluation, policy enforcement, and audit logging.
    """
    def __init__(self, adapter: BaseLLMAdapter, risk_engine: RiskEngine, control_policy: ControlPolicy, audit_logger: AuditLogger):
        self.adapter = adapter
        self.risk_engine = risk_engine
        self.control_policy = control_policy
        self.audit_logger = audit_logger
        self.session_store = SessionStore()
        self.repair_engine = SpanRepairEngine()
        
    def process_request(self, prompt: str, policy: UseCasePolicy, user_id: str = "anonymous", session_id: Optional[str] = None) -> dict:
        """
        Synchronous wrapper for processing a request End-to-End.
        """
        llm_output = ""
        
        try:
            # 1. Generate text from LLM (accumulate chunks for the synchronous pipeline)
            for chunk in self.adapter.generate_stream(prompt):
                llm_output += chunk
                
            if not llm_output:
                llm_output = "[LLM Returned Empty String]"
                
            # 2. Risk Engine Evaluation
            report = self.risk_engine.evaluate_response(
                llm_output,
                prompt=prompt,
                adapter=self.adapter,
                policy=policy
            )
            
            # 3. Session State Update (Spec 06)
            session_state = None
            if session_id:
                session_state = self.session_store.update(
                    session_id=session_id,
                    user_text=prompt, # Evaluate drift on the user prompt
                    checker_results=report.checker_results,
                    drift_window=policy.session_drift_window_size,
                    require_monotonic=policy.session_require_monotonic_trend
                )
            
            # 4. Control Policy Decision (Spec 03 + Spec 06)
            decision = self.control_policy.evaluate(report, policy, response_text=llm_output, session_state=session_state)
            
            # 4.5. SPEC 08: Intelligent Edit & Repair (Splice and Re-verify)
            repaired_text = llm_output
            was_repaired = False
            
            if decision.action == "MODIFY" and decision.target_spans:
                print(f"   [Pipeline] Initiating SPEC 08 span repair for {len(decision.target_spans)} spans...")
                for span_data in decision.target_spans:
                    span_text = span_data.get("text", "")
                    if not span_text or span_text not in repaired_text:
                        continue
                        
                    # Determine route (PII uses Presidio, others use LLM)
                    # We can guess based on entity_type presence
                    entity_type = span_data.get("entity_type")
                    if entity_type or decision.triggering_dimension == "pii":
                        # PII route
                        replacement = self.repair_engine.repair_via_anonymizer(span_text, entity_type or "PII")
                    else:
                        # LLM Route (Hallucinations, bias, safety)
                        replacement = self.repair_engine.repair_via_llm(
                            span_text=span_text,
                            context=llm_output,
                            prompt=prompt,
                            reason=decision.reasoning,
                            adapter=self.adapter
                        )
                        
                    # Splice: replace only the FIRST occurrence of the exact span string
                    repaired_text = repaired_text.replace(span_text, replacement, 1)
                    was_repaired = True
                    
                if was_repaired:
                    # RE-VERIFY: Run risk engine again on the spliced text
                    print(f"   [Pipeline] Re-verifying repaired text...")
                    reverify_report = self.risk_engine.evaluate_response(
                        repaired_text,
                        prompt=prompt,
                        adapter=self.adapter,
                        policy=policy
                    )
                    
                    reverify_decision = self.control_policy.evaluate(reverify_report, policy, response_text=repaired_text, session_state=session_state)
                    
                    if reverify_decision.action == "ALLOW":
                        # Success! The repair lowered the risk enough to release.
                        decision.action = "ALLOW"
                        decision.reasoning = f"SILENT REPAIR SUCCESS: {decision.reasoning}"
                        llm_output = repaired_text
                        report = reverify_report # Log the safe report
                    else:
                        # Failed to repair safely (e.g., still MODIFY, HUMAN, or REGENERATE). Escalate to REGENERATE.
                        decision.action = "REGENERATE"
                        decision.reasoning = f"REPAIR FAILED RE-VERIFICATION -> ESCALATED TO REGENERATE: {reverify_decision.reasoning}"
            
            # 5. Audit Log
            metadata = {"user_id": user_id, "prompt_length": len(prompt)}
            if session_id and session_state:
                metadata["session_id"] = session_id
                metadata["semantic_drift_score"] = session_state.semantic_drift_score
                metadata["cumulative_pii_exposure_score"] = session_state.cumulative_pii_exposure_score
                
            self.audit_logger.log(
                response_text=llm_output,
                report=report,
                decision=decision,
                metadata=metadata
            )
            
            # 6. Return Output
            if decision.action == "ALLOW":
                final_text = llm_output
            elif decision.action == "REDACT":
                final_text = f"[REDACTED BY POLICY] Original response contained sensitive data (Action: REDACT)."
            elif decision.action == "MODIFY":
                # Should theoretically not hit this anymore since we spliced, but fallback just in case
                final_text = f"[MODIFIED BY POLICY] {decision.reasoning}"
            elif decision.action == "REGENERATE":
                final_text = f"[REGENERATED BY POLICY] {decision.reasoning}"
            elif decision.action == "HUMAN":
                final_text = f"[UNDER REVIEW] Your request has been escalated to a human reviewer. {decision.reasoning}"
            else: # BLOCK
                final_text = f"[BLOCKED BY POLICY] {decision.reasoning}"
                
            return {
                "final_output": final_text,
                "risk_report": report.model_dump(),
                "control_decision": decision.model_dump()
            }
                
        except Exception as e:
            # Extreme Edge Case Handling: Total Pipeline Failure
            error_msg = f"System Error: {str(e)}"
            
            # Force a Block Decision for the audit log
            synthetic_report = FinalRiskReport(
                overall_risk_score=1.0,
                is_blocked=True,
                overlap_detected=False,
                checker_results=[CheckerResult(checker_name="system_failure", risk_score=1.0, explanation=error_msg)]
            )
            synthetic_decision = ControlDecision(action="BLOCK", reasoning="BLOCKED DUE TO SYSTEM EXCEPTION")
            
            metadata = {"user_id": user_id, "prompt_length": len(prompt), "exception": error_msg}
            if session_id:
                metadata["session_id"] = session_id
                
            self.audit_logger.log(
                response_text=llm_output if llm_output else "FAILED BEFORE GENERATION",
                report=synthetic_report,
                decision=synthetic_decision,
                metadata=metadata
            )
            
            return {
                "final_output": f"[SYSTEM ERROR] Unable to process request safely. Fallback block executed.",
                "risk_report": synthetic_report.model_dump(),
                "control_decision": synthetic_decision.model_dump()
            }
