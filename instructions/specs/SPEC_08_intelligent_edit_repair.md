# SPEC_08 — Implement Real Span-Level Repair for the MODIFY Action

**Status:** Ready to implement
**Touches:** new `src/repair/span_repair.py`, `src/orchestrator/pipeline.py`
**Independent of:** other specs, but is most valuable once SPEC_01/02/04 are producing accurate
character spans (`sentence_scores`, `entities`) to repair — works with whatever spans exist today.

---

## 1. Why this is needed

Per `codebase_analysis_and_roadmap.md`: `MODIFY` currently returns a static fallback string instead
of actually repairing anything. Your own original architecture doc
(`ControlPlane (Accenture) (1).md`) designed this precisely: *"Repair only what needs repair
instead of regenerating the entire answer"* via *"RAG + micro-prompt/repair model."* This is the
single most visually impressive live-demo moment available to you — showing a response stream in,
get flagged mid-sentence, and get silently patched instead of blocked, is a much stronger judge
moment than a blocked/allowed binary.

## 2. The technique

This is the same underlying idea as retrieval-augmented fact correction / editing pipelines
(e.g., FActScore-style atomic-claim correction, RARR-style retrieve-and-revise). For a hackathon
scope, implement the lightweight version: **targeted regeneration of only the flagged span**,
optionally grounded by retrieved evidence when available, otherwise a constrained re-ask.

## 3. Design

1. **Input**: the flagged span (from SPEC_01's `sentence_scores` or SPEC_02's `entities`), its
   character offsets, the full original response, and the original prompt.
2. **Repair prompt template** (`src/repair/prompts/micro_repair_prompt.txt`):
   ```
   You are correcting ONE flawed sentence within an otherwise correct response.
   Original question: {prompt}
   Full response (for context only, do not repeat it): {full_response}
   Flawed sentence to fix: "{flagged_span}"
   Reason it was flagged: {explanation}
   Rewrite ONLY this sentence to be accurate/safe/non-identifying, in the same style and tense as
   the surrounding text. If the sentence cannot be repaired without fabricating a fact, replace it
   with a neutral statement that the detail is unconfirmed. Output ONLY the replacement sentence,
   nothing else.
   ```
3. **Call path**: use `adapter.generate_once(prompt, temperature=0.3)` — low temperature, this
   needs to be a careful correction, not creative.
4. **Splice**: replace `response_text[span_start:span_end]` with the repair model's output,
   preserving everything else in the original response verbatim (this is what "repair only what
   needs repair" means concretely).
5. **Re-check the spliced result**: run the specific checker(s) that originally flagged the span
   against the NEW spliced text (cheap — single span, not full pipeline) to confirm the repair
   actually resolved the risk before releasing. If it didn't, escalate to `REGENERATE` (SPEC_03's
   next tier) rather than releasing an unverified patch — never release a "repaired" response
   without re-verifying it.
6. **For PII spans specifically** (SPEC_02): skip the LLM repair call entirely and use Presidio's
   own `AnonymizerEngine` (already part of the Presidio install from SPEC_02) for deterministic
   masking/redaction of just that entity span — faster, cheaper, and more reliable than asking an
   LLM to rewrite around PII. Route PII-only-flagged spans through this deterministic path; route
   Performance/Bias/Safety-flagged spans through the LLM micro-repair path in steps 2-4.

## 4. Step-by-step implementation plan

**Step 1** — Create `src/repair/span_repair.py` with two entry points:
`repair_via_llm(span, context, reason, adapter) -> str` and
`repair_via_anonymizer(span, entity_type, analyzer_engine) -> str` (reusing SPEC_02's Presidio
`AnalyzerEngine`/`AnonymizerEngine` instance, don't instantiate a second one).

**Step 2** — In `control_policy.py`'s MODIFY branch (SPEC_03), route each target span to the
correct repair function based on which checker flagged it (PII → anonymizer path, everything
else → LLM micro-repair path).

**Step 3** — Implement the splice-and-reverify logic in step 5 above inside `pipeline.py`, after
`control_policy.py` returns a MODIFY decision with target spans.

**Step 4** — Handle multi-span MODIFY (more than one flagged span in one response): repair each
independently, back-to-front by character offset (so earlier splices don't shift later spans'
offsets), then re-verify the whole spliced result once at the end.

## 5. Definition of Done

- [ ] LLM micro-repair path implemented and produces a replacement sentence, not a full
      regeneration.
- [ ] PII spans route through Presidio's `AnonymizerEngine`, not the LLM path.
- [ ] Splice preserves all non-flagged text verbatim, byte-for-byte.
- [ ] Repaired result is re-checked by the originating checker before release; failed re-checks
      escalate to REGENERATE, never silently release.
- [ ] Multi-span case handled back-to-front without offset corruption.
- [ ] Diagnostic: single-span hallucination repair (verify re-check passes), single-span PII
      redaction (verify anonymizer output), multi-span case (verify all spans corrected and offsets
      intact), and a repair-fails-reverify case (verify it escalates to REGENERATE, not released).
- [ ] Pitch: this is your strongest live-demo moment — script the demo to show a response streaming
      in, catching a flaw mid-sentence, and silently patching it, not just blocking.
