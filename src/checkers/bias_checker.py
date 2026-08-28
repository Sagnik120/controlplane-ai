import re
import os
import json
from .base import CheckerResult

class BiasChecker:
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

    def evaluate(self, response_text: str, prompt: str = "", adapter=None, policy=None) -> CheckerResult:
        try:
            if not response_text:
                return CheckerResult(checker_name=self.name, risk_score=0.0, explanation="Empty.")
                
            # 1. Pre-filter Check
            flagged_span = self._run_prefilter(response_text)
            
            # 2. Check Policy (Do we skip the LLM judge?)
            always_judge = False
            if policy and hasattr(policy, 'bias_checker_always_judge'):
                always_judge = policy.bias_checker_always_judge
                
            if not flagged_span and not always_judge:
                # Fast path: deemed safe by pre-filter
                return CheckerResult(
                    checker_name=self.name,
                    risk_score=0.0,
                    explanation="No bias risks detected (skipped LLM judge via pre-filter)."
                )
                
            # 3. LLM-as-a-Judge Evaluation
            if not adapter:
                return CheckerResult(
                    checker_name=self.name, 
                    risk_score=1.0, 
                    explanation="Checker failed: No adapter provided for LLM judge."
                )
                
            judge_prompt = self.prompt_template.replace("{response_text}", response_text)
            
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
                    risk_score=0.9, # Elevated conservative risk
                    flagged_span=flagged_span,
                    explanation=f"LLM Judge returned malformed JSON: {str(e)} | Raw: {judge_response}"
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
            
            res = CheckerResult(
                checker_name=self.name,
                risk_score=risk_score,
                flagged_span=flagged_span,
                explanation=reasoning,
                method="llm-as-judge-rubric",
                judge_category=group
            )
            
            return res
            
        except Exception as e:
            return CheckerResult(
                checker_name=self.name,
                risk_score=1.0,
                explanation=f"Checker failed: {str(e)}"
            )
