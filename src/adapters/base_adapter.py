from abc import ABC, abstractmethod
from typing import Iterator

class BaseLLMAdapter(ABC):
    """
    Abstract base class for all LLM provider adapters.
    Ensures a model-agnostic interface across different backends.
    """
    
    @abstractmethod
    def generate_stream(self, prompt: str) -> Iterator[str]:
        """
        Generates a response from the LLM, streaming chunks of text.
        
        Args:
            prompt (str): The input prompt to send to the LLM.
            
        """
        pass

    @abstractmethod
    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        """
        Generates a full response from the LLM in a single non-streaming call.
        Useful for stochastic sampling.
        
        Args:
            prompt (str): The input prompt to send to the LLM.
            temperature (float): The sampling temperature.
            
        Returns:
            str: The full generated text.
        """
        pass
