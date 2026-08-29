# SPEC_12 — Semantic Overlap Detection in RiskEngine (Embedding-Based)

**Status:** Draft for implementation
**Owns:** `src/engine/risk_engine.py`, `src/checkers/base.py`, `src/policy/schemas.py`, `src/session/session_state.py` (embedder becomes a shared dependency)
**Solves:** Upgrade #4 — "replace string-matching overlap in `RiskEngine` with embedding similarity, reuse `all-MiniLM-L6-v2` already loaded for session drift — near-zero extra cost."
**Direct PS relevance:** Round 2's PS names this exact failure mode — *"a fabricated detail about a person can simultaneously be a hallucination and a privacy concern... making clean categorization harder than it first appears."* Your current text-intersection heuristic can only catch overlap when the *same characters* are flagged by two checkers. It structurally cannot catch the PS's own example: a hallucinated name and a PII concern about that same (fabricated) name are about the same **entity/claim**, but the Performance checker and the PII checker may phrase, tokenize, or bound their flagged spans completely differently.

---

## 1. Why string-matching overlap is the wrong tool, precisely

Per the codebase doc, today's overlap detection is "a primitive string-matching bounding box, not a true semantic intersection." Concretely, this means it likely does something like checking whether two checkers' flagged character ranges intersect. Two failure modes follow directly:

- **False negatives (the real risk):** the Performance checker flags "the treaty was signed in 1994" (a hallucinated date) in one sentence, while the PII checker flags "John Whitfield" (a fabricated name attributed to a real-sounding person) in a *different* sentence three lines later, both about the same fabricated historical claim. No character overlap exists, so `RiskEngine` never notices these are the same underlying failure, and severity never escalates the way the PS explicitly says it should.
- **False positives (alert fatigue risk):** two genuinely unrelated flags that happen to sit in adjacent or overlapping character ranges (e.g., a PII flag on a phone number immediately followed by an unrelated bias flag on the next clause) get treated as "overlapping" purely because of proximity, inflating severity for no real reason — directly working against the PS's alert-fatigue concern.

Both are symptoms of using **position** as a proxy for **relatedness**, when the actual thing you want to detect is semantic relatedness.

---

## 2. Research synthesis

