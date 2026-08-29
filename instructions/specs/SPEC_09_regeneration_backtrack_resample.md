# SPEC_09 — Regeneration via Checkpoint-Backtrack Resampling

**Status:** Draft for implementation
**Owns:** `src/orchestrator/pipeline.py`, `src/policy/control_policy.py`, `src/engine/risk_engine.py`, `src/checkers/*`, new `src/regenerate/` module
**Solves:** Upgrade #1 ("Wire REGENERATE for real") + directly supports Upgrade #2 (latency) and #3 (use-case latency budgets), since the resampling scope is what makes REGENERATE cheap or expensive.
**Verdict on your idea up front:** Your instinct (sliding window over generated tokens + advanced prompt rewriting + regenerate) is directionally correct and is close to what several published techniques already do — you were mostly missing three things: (1) a formal **checkpoint** concept so you resample only the broken suffix instead of the whole response, (2) a **cheap trigger gate** before the expensive verification fires, and (3) a **specific rewrite recipe** rather than "rewrite the prompt better." This spec fills in those three gaps and cites where each piece comes from.

---

## 1. Research synthesis — what exists and what we're fusing

No single paper does "sliding-window streaming detection → backtrack to a checkpoint → advanced-prompt resample" end-to-end. We're fusing five separate lines of research, each solving one part of the problem your ControlPlane REGENERATE action needs.

### 1.1 Detecting *that* something is wrong, cheaply, while streaming
- **NeMo Guardrails output-rail streaming** (NVIDIA) already implements the exact mechanic you described: it buffers generated tokens into chunks (`chunk_size`) with a trailing `context_size` window of prior tokens for context, runs a check on each chunk as it streams, and only then releases it — this is effectively your "sliding window strided over tokens as they generate" idea, already shipped in a real guardrails framework. [docs.nvidia.com/nemo/guardrails — streaming config]
- **TrajGuard** (2026) is closer to your idea than NeMo: it aggregates *hidden-state trajectories* over a sliding window during decoding to score risk in real time, and only escalates to a heavier semantic check when risk stays above a threshold **persistently across the window**, not on a single spike. That "persist across window, then escalate" rule is exactly the noise-filtering behavior you want so you don't regenerate on one noisy token. It reports ~5ms/token overhead, i.e., cheap enough to run on every token. [arXiv:2604.07727]
- **Qwen3Guard "Stream" mode** does per-token real-time classification with a lightweight classification head running alongside generation, rather than a full second LLM call — the architectural lesson is: the *first-pass* streaming check should be a small classifier/heuristic, not another generation. [arXiv:2510.14276]

**Implication for your architecture:** your existing `ControlPlane.ai` design doc already specifies an adaptive token/sentence buffer feeding the Performance Checker — this is correct and validated. What's missing in the current codebase is that the *heavy* check (SelfCheckGPT) runs unconditionally on every window. It should only fire when a cheap signal (below) is uncertain.

### 1.2 The cheap first-pass signal (what gates the expensive check)
- **Semantic Entropy** (Farquhar et al., *Nature* 2024) and its cheaper cousin **Semantic Entropy Probes (SEPs)** are the relevant lineage here. Semantic entropy samples multiple completions, clusters them by meaning (not surface wording), and computes entropy over the clusters — high semantic entropy correlates with confabulation. SEPs go further: they train a lightweight probe directly on the model's **hidden states from a single generation**, so you get a semantic-entropy-like uncertainty signal **without multi-sampling**, which is the cheap-first-pass property you need. [arXiv:2406.15927]
- **Semantic Energy** (2026) is a newer alternative that operates on penultimate-layer logits with a Boltzmann-style energy score instead of post-softmax probabilities, explicitly proposed as a fix to cases where semantic entropy under-detects (e.g., when the model is confidently, repeatedly wrong in the same way). It's positioned as a strict improvement over semantic entropy for triggering "regenerate" decisions specifically. [arXiv:2508.14496]
- **TrajGuard's own cheap gate** — sliding-window hidden-state trajectory delta — is a third viable option and has the advantage of already living in "streaming decode" literature rather than QA-benchmark literature.

**Recommendation:** you already load `sentence-transformers` (`all-MiniLM-L6-v2`) for session drift. For the cheap gate, don't add a new model — use **token-level output entropy / top-2 logit margin** (free, already available from the adapter's logprobs) as the tier-0 gate, and only escalate to SelfCheckGPT (tier-1, expensive) when tier-0 crosses an uncertain band. This is the standard cascade pattern implied by both TrajGuard and Semantic Energy's framing ("high uncertainty → trigger regeneration / human"), just using signal you already have for free instead of adding a probe model to train.

