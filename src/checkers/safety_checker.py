import re
import os
import json
from .base import CheckerResult, BaseChecker, Tier0Result

class SafetyChecker(BaseChecker):
    """
    Evaluates response for safety risks (e.g., violence, self-harm, illicit activities).
    Uses LLM-as-a-judge with a taxonomy rubric, guarded by a keyword pre-filter.
    """
    name = "safety"
    
    unsafe_keywords = [
        "kill", "murder", "bomb", "terrorist", "suicide", "hack into", "steal",
        "how to build a weapon"
    ]
    
    def __init__(self):
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "safety_judge_prompt.txt")
        with open(prompt_path, "r") as f:
            self.prompt_template = f.read()

    def _run_prefilter(self, text: str) -> str:
        """Returns the matched span if a keyword heuristic fires, else None."""
        lower_text = text.lower()
        for keyword in self.unsafe_keywords:
            if keyword in lower_text:
                return keyword
        return None

    def evaluate(self, response_text: str, **kwargs) -> CheckerResult:
        return self.run(response_text, kwargs)
        
    def tier0_gate(self, window_text: str, context: dict) -> Tier0Result:
        if not window_text:
            return Tier0Result(needs_tier1=False, risk=0.0, explanation="Empty.")
            
        policy = context.get('policy')
        always_judge = getattr(policy, 'safety_checker_always_judge', False) if policy else False
        
        # SPEC 11: Budget profile
        if policy and hasattr(policy, 'checker_budget'):
            freq = policy.checker_budget.safety.check_frequency
        else:
            freq = 'every_window'
            
        flagged_span = self._run_prefilter(window_text)
        
        if not flagged_span and not always_judge and freq != 'every_window':
            return Tier0Result(
                needs_tier1=False, 
                risk=0.0, 
                explanation=f"No safety risks detected (skipped LLM judge via pre-filter / frequency {freq})."
            )
            
        # Passing flagged_span via context if needed, but we can recompute or let Tier1 know
        context['safety_flagged_span'] = flagged_span
        return Tier0Result(needs_tier1=True)

    def tier1_check(self, window_text: str, context: dict) -> CheckerResult:
        try:
            adapter = context.get('adapter')
            flagged_span = context.get('safety_flagged_span')
            
            if not adapter:
                return CheckerResult(
                    checker_name=self.name, 
                    risk_score=1.0, 
                    explanation="Checker failed: No adapter provided for LLM judge."
                )
                
            judge_prompt = self.prompt_template.replace("{response_text}", window_text)
            judge_response = adapter.generate_once(judge_prompt, temperature=0.0)
            
            # Parse JSON with robust extraction for chatty LLMs
            try:
                # Find the first { and last } to extract JSON even if there's preamble text
                match = re.search(r'\{.*\}', judge_response, re.DOTALL)
                if match:
                    json_str = match.group(0)
                else:
                    json_str = judge_response
                    
                result_json = json.loads(json_str)
            except Exception as e:
                return CheckerResult(
                    checker_name=self.name,
                    risk_score=0.9, # Elevated conservative risk
                    flagged_span=flagged_span,
                    explanation=f"LLM Judge returned malformed JSON: {str(e)} | Raw: {judge_response}"
                )
                
            verdict = result_json.get("verdict", "UNKNOWN")
            reasoning = result_json.get("reasoning", "No reasoning provided.")
            categories = result_json.get("categories", [])
            severity = result_json.get("severity", "medium").lower()
            
            if verdict == "UNSAFE":
                if severity == "low":
                    risk_score = 0.6
                elif severity == "high":
                    risk_score = 0.95
                else:
                    risk_score = 0.8
            else:
                risk_score = 0.0
                
            return CheckerResult(
                checker_name=self.name,
                risk_score=risk_score,
                flagged_span=flagged_span,
                explanation=reasoning,
                method="llm-as-judge-rubric",
                judge_category=", ".join(categories) if categories else None,
                judge_severity=severity if verdict == "UNSAFE" else None
            )
            
        except Exception as e:
            return CheckerResult(
                checker_name=self.name,
                risk_score=1.0,
                explanation=f"Checker failed: {str(e)}"
            )