### 2.1 Which embedding architecture, and why reuse is the right call, not just cheap
- The standard trade-off in the retrieval/STS literature is **bi-encoders vs. cross-encoders**: bi-encoders (e.g., Sentence-BERT-style models, which is what `all-MiniLM-L6-v2` is) encode each text independently into a fixed vector and compare via cosine similarity — cheap, cacheable, embeddings reusable across comparisons. Cross-encoders jointly attend over a text *pair* and produce a single relevance score — more accurate at the pairwise level, but require one forward pass **per pair**, which doesn't scale when you might have several flagged spans per window across three checkers. [Reimers & Gurevych's bi-encoder/cross-encoder distinction, as summarized across multiple 2024–2026 survey papers: arXiv:2406.15066, arXiv:2109.13059, arXiv:2206.12664, arXiv:2508.21085]
- The standard production pattern when you want both cheap coverage and high precision is **retrieve-then-rerank**: use the cheap bi-encoder for the first pass over all pairs, then only run a more expensive cross-encoder on the small number of pairs that land near the decision boundary. This is exactly the shape SPEC_10/SPEC_11 already established for your checkers (cheap Tier-0 gate, expensive Tier-1 only when uncertain) — this spec applies the identical pattern to overlap scoring instead of introducing a new architecture concept. [arXiv:2210.04261 "Noise-Robust De-Duplication at Scale" — explicitly uses bi-encoder-first, cross-encoder-rerank for the same cost reason]
- **Reuse justification, concretely**: `all-MiniLM-L6-v2` is already resident in memory for session-drift cosine distance (per the codebase doc's `session_state.py` entry). Loading a second embedding model for overlap scoring would cost real memory and startup latency for no accuracy benefit at this text length — short flagged spans (a sentence or a claim) are exactly the regime `all-MiniLM-L6-v2` was designed and evaluated for ("lightweight... designed for sentence- and short-paragraph embedding," explicitly contrasted against larger models like `all-mpnet-base-v2` as the efficient choice for large pairwise comparison volumes). [arXiv:2606.04806]

### 2.2 Combine position AND semantics, don't replace one with the other
A useful precedent from text-clustering literature (originally developed for near-duplicate/related-content clustering) is to use **two independent signals jointly** rather than one: a similarity score (semantic) and an overlap score (lexical/positional), each with its own threshold, and treat a pair as related if *either* a high-similarity threshold is met on its own, *or* a lower-similarity-plus-meaningful-overlap combination is met. [nearest-neighbor clustering method, image-ppubs.uspto.gov/dirsearch-public 7747083 — describes exactly this dual-threshold gate: high similarity alone qualifies, OR moderate similarity + overlap together qualifies]

This maps directly onto your two failure modes from §1: keep a **cheap char-offset IoU check** (catches the "same sentence, multiple checkers" case, effectively free) **and add** a **semantic cosine-similarity check** (catches the "different sentence, same underlying claim" case) — union them, don't replace one with the other. Removing the char-offset check entirely would regress your current (if crude) detection of literal same-span overlap.

### 2.3 Precedent for hybrid similarity + classification detection improving real coverage
Two production-scale content-moderation papers report the same finding in different domains: a classification-based detector and a similarity/embedding-based detector catch **substantially non-overlapping** sets of true positives when run side by side, not the same cases twice.
- A livestream moderation system reports its similarity-matching path contributes **~22% additional coverage beyond the classification branch alone**, in production A/B testing. [arXiv:2512.03553]
- A separate short-video risk system explicitly frames embedding similarity as *complementary* to classification specifically because classification models "produce only categorical outputs... limiting flexibility... when handling high-risk content that demands a more nuanced approach," while similarity search generalizes to novel phrasings of a known risk pattern without retraining. [arXiv:2507.01066]

**Implication for you:** this isn't just an overlap-scoring upgrade — the same embedding infrastructure, once in place, gives you a cheap secondary detection signal (nearest-neighbor similarity against a small curated set of known cross-risk patterns, e.g. "fabricated-name-plus-fake-biographical-detail" as a labeled reference case) that neither your rule-based overlap logic nor your individual checkers currently provide. This spec implements the core overlap fix now and flags the reference-set extension as a natural Phase 2 (§5).

---

## 3. Proposed architecture

### 3.1 Standardize checker output to span-level, not just scalar risk
Today, checkers apparently return a single risk scalar per checker (`CheckerResult(risk=..., tier=...)` per SPEC_10). Semantic overlap requires each checker to also report **which span of text it flagged**, since that's the unit being compared:
```python
@dataclass
class FlaggedSpan:
    checker_name: str          # "performance" | "pii" | "safety_bias"
    text: str                  # the exact flagged substring
    char_start: int
    char_end: int
    risk_score: float
    risk_reason: str           # e.g. "unsupported claim", "PERSON entity, high confidence"
    embedding: np.ndarray | None = None   # populated lazily, cached
```
`CheckerResult` gains a `flagged_spans: list[FlaggedSpan]` field (empty if the checker found nothing). This is a small, additive schema change — it doesn't remove the existing scalar `risk` field, so `control_policy.py`'s existing threshold logic keeps working unchanged.

### 3.2 `SemanticOverlapDetector` — the new component
```python
class SemanticOverlapDetector:
    def __init__(self, embedder: SentenceTransformer, cross_encoder=None):
        self.embedder = embedder            # SAME instance as session_state.py's MiniLM (DI, not re-instantiated)
        self.cross_encoder = cross_encoder   # optional, only for borderline reranking (§3.4)

    def find_overlaps(self, spans: list[FlaggedSpan],
                       char_iou_threshold: float = 0.3,
                       cosine_threshold: float = 0.62) -> list[OverlapGroup]:
        # 1. cheap positional pass — O(n^2) on typically <10 spans per window, negligible
        char_overlaps = self._char_iou_pairs(spans, char_iou_threshold)

        # 2. semantic pass — batch-embed all flagged spans in ONE forward call (batching,
        #    not one-at-a-time, is what keeps this near-zero-cost even with several spans)
        texts = [s.text for s in spans if s.embedding is None]
        if texts:
            new_embeddings = self.embedder.encode(texts, batch_size=32)
            # cache back onto the span objects
            ...
        semantic_overlaps = self._cosine_sim_pairs(spans, cosine_threshold)

        # 3. union (§2.2) — either signal alone is sufficient to flag relatedness
        return self._merge_groups(char_overlaps, semantic_overlaps)
```

### 3.3 Cross-dimension escalation reuses your existing Noisy-OR, just applied across checkers
The codebase doc notes `pii_checker.py` already combines multiple internal signals via Noisy-OR ($1 - \prod(1-p_i)$). Reuse the identical aggregator for **cross-checker** escalation once an `OverlapGroup` is found, rather than inventing a new fusion formula:
```python
def escalate_overlap_severity(group: OverlapGroup) -> float:
    individual_risks = [span.risk_score for span in group.spans]
    return 1 - math.prod(1 - r for r in individual_risks)   # same Noisy-OR as pii_checker.py
```
This keeps the "why did severity go up" story consistent and explainable across the whole system — one aggregation rule, reused, not a different formula per subsystem. It also directly answers the PS's explicit example (a fabricated detail that is simultaneously a hallucination *and* a privacy concern) with real math: two moderate individual risks (say 0.5 performance + 0.5 PII) compound to 0.75 once recognized as the same underlying claim, appropriately outranking either alone.

### 3.4 Cross-encoder rerank — deferred (v1 ships bi-encoder-only)
Per §2.1's retrieve-then-rerank pattern, bi-encoder cosine similarity is reliable at the extremes but noisier in a middle band. Originally, an optional cross-encoder (e.g., `cross-encoder/stsb-roberta-base`) was proposed for this narrow "uncertain" band.

**Decision:** Deferred — v1 ships bi-encoder-only. Revisit if the false-positive/negative overlap rate from the dashboard (Upgrade #8) justifies the extra dependency weight and complexity. For now, a single well-chosen `cosine_threshold` per use-case tier is sufficient.

### 3.5 Caching and re-verification reuse (ties to SPEC_09's MODIFY/REGENERATE re-check)
Span embeddings should be cached on the `FlaggedSpan` object itself (per §3.2's `embedding` field) so that when `control_policy.py` triggers a MODIFY repair or SPEC_09's REGENERATE re-verification runs the risk engine again on a patched span, you're not recomputing embeddings for text that hasn't changed — only the newly-generated/repaired span needs a fresh embedding call, and it's a single-item batch, still essentially free.

---

## 4. Step-by-step implementation guide

1. **Extend `FlaggedSpan` / `CheckerResult` schemas** in `src/policy/schemas.py` per §3.1. Update `performance_checker.py`, `pii_checker.py`, `safety_bias_checker.py` to populate `flagged_spans` with char offsets (they likely already know these internally — Presidio and the NER pipeline both return character spans natively; SelfCheckGPT-flagged claims need their originating sentence's char offset tracked, which is also required groundwork for SPEC_09's checkpoint offsets and the span-splice fix in `span_repair.py`, so this is shared infrastructure, not one-off work).
2. **Dependency-inject the shared embedder.** Refactor `session_state.py` so its `all-MiniLM-L6-v2` `SentenceTransformer` instance is constructed once (e.g., in `main.py` or a small `embedding_registry.py`) and passed into both `SessionRiskState` and the new `SemanticOverlapDetector` — this is the literal "reuse it" instruction from the upgrade request; do not call `SentenceTransformer(...)` a second time anywhere.
3. **Add `SemanticOverlapDetector`** as a new file `src/engine/semantic_overlap.py`, implementing §3.2–§3.4.
4. **Wire into `risk_engine.py`**: after `asyncio.gather` collects all `CheckerResult`s (per SPEC_10's parallel dispatch), flatten their `flagged_spans` into one list, call `SemanticOverlapDetector.find_overlaps(...)`, then apply §3.3's escalation to any resulting `OverlapGroup`s before building the final `FinalRiskReport`.
5. **Add `overlap_groups: list[OverlapGroup]` to `FinalRiskReport`** for audit-trail visibility — this becomes a first-class field in the dashboard (Upgrade #8), not just an internal intermediate value; a judge can literally be shown "these two flags were recognized as the same underlying issue and severity was escalated accordingly," which is a strong, concrete demonstration of solving the PS's "overlapping risks" callout.
6. **Config**: add `char_iou_threshold`, `cosine_threshold`, and the optional cross-encoder uncertain band to `use_case_policies.yaml` per use case (per SPEC_11's per-tier philosophy — an internal/high-consequence tier may want a lower `cosine_threshold`, i.e., more sensitive overlap detection, than a customer-facing tier).

---

## 5. Phase 2 (flagged, not required for this spec): reference-set similarity matching
Per §2.3's hybrid-detection finding, once span embeddings are flowing through the system anyway, a natural low-cost extension is a small curated set of **known cross-risk pattern examples** (e.g., 20–50 hand-labeled examples of "hallucinated identity + PII" or "biased claim + fabricated statistic") that new flagged spans get compared against via the same embedder, as a second, independent detection path — not replacing the checkers, complementing them, exactly as both cited production systems describe. This is out of scope for the immediate overlap fix but worth noting in the roadmap doc since the infrastructure this spec builds (batched embedding, cosine comparison utilities) is a direct prerequisite.

---

## 6. Testing checklist
- Unit test: two spans with identical char ranges but low semantic similarity are still caught by the char-IoU path (regression test — don't lose current behavior).
- Unit test: two spans with zero char overlap but high cosine similarity (paraphrased references to the same fabricated entity) are caught by the semantic path — this is the core new capability, write this as the PS's own example (a hallucinated name flagged by Performance, the same name flagged separately by PII).
- Unit test: cross-encoder rerank correctly resolves a pair sitting in the uncertain band in both directions (confirm it can say "not actually related" as well as "related" — a rerank-always-escalates bug would quietly reintroduce alert fatigue).
- Unit test: Noisy-OR escalation math matches the existing `pii_checker.py` implementation exactly (shared function, not a re-derived formula, to avoid drift between the two).
- Performance test: batched embedding of N flagged spans in one window completes in the same rough latency envelope as a single MiniLM call — assert batching is actually happening (not looping single-item calls), since that's the main way this "near-zero-cost" claim could regress silently.
- Integration test: full pipeline run where Performance and PII checkers independently flag related-but-non-identical spans; assert the resulting `FinalRiskReport.overlap_groups` is non-empty and the combined severity via §3.3 exceeds either individual checker's raw score.

---

## 7. Reference list

- Reimers & Gurevych bi-encoder/cross-encoder framing, as summarized in: "Cross-lingual paraphrase identification" (arXiv:2406.15066), "Trans-Encoder" (arXiv:2109.13059), "Evaluation of Semantic Answer Similarity Metrics" (arXiv:2206.12664), "Granite Embedding R2 Models" (arXiv:2508.21085)
- "Noise-Robust De-Duplication at Scale" — bi-encoder-first, cross-encoder-rerank pattern — arXiv:2210.04261
- "NoRA: Evaluating Grounded Reasonableness..." — direct comparison including `all-MiniLM-L6-v2` as the efficient bi-encoder choice for short-span comparison — arXiv:2606.04806
- Dual-threshold (similarity + overlap) nearest-neighbor clustering method — US Patent / image-ppubs.uspto.gov 7747083
- "Dynamic Content Moderation in Livestreams: Combining Supervised Classification with MLLM-Boosted Similarity Matching" — ~22% additional coverage from similarity path — arXiv:2512.03553
- "Embedding-based Retrieval in Multimodal Content Moderation" — similarity-vs-classification complementarity argument — arXiv:2507.01066
