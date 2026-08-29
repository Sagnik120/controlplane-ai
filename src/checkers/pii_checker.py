import os
import transformers
from typing import List, Dict, Any, Optional

try:
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, EntityRecognizer, RecognizerResult
    from presidio_analyzer.nlp_engine import NlpEngineProvider
except ImportError:
    AnalyzerEngine = None
    RecognizerRegistry = None
    EntityRecognizer = object
    RecognizerResult = None
    NlpEngineProvider = None

from .base import CheckerResult, BaseChecker, Tier0Result
from src.policy.schemas import FlaggedSpan
import re

class PiiranhaRecognizer(EntityRecognizer):
    """
    Custom Presidio EntityRecognizer wrapping iiiorg/piiranha-v1-detect-personal-information
    """
    def __init__(self, supported_entities=None):
        if supported_entities is None:
            # Common labels from piiranha
            supported_entities = ["PERSON", "LOCATION", "ORGANIZATION", "PASSWORD", "IP_ADDRESS", "EMAIL", "PHONE_NUMBER", "SSN"]
        super().__init__(supported_entities=supported_entities, name="PiiranhaRecognizer")
        # Load HuggingFace pipeline
        self.pipeline = transformers.pipeline(
            "ner", 
            model="iiiorg/piiranha-v1-detect-personal-information",
            aggregation_strategy="simple"
        )
        
    def load(self):
        pass

    def analyze(self, text: str, entities: List[str], nlp_artifacts=None):
        results = []
        if not text:
            return results
        
        preds = self.pipeline(text)
        for pred in preds:
            entity_group = pred.get("entity_group", pred.get("entity"))
            if not entities or entity_group in entities:
                res = RecognizerResult(
                    entity_type=entity_group,
                    start=pred["start"],
                    end=pred["end"],
                    score=pred["score"]
                )
                results.append(res)
        return results

