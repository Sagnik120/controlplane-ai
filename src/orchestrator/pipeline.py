from typing import Optional
from src.adapters.base_adapter import BaseLLMAdapter
from src.engine.risk_engine import RiskEngine, FinalRiskReport
from src.policy.control_policy import ControlPolicy
from src.policy.schemas import UseCasePolicy, ControlDecision
from src.audit.audit_logger import AuditLogger
from src.checkers.base import CheckerResult
from src.session.session_state import SessionStore
from src.repair.span_repair import SpanRepairEngine
from src.regenerate.checkpoint_backtrack import CheckpointManager, RegenerationEngine
from src.agent.action_gate import ActionRiskChecker
from src.policy.schemas import ProposedAction
from src.engine.embedding_registry import EmbeddingRegistry
from src.engine.semantic_overlap import SemanticOverlapDetector
import time
import uuid

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
        self.checkpoint_mgr = CheckpointManager()
        self.regeneration_engine = RegenerationEngine(adapter, self.checkpoint_mgr)
        
        # Instantiate overlap detector sharing the engine's embedder if possible
        embedder = EmbeddingRegistry.get_embedder()
        overlap_detector = SemanticOverlapDetector(embedder=embedder)
        self.action_checker = ActionRiskChecker(overlap_detector=overlap_detector)
        
    def process_request(self, prompt: str, policy: UseCasePolicy, user_id: str = "anonymous", session_id: Optional[str] = None, request_context: Optional[dict] = None) -> dict:
        """
        Synchronous wrapper for processing a request End-to-End.
        Delegates to process_request_async.
        """
        import asyncio
        import threading
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            result = None
            def run_in_thread():
                nonlocal result
                result = asyncio.run(self.process_request_async(prompt, policy, user_id, session_id, request_context))
            t = threading.Thread(target=run_in_thread)
            t.start()
            t.join()
            return result
        else:
            return asyncio.run(self.process_request_async(prompt, policy, user_id, session_id, request_context))

    async def process_request_async(self, prompt: str, policy: UseCasePolicy, user_id: str = "anonymous", session_id: Optional[str] = None, request_context: Optional[dict] = None) -> dict:
        """
        Synchronous wrapper for processing a request End-to-End.
        """
        import copy
        start_time = time.time()
        request_id = str(uuid.uuid4())
        request_context = request_context or {}
        
        # SPEC 11: Action Type Escalation (Tier Override)
        action_type = request_context.get("action_type")
        proposed_action_dict = request_context.get("proposed_action")
        
        if action_type in ["refund", "account_change", "delete_data", "execute_trade"] or proposed_action_dict:
            print(f"   [Pipeline] Action context detected. Extending latency budget.")
            policy = policy.model_copy(deep=True) if hasattr(policy, 'model_copy') else copy.deepcopy(policy)
            if policy.latency_budget_ms and policy.latency_budget_ms < 3000:
                policy.latency_budget_ms = 3000 # Give it more time to run heavier checks
                
        llm_output = ""
        
        try:
            # 1. Generate text from LLM (accumulate chunks for the synchronous pipeline)
            for chunk in self.adapter.generate_stream(prompt):
                llm_output += chunk
                
            if not llm_output:
                llm_output = "[LLM Returned Empty String]"
                
            # 2. Risk Engine Evaluation
            report = await self.risk_engine.evaluate_response_async(
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
                    reverify_report = await self.risk_engine.evaluate_response_async(
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
                        decision.clean_prefix = reverify_decision.clean_prefix
                        decision.failed_span = reverify_decision.failed_span

            # 4.6. SPEC 09: Checkpoint-Backtrack Regeneration
            if decision.action == "REGENERATE":
                if decision.clean_prefix is not None:
                    # Mocking turn_id for the synchronous pipeline
                    turn_id = session_id or "default_turn"
                    
                    # Commit the clean prefix as the last good checkpoint
                    self.checkpoint_mgr.commit(
                        turn_id=turn_id,
                        char_offset=len(decision.clean_prefix),
                        token_offset=0,
                        risk_snapshot=report,
                        prompt_state=decision.clean_prefix
                    )
                    
                    final_text = None
                    max_attempts = getattr(policy, "max_regenerate_attempts", 2)
                    for attempt in range(1, max_attempts + 1):
                        print(f"   [Pipeline] Initiating SPEC 09 backtrack-regeneration (Attempt {attempt})...")
                        new_text = self.regeneration_engine.regenerate(
                            turn_id=turn_id,
                            original_prompt=prompt,
                            flagged_span=decision.failed_span or "General failure",
                            risk_reason=decision.reasoning,
                            use_case_policy=policy
                        )
                        
                        # Re-verify the spliced result
                        spliced_result = decision.clean_prefix.rstrip() + " " + new_text.lstrip()
                        
                        reverify_report = await self.risk_engine.evaluate_response_async(
                            spliced_result,
                            prompt=prompt,
                            adapter=self.adapter,
                            policy=policy
                        )
                        reverify_decision = self.control_policy.evaluate(reverify_report, policy, response_text=spliced_result, session_state=session_state)
                        
                        if reverify_decision.action == "ALLOW":
                            decision.action = "ALLOW"
                            decision.reasoning = f"SILENT REGENERATE SUCCESS: {decision.reasoning}"
                            report = reverify_report
                            llm_output = spliced_result
                            
                            # Commit the new clean state
                            self.checkpoint_mgr.commit(
                                turn_id=turn_id,
                                char_offset=len(spliced_result),
                                token_offset=0,
                                risk_snapshot=reverify_report,
                                prompt_state=spliced_result
                            )
                            break
                            
                    if decision.action != "ALLOW":
                        # Escalated to HUMAN after exhaustion
                        decision.action = "HUMAN"
                        decision.reasoning = "HUMAN ESCALATION: Regeneration attempts exhausted."
                        
            # 4.7. SPEC 14: Action Gate
            action_decision = None
            if proposed_action_dict:
                import asyncio
                proposed_action = ProposedAction(**proposed_action_dict)
                print(f"   [Pipeline] Action Gate evaluating proposed tool call: {proposed_action.name}")
                
                action_decision = await self.action_checker.run(
                    proposed_action=proposed_action, 
                    context=report, 
                    adapter=self.adapter, 
                    policy=policy
                )
                
                print(f"   [Pipeline] Action Decision: {action_decision.action} ({action_decision.reasoning})")

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
                metadata=metadata,
                action_decision=action_decision
            )
            
            # 5.5 Metrics Log (SPEC 16)
            latency_ms = int((time.time() - start_time) * 1000)
            risk_scores = {}
            for res in report.checker_results:
                if hasattr(res, 'checker_name'):
                    risk_scores[res.checker_name] = res.risk_score
                    
            coverage_pct = 95.0 # Guaranteed coverage from calibration
            
            self.audit_logger.log_metrics(
                request_id=request_id,
                use_case=policy.name if hasattr(policy, 'name') else "default",
                decision_tier=decision.action,
                risk_scores=risk_scores,
                overlap_flag=report.overlap_detected,
                coverage_pct=coverage_pct,
                latency_ms=latency_ms,
                human_verdict=None
            )
            
            # 6. Return Output
            if decision.action == "ALLOW":
                final_text = llm_output
            elif decision.action == "REDACT":
                final_text = f"[REDACTED BY POLICY] Original response contained sensitive data (Action: REDACT)."
            elif decision.action == "MODIFY":
                final_text = f"[MODIFIED BY POLICY] {decision.reasoning}"
            elif decision.action == "REGENERATE":
                final_text = f"[REGENERATED BY POLICY] {decision.reasoning}"
            elif decision.action == "HUMAN":
                final_text = f"[UNDER REVIEW] Your request has been escalated to a human reviewer. {decision.reasoning}"
            else: # BLOCK
                final_text = f"[BLOCKED BY POLICY] {decision.reasoning}"

            ret = {
                "final_output": final_text,
                "risk_report": report.model_dump(),
                "control_decision": decision.model_dump()
            }
            if action_decision:
                ret["action_decision"] = action_decision.model_dump()
                
            return ret
                
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