### 1.3 What to do once triggered — repair vs. regenerate vs. backtrack
This is the part your control policy already gets right conceptually (MODIFY vs REGENERATE), but the *how* of REGENERATE needs a scope decision. Three published patterns map onto this:

- **Self-Refine** (Madaan et al., 2023): same model critiques its own output in natural language, then rewrites using that critique, iterated until a stop condition. Reports ~20% average quality gain across 7 tasks, no training required. Key caveat from follow-up work: **self-bias** — models trained/aligned in RLHF tend to over-rate their own prior output, so pure self-critique-and-rewrite under-corrects. [arXiv:2303.17651; self-bias finding from Xu et al., cited in the "Iterative Refinement for Design Critique" survey]
- **Chain-of-Verification (CoVe)** (Dhuliawala et al., Meta, 2023): draft → generate independent verification questions targeting specific claims → answer those questions **without letting the model see its own draft answer** (the "Factored" variant) → synthesize a corrected final response. The Factored variant exists specifically because letting the model see its prior answer while verifying causes it to just repeat the same hallucination. This is the single most directly-applicable technique for your "rewrite the prompt with an advanced technique" instinct — CoVe *is* a formalized version of that idea. [arXiv:2309.11495]
- **RARR — "Researching and Revising What Language Models Say, Using Language Models"** (Google, 2022): post-hoc, model-agnostic. Given a generated claim: (1) generate research questions about the claim, (2) retrieve evidence for each, (3) run an "agreement gate" LLM call that decides per-piece-of-evidence whether it contradicts the claim, (4) only if it contradicts, run an edit call that revises the claim to match evidence while preserving style. Open-source reference implementation exists. This is the right template for your **PII/factual repair** path specifically, because it only edits when there's a genuine contradiction (avoiding the alert-fatigue problem the PS calls out) and it's explicitly model-agnostic / works purely at input-output layer, matching your constraint of only having API access to the foundation model. [arXiv:2210.08726; github.com/anthonywchen/RARR]
- **Tree of Thoughts (ToT)** (Yao et al., NeurIPS 2023): the formal source of the word "backtrack" in this spec's title. ToT frames generation as search over a tree of partial states, where a checker/evaluator can decide to backtrack to a previous node rather than restart from scratch or accept the current path. The general lesson for us is architectural, not literal (we're not doing multi-branch tree search per token, that's too slow for a live proxy) — it's the principle that **the unit of "undo" should be the last good checkpoint, not the whole generation.** [arXiv:2305.10601]

### 1.4 Fragile-repair problem (your existing `span_repair.py` issue)
Not a regeneration technique per se, but relevant: RARR's "revise only the flagged claim, preserve everything else" pattern is exactly the discipline your `SpanRepairEngine` needs, and the fix for the `str.replace` fragility is character-offset tracking captured **at generation time** (i.e., record the buffer's char offsets when each window/chunk was checked, don't re-search for the string later). This is covered fully in SPEC for span_repair; noted here because REGENERATE and MODIFY share the same offset-tracking data structure (see §3.1).

### 1.5 Why NOT full multi-sample best-of-N / speculative rejection for this use case
Best-of-N with a reward model (generate N full completions, score, pick best) and speculative-rejection variants are real and are used in some hallucination-mitigation pipelines, but they multiply generation cost by N and don't fit "don't slow the AI down" — they're the wrong tool for an inline proxy with a latency budget, even though they're a valid technique for offline/batch use cases. Use case differentiation (Upgrade #3) is exactly where this belongs: allow N>1 best-of-N regeneration for the `internal-batch` use-case tier only, never for customer-facing real-time.

---

## 2. The technique: Checkpoint-Backtrack Resampling (CBR)

Fusing §1.1–1.4 into one pipeline-shaped mechanism.

