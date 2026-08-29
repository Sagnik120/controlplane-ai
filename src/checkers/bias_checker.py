import re
import os
import json
from .base import CheckerResult, BaseChecker, Tier0Result
from src.policy.schemas import FlaggedSpan

class BiasChecker(BaseChecker):
    """
    Evaluates response for bias and stereotyping risk.
    Uses LLM-as-a-judge with a structured rubric, guarded by a keyword pre-filter.
    """
    name = "bias"
    
    bias_patterns = [
        (r'\b(women|men|asians|black people|white people|hispanics|immigrants)\b', r'\b(are typically|are usually|are less|are more|always|never)\b')
    ]
    
    def __init__(self):
        # Load the prompt template
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "bias_judge_prompt.txt")
        with open(prompt_path, "r") as f:
            self.prompt_template = f.read()
            
    def _run_prefilter(self, text: str) -> str:
        """Returns the matched span if a keyword heuristic fires, else None."""
        lower_text = text.lower()
        for demo_re, stereo_re in self.bias_patterns:
            match = re.search(f"{demo_re}.{{0,30}}{stereo_re}|{stereo_re}.{{0,30}}{demo_re}", lower_text)
            if match:
                return match.group(0)
        return None

    def evaluate(self, response_text: str, **kwargs) -> CheckerResult:
        return self.run(response_text, kwargs)
        
    def tier0_gate(self, window_text: str, context: dict) -> Tier0Result:
        if not window_text:
            return Tier0Result(needs_tier1=False, risk=0.0, explanation="Empty.")
            
        policy = context.get('policy')
        always_judge = getattr(policy, 'bias_checker_always_judge', False) if policy else False
        
        # SPEC 11: Budget profile
        if policy and hasattr(policy, 'checker_budget'):
            freq = policy.checker_budget.bias.check_frequency
        else:
            freq = getattr(policy, 'bias_check_frequency', 'every_window') if policy else 'every_window'
        
        # Simulated frequency gate (in a real app, this reads turn_id % N)
        # We will assume if not always_judge and freq isn't every_window, we only run if prefilter fires
        
        flagged_span = self._run_prefilter(window_text)
        
        if not flagged_span and not always_judge and freq != 'every_window':
            return Tier0Result(
                needs_tier1=False, 
                risk=0.0, 
                explanation=f"No bias risks detected (skipped LLM judge via pre-filter / frequency {freq})."
            )
            
        # Passing flagged_span via context
        context['bias_flagged_span'] = flagged_span
        return Tier0Result(needs_tier1=True)

    def tier1_check(self, window_text: str, context: dict) -> CheckerResult:
        try:
            adapter = context.get('adapter')
            flagged_span = context.get('bias_flagged_span')
            
            if not adapter:
                return CheckerResult(
                    checker_name=self.name, 
                    risk_score=1.0, 
                    explanation="Checker failed: No adapter provided for LLM judge."
                )
                
            judge_prompt = self.prompt_template.replace("{response_text}", window_text)
            
            # Call adapter with temperature=0.0
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
                # Malformed JSON handling per 03_Rules.md
                return CheckerResult(
                    checker_name=self.name,
                    risk_score=1.0, # Fatal error risk
                    flagged_span=flagged_span,
                    explanation=f"LLM Judge API/Model Error: {str(e)} | Raw: {judge_response}",
                    is_error=True
                )
                
            verdict = result_json.get("verdict", "UNKNOWN")
            reasoning = result_json.get("reasoning", "No reasoning provided.")
            group = result_json.get("group", None)
            
            if verdict == "BIASED":
                risk_score = 0.7
            else:
                risk_score = 0.0
                
            # We preserve the original flagged_span from the regex if it triggered it, 
            # to help the Modify stage surgically repair it if necessary.
            
            # Note: We need judge_category/judge_severity in CheckerResult if we are extending it,
            # but wait, CheckerResult might not have these fields yet! We need to update base.py.
            # We can just add them via setattr or extend CheckerResult model.
            
            flagged_spans = []
            if risk_score > 0.0:
                span_text = flagged_span if flagged_span else window_text
                start_idx = window_text.lower().find(span_text.lower()) if span_text else 0
                if start_idx == -1:
                    start_idx = 0
                end_idx = start_idx + len(span_text) if span_text else len(window_text)
                
                flagged_spans.append(FlaggedSpan(
                    checker_name=self.name,
                    text=span_text,
                    char_start=start_idx,
                    char_end=end_idx,
                    risk_score=risk_score,
                    risk_reason=group if group else "bias_violation"
                ))
            
            res = CheckerResult(
                checker_name=self.name,
                risk_score=risk_score,
                flagged_span=flagged_span,
                flagged_spans=flagged_spans,
                explanation=reasoning,
                method="llm-as-judge-rubric",
                judge_category=group
            )
            
            return res
            
        except Exception as e:
            return CheckerResult(
                checker_name=self.name,
                risk_score=1.0,
                explanation=f"Checker failed: {str(e)}",
                is_error=True
            )
