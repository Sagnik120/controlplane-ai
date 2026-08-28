# Spec 02 — Upgrade `pii_checker.py` with a Presidio-Style Hybrid Detection Pipeline

**Status:** Ready to implement
**Touches:** `src/checkers/pii_checker.py`, `configs/use_case_policies.yaml`
**Do not touch:** other checkers, risk engine, control policy

---

## 1. Why the current logic is weak

Current `pii_checker.py`: static regex for SSNs, emails, phone numbers. Per the roadmap doc,
this "fails on edge cases or obfuscated PII (e.g., 'my number is 5 five 5...')." Regex-only PII
detection also completely misses **unstructured PII** — person names, addresses, organizations —
which have no fixed pattern and require actual entity recognition, not pattern matching.

## 2. The research this is based on

**System:** Microsoft Presidio — open-source PII detection/anonymization framework, widely cited
as "the current state of practice for enterprise PII detection" in recent literature (e.g.
*SurrogateShield*, arXiv:2606.29567; *Hardening x402*, arXiv:2604.11430).
Repo: `github.com/microsoft/presidio`. `pip install presidio-analyzer presidio-anonymizer`.

**Architecture (what Presidio actually does, confirmed from its own docs and independent
papers):**
- An **AnalyzerEngine** runs a **registry of recognizers** in parallel, each specialized:
  - **Regex + checksum recognizers** for structured entities: emails, credit cards (Luhn
    checksum), IBANs, SSNs, phone numbers.
  - **A spaCy NER model** (or swappable transformer NER model) for *contextual*, unstructured
    entities: person names, locations, organizations — things regex cannot catch.
  - **Context-word boosting**: if a regex match sits near a supporting keyword (e.g., "SSN:",
    "born on"), Presidio boosts the confidence score for that match. This is the mechanism that
    fixes your roadmap's obfuscation problem to a meaningful degree, and is easy to replicate.
- Each recognizer returns `(entity_type, char_span, confidence_score)` — not a binary flag. This
  score-based (not boolean) output is exactly what your `RiskEngine` needs to combine with other
  checkers.
- An **AnonymizerEngine** applies the actual redaction/masking — this is what Spec 08
  (Intelligent Edit) will reuse instead of the current static `[REDACTED BY POLICY]` string.

**Important finding from research (state this in your pitch as informed nuance, not a flaw
hidden from judges):** Multiple recent papers (*PIIBench*, arXiv:2604.15776; *Towards Fair and
Efficient De-identification*, arXiv:2602.15869) show Presidio's default spaCy backend
underperforms newer transformer-based PII-specific models. `PIIBench` and the de-identification
paper both show transformer NER models (BERT-family, or the PII-specific
`iiiorg/piiranha-v1-detect-personal-information` fine-tuned on `ai4privacy-400k`) achieve
precision/recall around 0.96–0.99 vs. Presidio's default spaCy backend being noticeably weaker on
nuanced types. **Recommendation: use the Presidio *architecture* (regex/checksum layer + context
boosting + pluggable NER layer) but swap the NER backend to `iiiorg/piiranha-v1-detect-personal-information`
(HuggingFace) instead of default spaCy** — Presidio explicitly supports pluggable NLP engines for
this. This is a stronger, more specific pitch point than "we used Presidio out of the box."

## 3. Data contract

### Output (fits existing `CheckerResult` schema)
```
CheckerResult:
    checker_name: "pii"
    risk_score: float                # 0.0-1.0, aggregated from max/weighted entity confidences
    entities: List[{
        entity_type: str,            # "EMAIL", "PHONE", "PERSON", "SSN", "LOCATION", "CREDIT_CARD", ...
        text: str,
        span_start: int,
        span_end: int,
        confidence: float,           # recognizer-native confidence, 0-1
        detection_method: "regex_checksum" | "transformer_ner" | "context_boosted"
    }]
    method: "presidio_hybrid_piiranha"
```
Character spans here are what makes Spec 08's targeted redaction possible (redact only the
entity span, not the whole response).

## 4. Step-by-step implementation plan

