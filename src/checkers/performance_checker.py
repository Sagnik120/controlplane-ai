import concurrent.futures
import threading
from typing import Optional, List, Dict, Any
from .base import CheckerResult, BaseChecker, Tier0Result
from spacy.lang.en import English

try:
    import spacy
    import warnings
    # Suppress the PyTorch/numpy non-writable tensor warning from bert_score
    warnings.filterwarnings("ignore", message="The given NumPy array is not writable")
    from selfcheckgpt.modeling_selfcheck import SelfCheckNLI, SelfCheckBERTScore
except ImportError:
    spacy = None
    SelfCheckNLI = None
    SelfCheckBERTScore = None

class PerformanceChecker(BaseChecker):
    """
    Evaluates response for performance risk (hallucination) using SelfCheckGPT
    (zero-resource black-box hallucination detection via stochastic sampling).
    """
    name = "performance"
    
    def __init__(self):
        if spacy is None or SelfCheckNLI is None:
            raise ImportError("selfcheckgpt and spacy are required for PerformanceChecker")
            
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            self.nlp = English()
            self.nlp.add_pipe("sentencizer")
            
        # Initialize models (CPU for demo/hackathon to avoid GPU mem issues)
        self.selfcheck_nli = SelfCheckNLI(device="cpu")
        self.selfcheck_bertscore = SelfCheckBERTScore(default_model="en")
        
        # Latency mitigation: Cache samples by prompt prefix
        self._sample_cache = {}
        
        # PyTorch thread-safety lock for concurrent evaluations
        self._model_lock = threading.Lock()

    def _cheap_uncertainty(self, text: str) -> float:
        """
        Simulated Tier-0 gate.
        In production, this would use token entropy or top-2 logit margin from the streaming logprobs.
        Here we mock it based on sentence length/complexity for demonstration.
        """
        if not text:
            return 0.0
        words = text.split()
        if len(words) < 10:
            return 0.1 # Highly confident
        elif len(words) < 50:
            return 0.4 # Uncertain band
        else:
            return 0.7 # High uncertainty

    def evaluate(self, response_text: str, **kwargs) -> CheckerResult:
        # For legacy compatibility, call run
        return self.run(response_text, kwargs)
        
    def tier0_gate(self, window_text: str, context: dict) -> Tier0Result:
        if not window_text or not window_text.strip() or window_text == "[LLM Returned Empty String]":
            return Tier0Result(needs_tier1=False, risk=1.0, explanation="Response is empty.")
            
        policy = context.get('policy')
        tier0_band_low = getattr(policy, "tier0_uncertain_band_low", 0.20) if policy else 0.20
        tier0_score = self._cheap_uncertainty(window_text)
        
        if tier0_score < tier0_band_low:
            return Tier0Result(
                needs_tier1=False, 
                risk=tier0_score, 
                explanation=f"Tier-0 Gate confident (score {tier0_score}). Bypassed Tier-1 SelfCheckGPT."
            )
        return Tier0Result(needs_tier1=True)

    def tier1_check(self, window_text: str, context: dict) -> CheckerResult:
        try:
            adapter = context.get('adapter')
            prompt = context.get('prompt', "")
            policy = context.get('policy')
            
            if not adapter or not prompt:
                # Return dummy check if not wired properly yet
                return CheckerResult(
                    checker_name=self.name,
                    risk_score=0.0,
                    explanation="Adapter or prompt missing, skipped SelfCheckGPT."
                )

            # Extract config knobs
            n_samples = 3
            sampling_temp = 1.0
            nli_weight = 0.7
            bertscore_weight = 0.3
            
            if policy:
                n_samples = getattr(policy, "performance_n_samples", n_samples)
                sampling_temp = getattr(policy, "performance_sampling_temperature", sampling_temp)
                nli_weight = getattr(policy, "performance_nli_weight", nli_weight)
                bertscore_weight = getattr(policy, "performance_bertscore_weight", bertscore_weight)

            # 1. Adaptive Triggering / Caching
            # Cache the full result if prompt and response are identical
            full_cache_key = f"{hash(prompt)}_{hash(window_text)}_{n_samples}_{sampling_temp}"
            if hasattr(self, "_result_cache") and full_cache_key in self._result_cache:
                return self._result_cache[full_cache_key]

            cache_key = f"{prompt[:100]}_{n_samples}_{sampling_temp}"
            if cache_key in self._sample_cache:
                samples = self._sample_cache[cache_key]
            else:
                # 2. Parallel Sampling for Latency Mitigation
                samples = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=n_samples) as executor:
                    futures = [executor.submit(adapter.generate_once, prompt, sampling_temp) for _ in range(n_samples)]
                    for future in concurrent.futures.as_completed(futures):
                        res = future.result()
                        if res:
                            samples.append(res)
                self._sample_cache[cache_key] = samples
                
            if not samples:
                return CheckerResult(
                    checker_name=self.name,
                    risk_score=1.0,
                    explanation="Failed to generate stochastic samples (adapter degradation)."
                )

            # 3. Sentence Segmentation
            doc = self.nlp(window_text)
            sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
            
            if not sentences:
                return CheckerResult(
                    checker_name=self.name,
                    risk_score=0.0,
                    explanation="No valid sentences found."
                )

            # 4. Predict Hallucination
            with self._model_lock:
                sent_scores_nli = self.selfcheck_nli.predict(sentences=sentences, sampled_passages=samples)
                sent_scores_bertscore = self.selfcheck_bertscore.predict(sentences=sentences, sampled_passages=samples)

            sentence_scores = []
            max_risk = 0.0
            flagged_span = None
            
            for i, sent in enumerate(sentences):
                # Weighted ensemble of NLI and BERTScore
                score = (nli_weight * sent_scores_nli[i]) + (bertscore_weight * sent_scores_bertscore[i])
                max_risk = max(max_risk, score)
                
                span_start = window_text.find(sent)
                span_end = span_start + len(sent) if span_start != -1 else -1
                
                sentence_scores.append({
                    "sentence": sent,
                    "span_start": span_start,
                    "span_end": span_end,
                    "inconsistency_score": float(score)
                })
                
                # Save the highest risk sentence as the flagged_span for Risk Engine overlaps
                if score == max_risk and score > 0.4:
                    flagged_span = sent

            result = CheckerResult(
                checker_name=self.name,
                risk_score=round(max_risk, 3),
                flagged_span=flagged_span,
                explanation=f"SelfCheckGPT detected hallucination risk of {round(max_risk, 3)}.",
                sentence_scores=sentence_scores,
                confidence=round(1.0 - max_risk, 3),
                method="selfcheckgpt-nli+bertscore",
                tier=1,
                ran_selfcheck=True
            )
            
            # Save to full result cache
            if not hasattr(self, "_result_cache"):
                self._result_cache = {}
            self._result_cache[full_cache_key] = result
            
            return result
            
        except Exception as e:
            return CheckerResult(
                checker_name=self.name,
                risk_score=1.0,
                explanation=f"Checker failed: {str(e)}"
            )
