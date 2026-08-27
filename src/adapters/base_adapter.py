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
            
        Returns:
            Iterator[str]: An iterator yielding chunks of the generated response.
        """
        pass
