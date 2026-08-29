import os
from google import genai
from google.genai import types
from typing import Iterator
from .base_adapter import BaseLLMAdapter

class GeminiAdapter(BaseLLMAdapter):
    """
    Adapter for Google's Gemini API using the modern google-genai SDK.
    """
    
    def __init__(self, model_name: str = "gemini-3.6-flash"):
        # Relies on GEMINI_API_KEY being present in os.environ (loaded via python-dotenv in the app)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in your .env file.")
        
        # The genai.Client automatically picks up GEMINI_API_KEY from os.environ, 
        # but we pass it explicitly here just to be safe.
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        
    def generate_stream(self, prompt: str) -> Iterator[str]:
        try:
            response = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=prompt
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            # Provide a fallback error chunk so the stream doesn't crash silently
            yield f"[Error generating response from Gemini: {str(e)}]"

    def generate_once(self, prompt: str, temperature: float = 1.0) -> str:
        try:
            config = types.GenerateContentConfig(temperature=temperature)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text if response.text else ""
        except Exception as e:
            return f"[Error generating response from Gemini: {str(e)}]"