```
                     ┌─────────────────────────────────────────┐
                     │   Streaming generation (existing buffer)  │
                     └─────────────────────────────────────────┘
                                       │
                         sliding window, stride = N tokens
                         (existing adaptive buffer in pipeline.py)
                                       │
                                       ▼
                     ┌─────────────────────────────────────────┐
                     │  TIER-0 gate: cheap signal, every window  │
                     │  (token entropy / top-2 logit margin, or  │
                     │   MiniLM cosine drift vs. last checkpoint)│
                     └─────────────────────────────────────────┘
                            │ uncertain?            │ confident
                            ▼                        ▼
        ┌───────────────────────────────┐   commit window as new
        │ TIER-1: run existing checkers  │   CHECKPOINT, continue
        │ (SelfCheckGPT / PII / bias)    │   streaming
        │  — only fires here, not always │
        └───────────────────────────────┘
                            │
                risk classified by Control Policy
                            │
         ┌──────────┬───────────────┬──────────────┐
         ▼          ▼               ▼               ▼
       ALLOW      MODIFY        REGENERATE        HUMAN
                (span repair,   (this spec)     (escalate)
                 RARR-style)
```

### 2.1 What a "checkpoint" is
A checkpoint is **the last window boundary that passed Tier-0 (and Tier-1, if it ran) with acceptable risk.** Concretely, store:

```python
@dataclass
class Checkpoint:
    turn_id: str
    char_offset: int          # offset into the response buffer, not the LLM's KV cache
    token_offset: int
    risk_snapshot: FinalRiskReport   # risk profile AT this point, for audit trail
    prompt_state: str          # the effective prompt/context up to this point
    timestamp: float
```

You do **not** need to snapshot the model's actual KV cache (that requires low-level engine access most API-based deployments don't have — see PS constraint "enterprises consume a foundation model via API rather than owning it outright"). Instead, checkpoint at the **text level**: the checkpoint is "everything generated up to char_offset X is accepted; discard everything after."

### 2.2 What "backtrack" means operationally
When Control Policy returns REGENERATE:
1. Truncate the in-flight response buffer back to the **last good checkpoint** (not to zero — this is the fix for "decision-only" REGENERATE and the core efficiency win over full-response regeneration).
2. If no checkpoint exists yet (the very first window already failed), backtrack to the empty string — equivalent to full regeneration, which is correct behavior for a bad start.
3. Everything after the checkpoint is discarded and never shown to the user (this requires the output buffer to *not* have released those tokens yet — consistent with your existing "buffer collects before releasing" design in the ControlPlane doc).

### 2.3 What "resample" means — the advanced-prompt rewrite recipe
This is the part you asked for directly: don't just "rewrite the prompt better" vaguely — use this concrete, three-step recipe, adapted from CoVe + RARR:

**Step A — Diagnose (CoVe-style, Factored).** Using the *same* model but a fresh context (the model does not see its own flawed continuation while diagnosing — this avoids the self-bias problem noted in §1.3):
```
SYSTEM: You are a verification assistant. You will be given a PARTIAL response
and the risk signal that flagged it. Generate 2-4 short, independent, checkable
questions that would confirm or refute the flagged concern. Do not answer them.

USER:
Original user request: {original_prompt}
Response so far (accepted, up to checkpoint): {checkpoint_prefix}
Flagged continuation (will be discarded): {flagged_span}
Flagged risk type + evidence: {risk_engine_reason}   # e.g. "Performance risk 0.81:
   claim 'the treaty was signed in 1994' not supported by any retrieved context"

Output ONLY the verification questions, one per line.
```

**Step B — Verify (Factored, independent context).** Answer each question in a *separate* call with no access to the flagged span:
```
SYSTEM: Answer the following question as accurately and concisely as possible,
using only the provided evidence if any. If you don't know, say so explicitly
rather than guessing.

USER:
Question: {verification_question}
Evidence (if retrieved / from RAG source): {evidence_or_none}
```
If your use case has retrieval available, this is where RARR's "agreement gate" pattern applies: only treat an answer as a real contradiction if it's grounded in retrieved evidence, not just a second unguided guess (which just risks a second hallucination).

**Step C — Regenerate with constrained micro-prompt.** Build the resample prompt from the checkpoint prefix + diagnosis, and regenerate *only the continuation*, not the whole answer:
```
SYSTEM: Continue the response below. The prior draft continuation was discarded
because: {consolidated_verification_findings}.
Do not repeat the discarded content. Stay consistent with everything already
written. If you are not confident about a specific fact, state your uncertainty
explicitly rather than asserting it.
Constraints: temperature={lower_than_original}, max_tokens={remaining_budget}.

USER:
Original request: {original_prompt}
Accepted response so far: {checkpoint_prefix}
Continue from here:
```

