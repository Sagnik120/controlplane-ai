import re
from typing import Optional
from .base import CheckerResult

class PerformanceChecker:
    """
    Evaluates response for performance risk (e.g., hallucination, low confidence, self-contradiction).
    Uses heuristic detection of hedging language.
    """
    name = "performance"
    
    # Simple heuristics for hedging/uncertainty
    hedging_phrases = [
        "i am not sure", "i might be wrong", "it is possible that",
        "could be", "i think", "probably", "i don't have real-time",
        "as an ai", "i cannot guarantee", "it seems like"
    ]
    
    def evaluate(self, response_text: str) -> CheckerResult:
        try:
            if not response_text or not response_text.strip():
                # Empty response is a performance failure
                return CheckerResult(
                    checker_name=self.name,
                    risk_score=1.0,
                    explanation="Response is empty."
                )
                
            lower_text = response_text.lower()
            
            # 1. Check for hedging
            for phrase in self.hedging_phrases:
                if phrase in lower_text:
                    # High risk of low confidence or hallucination deflection
                    return CheckerResult(
                        checker_name=self.name,
                        risk_score=0.7,
                        flagged_span=phrase,
                        explanation=f"Detected low-confidence/hedging language: '{phrase}'"
                    )
            
            # 2. Check for contradiction (very naive heuristic for demo: "is X, but is not X")
            # In a real system, this would use a small classifier. Here we just look for "but" near a negation.
            if re.search(r'\b(is|are|was|were)\b.{1,20}\b(but|however)\b.{1,20}\b(not|never)\b', lower_text):
                return CheckerResult(
                    checker_name=self.name,
                    risk_score=0.9,
                    flagged_span="contradictory clause pattern",
                    explanation="Detected potential self-contradiction pattern."
                )
            
            return CheckerResult(
                checker_name=self.name,
                risk_score=0.0,
                explanation="No performance risks detected (high confidence)."
            )
            
        except Exception as e:
            # Rule 4 from 03_Rules: Fail gracefully and conservatively
            return CheckerResult(
                checker_name=self.name,
                risk_score=1.0,
                explanation=f"Checker failed: {str(e)}"
            )
