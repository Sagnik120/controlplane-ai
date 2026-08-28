# Spec 01 — Upgrade `performance_checker.py` with SelfCheckGPT-style Hallucination Detection

**Status:** Ready to implement
**Touches:** `src/checkers/performance_checker.py`, `src/adapters/*`, `src/orchestrator/pipeline.py`, `configs/use_case_policies.yaml`
**Do not touch:** other checkers, risk engine, control policy (those are separate specs)

---

## 1. Why the current logic is weak

Current `performance_checker.py` logic (per `codebase_analysis_and_roadmap.md`):
- Looks for hard-coded hedging phrases ("I am not sure") and naive contradiction patterns
  ("is...but...not").
- Fails on **confident hallucinations** — the most dangerous case, where the model states a
  fabricated fact fluently and with no hedging at all. This is exactly the Round 1 PS framing:
  *"confidently wrong."*
- Is a pure string-matching heuristic with no theoretical grounding — a judge can trivially find
  a case where it fails live in the pitch demo.

## 2. The research this is based on

**Paper:** *SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large
Language Models* — Manakul, Liusie, Gales. University of Cambridge. EMNLP 2023.
arXiv:2303.08896. Code: `github.com/potsawee/selfcheckgpt` (`pip install selfcheckgpt`).

**Core idea (in plain terms):**
> If the LLM actually "knows" a fact, then asking it the same question multiple times
> (at higher temperature, so answers vary in phrasing) will produce answers that are
> semantically consistent with each other. If the LLM is hallucinating, the sampled answers
> will diverge and contradict each other, because there's no real underlying fact anchoring them.

**Why it fits your exact constraint:** The Round 2 PS explicitly says enterprises "consume a
foundation model via API rather than owning it outright, limiting how deeply a checker can
inspect model internals." SelfCheckGPT was *designed for this exact situation* — it is a
**black-box, zero-resource** method: no logits, no internal states, no external knowledge base
required. It only needs the ability to call the same model multiple times with the same prompt.
This is a strong pitch point: *"We use the same production-grade methodology as the peer-reviewed
EMNLP paper that specifically solves the API-only constraint your PS calls out."*

**Which variant to implement:** The paper compares 5 variants (BERTScore, QA, n-gram, NLI,
LLM-Prompt). For a hackathon prototype under latency pressure, implement two of them, combined:

1. **SelfCheckGPT-BERTScore** (fast, cheap, no extra LLM call cost beyond sampling) — measures
   sentence-level semantic overlap between the main response and N sampled responses using
   sentence embeddings.