This is deliberately **not** full Self-Refine (critique-then-rewrite-the-whole-thing) because that regenerates tokens you already paid for and already passed checks — the whole point of checkpointing is to only pay for the broken suffix.

### 2.4 Loop bound (prevents infinite regenerate thrashing)
```python
MAX_REGENERATE_ATTEMPTS_PER_CHECKPOINT = 2   # per use-case, configurable in YAML
```
If Tier-1 flags the *resampled* continuation again at the same checkpoint, do not backtrack further and retry indefinitely — this is exactly the "system cannot safely resolve conflicting signals" condition your Control Policy doc already defines as the trigger for **HUMAN**. Route there. This closes the loop between REGENERATE and HUMAN cleanly and gives you a natural demo beat ("watch it try twice, then escalate").

---

## 3. Step-by-step implementation guide

### 3.1 New module: `src/regenerate/checkpoint_backtrack.py`
```python
class CheckpointManager:
    def __init__(self):
        self.checkpoints: dict[str, list[Checkpoint]] = {}  # keyed by turn_id

    def commit(self, turn_id: str, char_offset: int, token_offset: int,
               risk_snapshot: FinalRiskReport, prompt_state: str) -> Checkpoint: ...

    def last_good(self, turn_id: str) -> Checkpoint | None: ...

    def backtrack(self, turn_id: str) -> str:
        """Return the accepted prefix text to resume generation from."""
        cp = self.last_good(turn_id)
        return cp.prompt_state if cp else ""
```

```python
class RegenerationEngine:
    def __init__(self, adapter, checkpoint_mgr: CheckpointManager, risk_engine, retriever=None):
        ...

    async def regenerate(self, turn_id, original_prompt, flagged_span,
                          risk_reason, use_case_policy) -> str:
        prefix = self.checkpoint_mgr.backtrack(turn_id)
        questions = await self._diagnose(original_prompt, prefix, flagged_span, risk_reason)
        findings = await self._verify(questions, retriever=self.retriever)
        return await self._resample(original_prompt, prefix, findings, use_case_policy)
```

### 3.2 Wire into `src/orchestrator/pipeline.py`
Locate the existing `(If MODIFY)` branch described in the codebase doc. Add a parallel branch:
```python
elif decision.action == Action.REGENERATE:
    attempts = session_state.get_regen_attempts(turn_id, checkpoint_id)
    if attempts >= use_case_policy.max_regenerate_attempts:
        decision = Decision(action=Action.HUMAN, reason="regen budget exhausted")
        # fall through to HUMAN handling
    else:
        new_span = await regeneration_engine.regenerate(
            turn_id, original_prompt, flagged_span, risk_reason, use_case_policy)
        # re-verify through risk_engine before splicing (same discipline as MODIFY)
        recheck = await risk_engine.evaluate(checkpoint_prefix + new_span, context)
        session_state.increment_regen_attempts(turn_id, checkpoint_id)
        if recheck.passes(use_case_policy):
            buffer.splice_from(checkpoint.char_offset, new_span)
            checkpoint_mgr.commit(turn_id, ...)  # new checkpoint after successful regen
        else:
            continue_loop  # will hit the attempts cap next time, then escalate to HUMAN
```