**Step 1 — Install dependencies**
```
pip install presidio-analyzer presidio-anonymizer transformers
python -m spacy download en_core_web_lg   # Presidio's default NLP engine dependency, still needed for its recognizer registry glue code
```

**Step 2 — Swap the NLP engine Presidio uses for NER**
- Presidio supports a `NlpEngineProvider` configuration where you register a custom NER pipeline.
- Load `iiiorg/piiranha-v1-detect-personal-information` via `transformers.pipeline("ner", ...)`
  and wrap it as a custom `EntityRecognizer` subclass registered into Presidio's
  `RecognizerRegistry` alongside its built-in regex recognizers (`EmailRecognizer`,
  `CreditCardRecognizer`, `IbanRecognizer`, `PhoneRecognizer`, `UsSsnRecognizer` — all
  ship built-in, keep them, they already implement checksum validation you don't have today).

**Step 3 — Rewrite `src/checkers/pii_checker.py`**
```
from presidio_analyzer import AnalyzerEngine

class PIIChecker:
    def __init__(self, analyzer: AnalyzerEngine):
        self.analyzer = analyzer   # constructed once at startup in dependencies.py with the custom NER recognizer registered

    def check(self, text: str, use_case_policy) -> CheckerResult:
        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=use_case_policy.pii_entity_allowlist,  # per-use-case configurability, see Step 4
        )
        entities = [to_entity_dict(r) for r in results]
        risk_score = aggregate_score(entities)  # e.g. 1 - product(1 - c_i) across entities, not simple max
        return CheckerResult(checker_name="pii", risk_score=risk_score, entities=entities, method="presidio_hybrid_piiranha")
```
- Use a **noisy-OR aggregation** (`1 - Π(1 - confidence_i)`) instead of a simple max — multiple
  medium-confidence PII hits in the same response should push risk higher than a single hit,
  which a max-based score can't express. This is a concrete, defensible improvement over "static
  regex → binary flag."

**Step 4 — Add per-use-case entity allowlists to `configs/use_case_policies.yaml`**
```yaml
pii_checker:
  customer_facing_chatbot:
    entity_allowlist: ["EMAIL", "PHONE", "CREDIT_CARD", "SSN", "PERSON"]
    min_confidence: 0.6
  internal_knowledge_assistant:
    entity_allowlist: ["SSN", "CREDIT_CARD"]   # employee names/emails are expected internally, don't over-flag
    min_confidence: 0.75
  decision_support_regulated:
    entity_allowlist: ["EMAIL", "PHONE", "CREDIT_CARD", "SSN", "PERSON", "LOCATION", "MEDICAL_LICENSE"]
    min_confidence: 0.5
```
This directly operationalizes the PS's "different risk signature depending on... how output is
used downstream" and gives judges a concrete answer to "how do you avoid alert fatigue" —
internal tools don't flag employee names, customer-facing tools do.

**Step 5 — Handle the "no internet / offline demo" risk**
- Both `piiranha` and `en_core_web_lg` are downloadable once and cached locally — pre-download
  them before the live demo so the pitch doesn't depend on live HuggingFace access.

## 5. Definition of Done

- [ ] `pii_checker.py` uses Presidio's `AnalyzerEngine` with built-in regex/checksum recognizers
      retained, plus a custom transformer NER recognizer (`piiranha`) registered.
- [ ] Output includes character spans and per-entity confidence, not a single boolean.
- [ ] Risk aggregation uses noisy-OR across multiple entities, not max.
- [ ] Per-use-case entity allowlist + confidence threshold wired from
      `configs/use_case_policies.yaml`.
- [ ] Pitch deck slide cites: Microsoft Presidio (industry-standard, cited as "current state of
      practice" in multiple 2025 papers) + `piiranha-v1` (HuggingFace, fine-tuned on
      `ai4privacy-400k`, ~0.96 F1) as the swapped-in NER backend, with the specific claim:
      "we didn't just use Presidio's defaults — research shows default spaCy backends
      underperform PII-specialized transformer models, so we upgraded the NER layer."
