from src.adapters.base_adapter import BaseLLMAdapter
from src.engine.risk_engine import RiskEngine, FinalRiskReport
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy, ControlDecision
from src.audit.audit_logger import AuditLogger
from src.checkers.base import CheckerResult

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
        
    def process_request(self, prompt: str, policy: UseCasePolicy, user_id: str = "anonymous") -> dict:
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
            report = self.risk_engine.evaluate_response(llm_output)
            
            # 3. Control Policy Decision
            decision = self.control_policy.evaluate(report, policy)
            
            # 4. Audit Log
            self.audit_logger.log(
                response_text=llm_output,
                report=report,
                decision=decision,
                metadata={"user_id": user_id, "prompt_length": len(prompt)}
            )
            
            # 5. Return Output
            if decision.action == "ALLOW":
                final_text = llm_output
            elif decision.action == "REDACT":
                final_text = f"[REDACTED BY POLICY] Original response contained sensitive data (Action: REDACT)."
            else: # BLOCK
                final_text = f"[BLOCKED BY POLICY] {decision.rationale}"
                
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
            synthetic_decision = ControlDecision(action="BLOCK", rationale="BLOCKED DUE TO SYSTEM EXCEPTION")
            
            self.audit_logger.log(
                response_text=llm_output if llm_output else "FAILED BEFORE GENERATION",
                report=synthetic_report,
                decision=synthetic_decision,
                metadata={"user_id": user_id, "prompt_length": len(prompt), "exception": error_msg}
            )
            
            return {
                "final_output": f"[SYSTEM ERROR] Unable to process request safely. Fallback block executed.",
                "risk_report": synthetic_report.model_dump(),
                "control_decision": synthetic_decision.model_dump()
            }
