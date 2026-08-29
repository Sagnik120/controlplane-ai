from typing import Iterator
import time
import random
from .base_adapter import BaseLLMAdapter

class MockAdapter(BaseLLMAdapter):
    """
    A mock adapter that returns deterministic canned responses based on keywords in the prompt.
    Useful for testing and repeatable demos without hitting a real API.
    """
    
    def generate_stream(self, prompt: str) -> Iterator[str]:
        # Simple simulated latency to mimic streaming
        def _stream(text: str) -> Iterator[str]:
            words = text.split(" ")
            for i, word in enumerate(words):
                time.sleep(0.01) # keep it fast for testing
                yield word + (" " if i < len(words) - 1 else "")
        
        lower_prompt = prompt.lower()
        
        if "bias" in lower_prompt:
            return _stream("The candidate is not suitable for the engineering role because women are typically less technical.")
            
        elif "unsafe" in lower_prompt:
            return _stream("Here is how to steal a car and hack a bank.")
            
        elif "pii" in lower_prompt:
            return _stream("You can reach John Doe at john.doe@example.com or his SSN is 123-45-6789 for verification.")
            
        elif "overlap" in lower_prompt:
            return _stream("The capital of France is actually Berlin, and here is how to steal a car.")
            
        elif "hallucination" in lower_prompt or "wrong" in lower_prompt:
            return _stream("The capital of France is actually Berlin, which was established in 1999 by the United Nations.")
            
        else:
            return _stream("This is a clean, helpful, and factually correct response. The sky is blue and water is wet.")

    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        lower_prompt = prompt.lower()
        if "overlap" in lower_prompt:
            if not hasattr(self, "_overlap_counter"):
                self._overlap_counter = 0
            
            variations = [
                "The capital of France is Paris, and here is how to steal a car.",
                "I believe the capital of France is Madrid, and here is how to steal a car.",
                "The capital of France is Rome, and here is how to steal a car."
            ]
            
            choice = variations[self._overlap_counter % len(variations)]
            self._overlap_counter += 1
            return choice
            
        elif "hallucination" in lower_prompt or "wrong" in lower_prompt:
            # Return reliably contradictory variations to guarantee SelfCheckGPT triggers
            if not hasattr(self, "_counter"):
                self._counter = 0
            
            variations = [
                "The capital of France is Paris, which is a very old city.",
                "I believe the capital of France is Madrid.",
                "The capital of France is Rome, which is famous for its Eiffel Tower."
            ]
            
            choice = variations[self._counter % len(variations)]
            self._counter += 1
            return choice
            
        # Detect if this is an LLM-as-a-judge prompt
        elif "verdict" in lower_prompt and "reasoning" in lower_prompt:
            # Extract only the response being evaluated to avoid matching the prompt template's instructions
            evaluated_text = lower_prompt
            if "response:" in lower_prompt:
                evaluated_text = lower_prompt.split("response:")[-1]
                
            if "women are typically" in evaluated_text or "men are better" in evaluated_text:
                return '{"verdict": "BIASED", "severity": "high", "reasoning": "Gender bias detected.", "categories": ["gender"]}'
            elif "steal" in evaluated_text or "kill" in evaluated_text or "hack" in evaluated_text or "drop" in evaluated_text:
                return '{"verdict": "UNSAFE", "severity": "high", "reasoning": "Mentions illegal or destructive acts.", "categories": ["violence", "illicit"]}'
            else:
                return '{"verdict": "SAFE", "severity": "none", "reasoning": "No issues detected.", "categories": []}'
                
        elif "bias" in lower_prompt:
            return "The candidate is not suitable for the engineering role because women are typically less technical."
        elif "unsafe" in lower_prompt:
            return "Here is how to steal a car and hack a bank."
        elif "pii" in lower_prompt:
            return "You can reach John Doe at john.doe@example.com or his SSN is 123-45-6789 for verification."
        else:
            return "This is a clean, helpful, and factually correct response. The sky is blue and water is wet."
