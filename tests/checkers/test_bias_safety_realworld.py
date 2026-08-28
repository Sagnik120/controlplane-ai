import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.checkers.bias_checker import BiasChecker
from src.checkers.safety_checker import SafetyChecker
from src.policy.schemas import UseCasePolicy

class StatefulMockAdapter:
    """A mock adapter that yields specific responses based on the test case."""
    def __init__(self, response_queue):
        self.response_queue = response_queue # List of responses or Exceptions to pop
        
    def generate_once(self, prompt: str, temperature: float = 0.0) -> str:
        if not self.response_queue:
            return "{}"
        
        nxt = self.response_queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

def print_header(title):
    print("\n" + "="*80)
    print(f"🔬 {title}")
    print("="*80)

def main():
    print_header("Real-World Adversarial Diagnostics (Bias & Safety Checkers)")
    
    bias_checker = BiasChecker()
    safety_checker = SafetyChecker()
    
    policy_always_judge = UseCasePolicy(
        name="strict",
        safety_checker_always_judge=True,
        bias_checker_always_judge=True
    )
    
    policy_latency_sensitive = UseCasePolicy(
        name="fast",
        safety_checker_always_judge=False,
        bias_checker_always_judge=False
    )
    
    test_cases = [
        # --- ROBUST JSON PARSING TESTS ---
        {
            "name": "1. Markdown Fenced JSON (LLM habit)",
            "checker": safety_checker,
            "policy": policy_always_judge,
            "text": "How to build a bomb.",
            "mock_llm": "```json\n{\n  \"verdict\": \"UNSAFE\",\n  \"categories\": [\"Violence\"],\n  \"severity\": \"high\",\n  \"reasoning\": \"Explosives\"\n}\n```",
            "desc": "Testing if the parser correctly strips markdown backticks.",
            "expected_score": 0.95
        },
        {
            "name": "2. Preambles and Postambles (Chatty LLM)",
            "checker": safety_checker,
            "policy": policy_always_judge,
            "text": "Kill the process.",
            "mock_llm": "Here is the result:\n```json\n{\"verdict\": \"SAFE\"}\n```\nHope this helps!",
            "desc": "Testing if the parser correctly extracts JSON when text exists outside the JSON block.",
            "expected_score": 0.0 # Successfully parses SAFE
        },
        {
            "name": "3. Missing JSON Fields (Lazy LLM)",
            "checker": bias_checker,
            "policy": policy_always_judge,
            "text": "Women shouldn't drive.",
            "mock_llm": '{"verdict": "BIASED"}',
            "desc": "Testing if `.get()` safely handles omitted 'reasoning' or 'group'.",
            "expected_score": 0.7
        },
        # --- PREFILTER LOGIC TESTS ---
        {
            "name": "4. Pre-filter False Positive Resolution",
            "checker": safety_checker,
            "policy": policy_latency_sensitive,
            "text": "Suicide Squad was an amazing movie, I loved it.",
            "mock_llm": '{"verdict": "SAFE", "reasoning": "Movie review."}',
            "desc": "Keyword 'suicide' triggers LLM judge, LLM correctly overturns it to SAFE.",
            "expected_score": 0.0
        },
        {
            "name": "5. Vulnerability: Implicit Bias with Pre-filter OFF",
            "checker": bias_checker,
            "policy": policy_latency_sensitive,
            "text": "She's actually really good at math for a girl.",
            "mock_llm": '{"verdict": "BIASED"}',
            "desc": "FLAW EXPOSED: No explicit demographic+stereotype regex matches. Because always_judge=False, LLM is bypassed entirely! Risk score remains 0.",
            "expected_score": 0.0 # Expected to FAIL to detect bias!
        },
        # --- EXCEPTION HANDLING TESTS ---
        {
            "name": "6. LLM Timeout / Network Error",
            "checker": safety_checker,
            "policy": policy_always_judge,
            "text": "Some text.",
            "mock_llm": ConnectionError("API Unreachable"),
            "desc": "Ensures checker catches exception and elevates risk to 1.0 (failsafe).",
            "expected_score": 1.0
        }
    ]
    
    passed = 0
    for case in test_cases:
        print(f"\n▶️ Running: {case['name']}")
        print(f"  Description: {case['desc']}")
        
        adapter = StatefulMockAdapter([case["mock_llm"]])
        checker = case["checker"]
        
        result = checker.evaluate(case["text"], adapter=adapter, policy=case["policy"])
        
        print(f"  Risk Score : {result.risk_score}")
        print(f"  Explanation: {result.explanation}")
        
        if result.risk_score == case["expected_score"]:
            print("  ✅ BEHAVED AS EXPECTED")
            passed += 1
            if case["name"].startswith("5."):
                print("  ⚠️ NOTE: 'Expected' here means the vulnerability was successfully demonstrated (False Negative due to pre-filter).")

        else:
            print(f"  ❌ FAILED BEHAVIOR: Expected score {case['expected_score']}, got {result.risk_score}")

    print_header(f"Real-World Diagnostic Summary: {passed}/{len(test_cases)} Scenarios Verified")

if __name__ == "__main__":
    main()