2. **SelfCheckGPT-NLI** (higher accuracy per the paper's AUC-PR results) — uses a small NLI model
   to check whether each sampled response entails/contradicts each sentence of the main response.

Use NLI as the primary signal (best AUC-PR in the paper) and BERTScore as a fast fallback when
latency budget is tight (see §5, adaptive sampling).

## 3. Data contract

### Input (unchanged interface, extend `CheckerResult` if needed)
```
PerformanceCheckInput:
    prompt: str                # original user prompt
    main_response: str         # the response currently streaming to the user
    adapter: BaseLLMAdapter    # the same adapter used for generation (for re-sampling)
    n_samples: int = 3         # number of extra stochastic samples to draw
    sampling_temperature: float = 1.0
    use_case_policy: UseCasePolicy   # for latency budget / n_samples override
```

### Output (fits existing `CheckerResult` schema in `src/checkers/base.py`)
```
CheckerResult:
    checker_name: "performance"
    risk_score: float            # 0.0 - 1.0, aggregated hallucination risk
    sentence_scores: List[{
        sentence: str,
        span_start: int,
        span_end: int,
        inconsistency_score: float   # 0 = fully consistent across samples, 1 = fully contradicted
    }]
    confidence: float             # based on sample agreement variance
    method: "selfcheckgpt-nli+bertscore"
```

The `sentence_scores` with `span_start`/`span_end` are critical — they let the Risk Engine (Spec
05) and the MODIFY action in `control_policy.py` target the exact problematic span instead of the
whole response, which is literally what your architecture doc's "MODIFY" action requires
(*"Repair only what needs repair instead of regenerating the entire answer"*).

## 4. Step-by-step implementation plan

**Step 1 — Add a sampling utility to the adapter layer**
- In `src/adapters/base_adapter.py`, ensure `BaseLLMAdapter` exposes a non-streaming
  `generate_once(prompt, temperature) -> str` method (most adapters already have the underlying
  call; streaming is just a wrapper).
- Add this to `gemini_adapter.py` and `mock_adapter.py`. For `mock_adapter.py`, make it return
  slightly randomized paraphrases when a "hallucination-test" keyword is present in the prompt,
  so you can demo inconsistency detection deterministically without burning API credits.

**Step 2 — Install dependencies**
```
pip install selfcheckgpt sentence-transformers
```
(NLI variant pulls a small cross-encoder NLI model, e.g. `vectara/hallucination_evaluation_model`
or the `potsawee/deberta-v3-large-mnli` used in the original repo — both are small enough to run
on CPU for a hackathon demo.)

**Step 3 — Rewrite `src/checkers/performance_checker.py`**
- On receiving a completed sentence/window from the Stream Buffer (per your architecture doc's
  sentence/claim-based window mode — use that mode for this checker, not token-based, since
  SelfCheckGPT needs full sentences):
  1. Call `adapter.generate_once(prompt, temperature=1.0)` `n_samples` times to get stochastic
     samples. (For streaming responses already fully generated by the time this checker runs on
     a finished window, this is a cheap side-call, not a re-generation of the main response.)
  2. Split `main_response` window into sentences (use `spacy` `en_core_web_sm`, already a
     dependency via Presidio in Spec 02 — reuse it, don't add a second NLP library).
  3. For each sentence, run:
     - `SelfCheckGPTNLI.predict(sentences, samples)` → per-sentence contradiction probability.
     - `SelfCheckGPTBERTScore.predict(sentences, samples)` → per-sentence semantic divergence.
  4. Combine: `inconsistency_score = 0.7 * nli_score + 0.3 * bertscore_score` (NLI weighted
     higher — paper shows it has the best AUC-PR).
  5. `risk_score = max(sentence-level scores)` for the window, but keep the full
     `sentence_scores` list so downstream MODIFY can target just the bad sentence.

**Step 4 — Wire into `pipeline.py`**
- The orchestrator already calls checkers per buffered window. No structural change needed —
  just swap the old `performance_checker.check(window)` call signature to also pass `adapter`
  and `prompt`.

**Step 5 — Add config knobs to `configs/use_case_policies.yaml`**
```yaml
performance_checker:
  n_samples: 3            # customer-facing: 2 (latency-sensitive), internal-copilot: 5 (higher accuracy ok)
  sampling_temperature: 1.0
  nli_weight: 0.7
  bertscore_weight: 0.3
  method: "hybrid"         # options: "nli_only", "bertscore_only", "hybrid"
```
This directly satisfies the PS requirement: *"a single, one-size-fits-all checking approach
rarely works well everywhere"* — customer-facing (low latency budget) uses fewer, cheaper
samples; internal decision-support (higher risk tolerance for latency, lower tolerance for
wrong answers) uses more samples.

## 5. Latency mitigation (judges will ask about this — PS explicitly asks "how do you avoid
slowing the AI down so much it defeats the purpose?")

- Run the `n_samples` calls **in parallel** (`asyncio.gather`), not sequentially — this is a
  concrete engineering answer to give judges.
- Only trigger SelfCheckGPT sampling on sentences that already show *some* signal from a cheap
  first-pass filter (e.g., a lightweight uncertainty proxy from log-prob if available, or simply
  run it on every Nth sentence for very long responses) — this operationalizes your own
  architecture doc's principle **"② Adaptive rather than fixed checking."** State this explicitly
  in the pitch: "we don't SelfCheck every sentence, we SelfCheck the sentences most likely to be
  wrong, using a cheap trigger first."
- Cache re-sampled answers per (prompt-prefix) within a session — if multiple sentences in the
  same response need checking, reuse the same N samples rather than re-sampling per sentence.

## 6. Definition of Done

- [ ] `performance_checker.py` no longer contains any hard-coded hedge-phrase list.
- [ ] Checker returns per-sentence `inconsistency_score` with character spans.
- [ ] `mock_adapter.py` supports a deterministic "inconsistent sample" mode for demoing without
      live API calls.
- [ ] Config supports per-use-case `n_samples` override.
- [ ] Pitch deck slide cites: Manakul et al., EMNLP 2023, arXiv:2303.08896 — "we use the
      peer-reviewed, zero-resource, black-box method designed for exactly the API-only
      constraint in the problem statement."