class PiiChecker(BaseChecker):
    name = "pii"
    
    def __init__(self, analyzer=None):
        if AnalyzerEngine is None:
            raise ImportError("presidio_analyzer is not installed")
            
        if analyzer:
            self.analyzer = analyzer
        else:
            # Initialize custom registry
            registry = RecognizerRegistry()
            registry.load_predefined_recognizers()
            
            # Add custom Piiranha NER
            piiranha = PiiranhaRecognizer()
            registry.add_recognizer(piiranha)
            
            # Add obfuscated phone recognizer to demonstrate context-boosting edge case
            from presidio_analyzer import PatternRecognizer, Pattern
            obfuscated_phone_pattern = Pattern(
                name="obfuscated_phone",
                regex=r"(?i)\b(?:\d|one|two|three|four|five|six|seven|eight|nine|zero)(?:[\s\W]*(?:\d|one|two|three|four|five|six|seven|eight|nine|zero)){6,14}\b",
                score=0.3  # Base score 0.3 + 0.35 context boost = 0.65 (passes 0.6 threshold)
            )
            obfuscated_phone_recognizer = PatternRecognizer(
                supported_entity="PHONE_NUMBER", 
                patterns=[obfuscated_phone_pattern],
                context=["phone", "call", "mobile", "telephone"] # Removed generic "number"
            )
            registry.add_recognizer(obfuscated_phone_recognizer)
            
            # Add India PII patterns (PAN and Aadhaar)
            india_pan_pattern = Pattern(
                name="india_pan",
                regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
                score=0.8
            )
            india_pan_recognizer = PatternRecognizer(
                supported_entity="IN_PAN",
                patterns=[india_pan_pattern],
                context=["pan", "tax", "india"]
            )
            registry.add_recognizer(india_pan_recognizer)
            
            india_aadhaar_pattern = Pattern(
                name="india_aadhaar",
                regex=r"\b\d{4}\s\d{4}\s\d{4}\b",
                score=0.8
            )
            india_aadhaar_recognizer = PatternRecognizer(
                supported_entity="IN_AADHAAR",
                patterns=[india_aadhaar_pattern],
                context=["aadhaar", "uidai", "india", "id"]
            )
            registry.add_recognizer(india_aadhaar_recognizer)
            
            # Setup NLP Engine for Presidio (default spacy)
            provider = NlpEngineProvider(nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}]
            })
            nlp_engine = provider.create_engine()
            
            self.analyzer = AnalyzerEngine(registry=registry, nlp_engine=nlp_engine, supported_languages=["en"])
            
    def evaluate(self, response_text: str, **kwargs) -> CheckerResult:
        # For legacy compatibility, call run
        return self.run(response_text, kwargs)
        
    def tier0_gate(self, window_text: str, context: dict) -> Tier0Result:
        if not window_text:
            return Tier0Result(needs_tier1=False, risk=0.0, explanation="Empty.")
            
        policy = context.get('policy')
        if policy and hasattr(policy, 'checker_budget'):
            mode = policy.checker_budget.pii.tier0_mode
        else:
            mode = getattr(policy, 'pii_tier0_mode', 'always_full_ner') if policy else 'always_full_ner'
        
        if mode == 'always_full_ner':
            return Tier0Result(needs_tier1=True)
            
        # pattern_only_unless_hit
        # Fast regex for numbers/emails/capitalized words
        has_digit_sequence = bool(re.search(r'\d{3,}', window_text))
        has_email = bool(re.search(r'\S+@\S+', window_text))
        has_capitalized_run = bool(re.search(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', window_text))
        
        if has_digit_sequence or has_email or has_capitalized_run:
            return Tier0Result(needs_tier1=True)
            
        return Tier0Result(
            needs_tier1=False, 
            risk=0.0, 
            explanation="Tier-0 Regex gate confident: No entity-shaped tokens detected."
        )

    def tier1_check(self, window_text: str, context: dict) -> CheckerResult:
        try:
            policy = context.get('policy')
            
            # Default allowlist if no policy provided
            allowlist = ["EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD", "PERSON", "EMAIL", "SSN", "IN_PAN", "IN_AADHAAR"]
            min_confidence = 0.5
            
            if policy and hasattr(policy, 'pii_entity_allowlist') and policy.pii_entity_allowlist:
                allowlist = list(set(policy.pii_entity_allowlist + ["IN_PAN", "IN_AADHAAR"]))
                min_confidence = getattr(policy, 'pii_min_confidence', min_confidence)
                
            results = self.analyzer.analyze(
                text=window_text,
                language="en",
                entities=allowlist
            )
            
            # Filter by min_confidence
            valid_results = [r for r in results if r.score >= min_confidence]
            
            if not valid_results:
                return CheckerResult(checker_name=self.name, risk_score=0.0, explanation="No PII risks detected.", entities=[])
                
            # Extract entities
            entities = []
            for r in valid_results:
                entities.append({
                    "entity_type": r.entity_type,
                    "text": window_text[r.start:r.end],
                    "span_start": r.start,
                    "span_end": r.end,
                    "confidence": float(r.score),
                    "detection_method": "presidio_hybrid_piiranha"
                })
                
            # Calculate Noisy-OR aggregation for risk score: 1 - product(1 - c_i)
            prob_safe = 1.0
            highest_score = 0.0
            flagged_span = None
            flagged_spans = []
            
            for r in valid_results:
                prob_safe *= (1.0 - float(r.score))
                if r.score > highest_score:
                    highest_score = float(r.score)
                    flagged_span = window_text[r.start:r.end]
                
                flagged_spans.append(FlaggedSpan(
                    checker_name=self.name,
                    text=window_text[r.start:r.end],
                    char_start=r.start,
                    char_end=r.end,
                    risk_score=float(r.score),
                    risk_reason=r.entity_type
                ))
                    
            risk_score = 1.0 - prob_safe
            
            return CheckerResult(
                checker_name=self.name,
                risk_score=round(risk_score, 3),
                flagged_span=flagged_span,
                flagged_spans=flagged_spans,
                explanation=f"Detected {len(valid_results)} PII entities. Noisy-OR aggregated risk: {round(risk_score, 3)}",
                entities=entities,
                method="presidio_hybrid_piiranha"
            )
            
        except Exception as e:
            return CheckerResult(
                checker_name=self.name,
                risk_score=1.0,
                explanation=f"Checker failed: {str(e)}"
            )
