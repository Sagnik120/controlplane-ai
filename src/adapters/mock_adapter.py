from typing import Iterator
import time
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
            
        elif "hallucination" in lower_prompt or "wrong" in lower_prompt:
            return _stream("The capital of France is actually Berlin, which was established in 1999 by the United Nations.")
            
        else:
            return _stream("This is a clean, helpful, and factually correct response. The sky is blue and water is wet.")