### 3.3 Wire the Tier-0/Tier-1 cascade into `src/checkers/performance_checker.py`
```python
async def check(self, window_text, logprobs, context):
    tier0_score = self._cheap_uncertainty(logprobs)   # top-2 logit margin / entropy, free
    if tier0_score < self.uncertain_threshold:
        return CheckerResult(risk=tier0_score, tier=0, ran_selfcheck=False)
    # only now pay for SelfCheckGPT
    selfcheck_score = await self._selfcheckgpt(window_text, context)
    return CheckerResult(risk=selfcheck_score, tier=1, ran_selfcheck=True)
```
`uncertain_threshold` should be per-use-case (Upgrade #3): customer-facing tiers get a wider "confident enough, skip Tier-1" band; internal/decision-support tiers get a narrower band (more Tier-1 calls, more scrutiny, matches their higher risk tolerance requirement per the PS).

### 3.4 Wire semantic overlap reuse (Upgrade #4, shares code with this spec)
Since `RegenerationEngine._verify` already needs an embedder for evidence-matching quality, reuse the same `all-MiniLM-L6-v2` instance already loaded by `session_state.py` (dependency-inject it rather than instantiate twice) — this is the "near-zero extra cost" reuse called out in your upgrade list, and it directly replaces the string-matching overlap heuristic in `RiskEngine` with cosine similarity between checker-flagged spans.

### 3.5 Config additions to `use_case_policies.yaml`
```yaml
customer_facing_chat:
  max_regenerate_attempts: 1
  tier0_uncertain_band: [0.35, 0.65]   # narrow -> most windows skip Tier-1
  regenerate_temperature: 0.2
  allow_best_of_n_regenerate: false

internal_decision_support:
  max_regenerate_attempts: 2
  tier0_uncertain_band: [0.20, 0.80]   # wide -> more windows get Tier-1 scrutiny
  regenerate_temperature: 0.1
  allow_best_of_n_regenerate: true      # batch/internal can afford it, see §1.5
  best_of_n: 3
```

### 3.6 Audit trail (needed for §2.1's risk_snapshot and for Upgrade #8 dashboard)
Every checkpoint, regenerate attempt, and outcome should append a row to whatever store Upgrade #10 (SQLite/Postgres) puts in place — checkpoint_id, turn_id, char_offset, attempt_number, diagnosis_questions, verification_findings, tier0_score, tier1_score, outcome (accepted/re-flagged/escalated). This is what lets the metrics dashboard (Upgrade #8) report "regenerate success rate" and "cost saved by partial vs full regeneration" — the latter being a strong, concrete number for a skeptical judge (e.g., "we regenerated 40 tokens instead of the full 400-token response, an 85% compute saving on this repair").

### 3.7 Testing checklist (ties to Upgrade #14)
- Unit test: checkpoint truncation math (char_offset correctness under multi-byte/unicode text).
- Unit test: attempt-cap → HUMAN escalation fires exactly at the configured limit, not before/after.
- Integration test: simulate a flagged span, confirm the resampled continuation is re-verified before splicing (never splice unchecked).
- Integration test: Tier-0 gate correctly skips Tier-1 on a clearly-confident window (assert `ran_selfcheck=False`) and correctly escalates on a synthetic high-entropy window.
- Demo script: scripted example where a first regenerate attempt still fails and a second succeeds, to show the "watch it retry" behavior live.

---

## 4. Answering your two open questions directly

**"Is my sliding-window idea bad?"** No — it's the same mechanism NeMo Guardrails and TrajGuard both ship in production-adjacent form. Your gap wasn't the window, it was that you were about to run the expensive check on *every* window (that's the latency-fatal issue Upgrade #2 flags) and you didn't yet have a formal checkpoint/backtrack boundary to scope what gets thrown away. Both are fixed above.

**"Advanced prompting technique — which one?"** Use CoVe's factored diagnose→verify pattern to figure out *what's wrong without repeating the same mistake*, and RARR's evidence-gated revise pattern to decide *whether it's actually wrong before editing* (protects against the alert-fatigue problem in the PS). Don't use plain Self-Refine alone — its documented self-bias problem (a model over-trusting its own prior output) is exactly the failure mode a Responsible-AI checker can't afford, which is why CoVe's factored/independent-context verification step matters specifically for this use case.

---

## 5. Reference list

- Farquhar et al., "Detecting hallucinations in large language models using semantic entropy," *Nature*, 2024 — arXiv:2406.15927 (Semantic Entropy Probes, same lineage)
- Duan et al., "Semantic Energy: Detecting LLM Hallucination Beyond Entropy," 2026 — arXiv:2508.14496
- TrajGuard, "Streaming Hidden-state Trajectory Detection for Decoding-time Jailbreak Defense," 2026 — arXiv:2604.07727
- Qwen3Guard Technical Report — arXiv:2510.14276
- NVIDIA NeMo Guardrails, output-rail streaming docs — docs.nvidia.com/nemo/guardrails
- Madaan et al., "Self-Refine: Iterative Refinement with Self-Feedback," 2023 — arXiv:2303.17651
- Dhuliawala et al., "Chain-of-Verification Reduces Hallucination in Large Language Models," Meta AI, 2023 — arXiv:2309.11495
- Chen, Zhao, Chan, et al., "RARR: Researching and Revising What Language Models Say, Using Language Models," Google Research, 2022 — arXiv:2210.08726, github.com/anthonywchen/RARR
- Yao et al., "Tree of Thoughts: Deliberate Problem Solving with Large Language Models," NeurIPS 2023 — arXiv:2305.10601
- Asai et al., "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection," ICLR 2024 — arXiv:2310.11511 (background reading — informs how you might later gate retrieval itself, not used directly in this spec)