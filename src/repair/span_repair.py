try:
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import RecognizerResult
except ImportError:
    AnonymizerEngine = None

from src.adapters.base_adapter import BaseLLMAdapter

class SpanRepairEngine:
    def __init__(self):
        self.anonymizer = AnonymizerEngine() if AnonymizerEngine else None
        
    def repair_via_anonymizer(self, span_text: str, entity_type: str = "PII") -> str:
        """
        Deterministically replaces PII spans using Presidio Anonymizer.
        In this micro-repair architecture, we just anonymize the specific span text.
        """
        if not self.anonymizer:
            return f"<{entity_type}>"
            
        # We pretend the entire span_text is the entity, so start=0, end=len
        res = RecognizerResult(entity_type=entity_type, start=0, end=len(span_text), score=1.0)
        
        anonymized_result = self.anonymizer.anonymize(
            text=span_text,
            analyzer_results=[res]
        )
        return anonymized_result.text

    def repair_via_llm(self, span_text: str, context: str, prompt: str, reason: str, adapter: BaseLLMAdapter) -> str:
        """
        Uses a micro-prompt to ask the LLM to surgically rewrite just the flawed sentence.
        """
        repair_prompt = f"""You are correcting ONE flawed sentence within an otherwise correct response.
Original question: {prompt}
Full response (for context only, do not repeat it): {context}
Flawed sentence to fix: "{span_text}"
Reason it was flagged: {reason}

Rewrite ONLY this sentence to be accurate/safe/non-identifying, in the same style and tense as the surrounding text. If the sentence cannot be repaired without fabricating a fact, replace it with a neutral statement that the detail is unconfirmed. 
Output ONLY the replacement sentence, nothing else."""

        # Use low temperature for deterministic, careful repair
        repaired_text = adapter.generate_once(repair_prompt, temperature=0.2).strip()
        
        # Guard against the LLM repeating the whole prompt or apologizing
        if "Flawed sentence to fix:" in repaired_text or "Here is the rewritten" in repaired_text:
            # Fallback to a neutral string if the LLM fails instruction following
            return "[Information removed for safety/accuracy]"
            
        return repaired_text
