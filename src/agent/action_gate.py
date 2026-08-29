import yaml
import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from src.checkers.base import BaseChecker, CheckerResult
from src.policy.schemas import ProposedAction, ActionDecision, FlaggedSpan, FinalRiskReport
from src.engine.semantic_overlap import SemanticOverlapDetector

class ActionCatalogEntry(BaseModel):
    reversibility: str
    blast_radius: str
    requires_confirmation_by_default: bool

class ActionTier0Result(BaseModel):
    needs_tier1: bool
    risk: float
    trigger_reason: str
    overlap_group: Optional[Any] = None

class ActionRiskChecker:
    def __init__(self, catalog_path: str = "src/agent/action_catalog.yaml", overlap_detector: Optional[SemanticOverlapDetector] = None):
        self.catalog = self._load_catalog(catalog_path)
        self.overlap_detector = overlap_detector

    def _load_catalog(self, path: str) -> Dict[str, ActionCatalogEntry]:
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            raw = yaml.safe_load(f) or {}
            
        return {k: ActionCatalogEntry(**v) for k, v in raw.items()}

    def _extract_flagged_spans(self, context: FinalRiskReport) -> List[FlaggedSpan]:
        spans = []
        for result in context.checker_results:
            if result.risk_score > 0 and result.entities:
                for entity in result.entities:
                    span_start = entity.get("span_start", 0)
                    span_end = entity.get("span_end", 0)
                    # reconstruct the span (we need the text, so we assume explanation has it or we just use text)
                    # wait, FinalRiskReport overlap_groups already has the extracted FlaggedSpan objects
                    pass
        # actually, it's easier to just pull from context.overlap_groups if any, 
        # or we just need the flat list of spans. Let's assume pipeline can pass flat spans, 
        # or we can reconstruct them.
        # But wait! The simplest is to just check if the action arguments string overlaps semantically
        # with any of the reasons/spans in the checker results.
        return []

    async def run(self, proposed_action: ProposedAction, context: FinalRiskReport, adapter, policy=None) -> ActionDecision:
        t0_res = self.tier0_gate(proposed_action, context)
        if not t0_res.needs_tier1:
            return ActionDecision(action="EXECUTE", reasoning="Action passed Tier-0 catalog and overlap checks.")
        
        return await self.tier1_check(proposed_action, context, adapter, t0_res)

    def tier0_gate(self, proposed_action: ProposedAction, context: FinalRiskReport) -> ActionTier0Result:
        entry = self.catalog.get(proposed_action.name)
        if not entry:
            # Unknown action, hold by default
            return ActionTier0Result(needs_tier1=True, risk=1.0, trigger_reason="Unknown action not in catalog.")
            
        # 1. Catalog check
        if entry.blast_radius in ("many_entities",) or entry.reversibility == "irreversible":
            return ActionTier0Result(needs_tier1=True, risk=1.0, trigger_reason=f"Catalog rules: blast_radius={entry.blast_radius}, reversibility={entry.reversibility}")
            
        # 2. Overlap check
        if not self.overlap_detector:
            # If no detector, fallback to catalog default
            if entry.requires_confirmation_by_default:
                return ActionTier0Result(needs_tier1=True, risk=0.5, trigger_reason="Catalog requires confirmation by default.")
            return ActionTier0Result(needs_tier1=False, risk=0.0, trigger_reason="")

        # Construct a synthetic span for the action arguments
        # We flatten the JSON values into a string because SentenceTransformers 
        # struggles to match raw JSON syntax to English sentences.
        def _extract_vals(d):
            vals = []
            if isinstance(d, dict):
                for v in d.values():
                    vals.extend(_extract_vals(v))
            elif isinstance(d, list):
                for v in d:
                    vals.extend(_extract_vals(v))
            else:
                vals.append(str(d))
            return vals
            
        flat_args = " ".join(_extract_vals(proposed_action.arguments))
        action_text = f"Action {proposed_action.name} with values {flat_args}"
        
        action_span = FlaggedSpan(
            checker_name="action_monitor",
            text=action_text,
            char_start=0,
            char_end=len(action_text),
            risk_score=0.0,
            risk_reason="proposed_action"
        )
        
        # Extract context spans directly from checker results to check against
        context_spans = []
        for cr in context.checker_results:
            if cr.risk_score > 0:
                # Mock a span for the checker result
                # In a real system, we'd use exact character offsets from the response
                text_val = cr.explanation or str(cr.entities)
                context_spans.append(FlaggedSpan(
                    checker_name=cr.checker_name,
                    text=text_val,
                    char_start=0,
                    char_end=len(text_val),
                    risk_score=cr.risk_score,
                    risk_reason=cr.explanation
                ))
                
        if not context_spans:
            return ActionTier0Result(needs_tier1=False, risk=0.0, trigger_reason="")
            
        # Check for overlaps (using a slightly lower cosine threshold because mapping action args to prose is harder)
        all_spans = [action_span] + context_spans
        groups = self.overlap_detector.find_overlaps(all_spans, char_iou_threshold=1.0, cosine_threshold=0.50)
        
        # See if our action_span is in any group
        for group in groups:
            if any(s.checker_name == "action_monitor" for s in group.spans):
                # Build rich reason string
                flagged_by = [s.checker_name for s in group.spans if s.checker_name != "action_monitor"]
                details = [s.risk_reason for s in group.spans if s.checker_name != "action_monitor"]
                reason_str = f"Action arguments semantically overlap with text flagged by {', '.join(set(flagged_by))} at risk={group.aggregated_risk}. Details: {', '.join(details)}"
                return ActionTier0Result(
                    needs_tier1=True, 
                    risk=group.aggregated_risk, 
                    trigger_reason=reason_str,
                    overlap_group=group
                )

        if entry.requires_confirmation_by_default:
            return ActionTier0Result(needs_tier1=True, risk=0.5, trigger_reason="Catalog requires confirmation by default.")
            
        return ActionTier0Result(needs_tier1=False, risk=0.0, trigger_reason="")

    async def tier1_check(self, proposed_action: ProposedAction, context: FinalRiskReport, adapter, t0_res: ActionTier0Result) -> ActionDecision:
        # LLM Judge pattern per SPEC 14
        prompt = f"""
        You are an Action Risk Judge.
        The system proposed the following action: {proposed_action.name}
        Arguments: {json.dumps(proposed_action.arguments)}
        
        This action was flagged for review because: {t0_res.trigger_reason}
        
        Should we APPROVE (execute), HOLD (require human confirmation), or BLOCK (prevent entirely) this action?
        Output strictly in JSON format: {{"decision": "APPROVE"|"HOLD"|"BLOCK", "rationale": "reason..."}}
        """
        
        try:
            # We assume adapter.generate_once is async since we use AsyncMock for it in tests
            # But the actual Gemini adapter might be synchronous. We'll await if it is a coroutine, otherwise just call it.
            # In pipeline.py, generate_once is synchronous, but we're mocking it with AsyncMock. 
            # To be safe and support AsyncMock, we'll use a wrapper or assume it's async in this new async checker.
            import inspect
            if inspect.iscoroutinefunction(adapter.generate_once):
                response_text = await adapter.generate_once(prompt)
            else:
                response_text = adapter.generate_once(prompt)
                
            # Strip markdown formatting
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
                
            result = json.loads(response_text)
            decision_mapped = result.get("decision", "HOLD")
            rationale = result.get("rationale", "No rationale provided.")
            
            # Translate APPROVE to EXECUTE
            if decision_mapped == "APPROVE":
                decision_mapped = "EXECUTE"
                
            return ActionDecision(action=decision_mapped, reasoning=rationale)
        except Exception as e:
            # Fail safe
            return ActionDecision(action="HOLD", reasoning=f"Failed to parse Tier-1 judge output. Trigger reason: {t0_res.trigger_reason}. Error: {str(e)}")
