import re
from .base import CheckerResult

class SafetyChecker:
    """
    Evaluates response for safety risks (e.g., violence, self-harm, illicit activities).
    Uses pattern-based detection.
    """
    name = "safety"
    
    # Highly simplified list for demo purposes
    unsafe_keywords = [
        "kill", "murder", "bomb", "terrorist", "suicide", "hack into", "steal",
        "how to build a weapon"
    ]
    
    def evaluate(self, response_text: str) -> CheckerResult:
        try:
            if not response_text:
                return CheckerResult(checker_name=self.name, risk_score=0.0, explanation="Empty.")
                
            lower_text = response_text.lower()
            
            for keyword in self.unsafe_keywords:
                if keyword in lower_text:
                    return CheckerResult(
                        checker_name=self.name,
                        risk_score=0.95,
                        flagged_span=keyword,
                        explanation=f"Unsafe keyword detected: '{keyword}'"
                    )
            
            return CheckerResult(
                checker_name=self.name,
                risk_score=0.0,
                explanation="No safety risks detected."
            )
            
        except Exception as e:
            return CheckerResult(
                checker_name=self.name,
                risk_score=1.0,
                explanation=f"Checker failed: {str(e)}"
            )
