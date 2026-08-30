# ControlPlane-AI -- Pipeline Overview

> **Context:** Actual implemented codebase (August 2026), not original proposal.

## 1. Problem & Architecture

**Problem:** Uncontrolled runtime LLM risks (Performance/Hallucination, Cost, Responsibility/Safety/PII). We need a policy engine to intercept and apply 5 tiers: ALLOW, MODIFY (localized repair), REGENERATE (diffuse repair), BLOCK (critical error), HUMAN (escalation).

**Proposed vs. Implemented:**
- *Proposed:* Grey-box, streaming interception, token entropy hallucination gating, ACI threshold recalibration from human feedback, dynamic routing.
- *Implemented:* Black-box, post-generation async pipeline. Gemini generation is fully awaited before 4 parallel checkers run. ACI singleton uses static/fallback thresholds. UI is vanilla HTML/FastAPI (no stream). 
- *Missing:* True streaming, token logit access, dynamic routing, real human review queue, RAG.

## 2. End-to-End Flow & Interventions

**UI -> API -> Gemini Flow:**
Browser (`src/ui/script.js`) POSTs to FastAPI `/api/chat`. `dependencies.py` selects `GeminiAdapter(model="gemini-3.6-flash")` (if `.env` has key) or `MockAdapter`. `PipelineOrchestrator` generates full response via Gemini.

**Risk Engine & Aggregation:**
`RiskEngine` runs checkers asynchronously (ThreadPoolExecutor). Scores (0.0 to 1.0) are extracted. `SemanticOverlapDetector` multiplies overlapping risks. Overall risk = max(all scores and overlap risks).

**Control Policy (ALLOW / MODIFY / REGENERATE / BLOCK / HUMAN):**
`ControlPolicy` compares results against thresholds (`tau_low`, `tau_high`):
- `is_error` -> **BLOCK**
- `score >= tau_high` -> **HUMAN** (logged to `human_review_queue.jsonl`, no actual UI)
- `score >= tau_low` -> **NEEDS_REPAIR** (if <25% text affected -> **MODIFY**, else -> **REGENERATE**)
- Overrides: Session drift or cumulative PII -> **HUMAN**

**Intervention (Repair & Regeneration):**
- **MODIFY:** `SpanRepairEngine` replaces PII via Presidio and other risks via LLM micro-prompt (`temp=0.2`). Uses `.replace()`.
- **REGENERATE:** `CheckpointManager` grabs clean prefix. `RegenerationEngine` calls adapter to continue. 
- Both require full re-verification.

**Multi-turn (Session):**
In-memory `SessionStore` tracks Semantic drift (cosine distance from initial intent) and cumulative PII (count of entities). NOTE: UI `script.js` does NOT re-send `session_id`, breaking this feature.

## 3. Checkers

| Checker | Method & Model | Key Limitations |
|---------|----------------|-----------------|
| **Performance** | Tier-0: Text length heuristic (NOT entropy). Tier-1: SelfCheckGPT (NLI + BERTScore). | N=3 extra Gemini calls per request. |
| **Safety** | Keyword pre-filter + LLM-as-judge Gemini prompt. | Depends on Gemini API. Errors cause BLOCK. |
| **Bias** | Keyword pre-filter + LLM-as-judge Gemini prompt. | Same as Safety. |
| **PII** | Presidio + piiranha HuggingFace NER + India regex (PAN/Aadhaar). | Anonymizes via Presidio. |
| **Cost** | Word count approximation. | No actual token limit enforcement. |

## 4. Current Validation & Limitations

**Validation:**
- `test_end_to_end_pipeline.py`: 6/6 PASS using MockAdapter.
- `live_gemini_smoke.py`: Passes with `gemini-3.6-flash` (Action ALLOW, Risk 0.10).

**Critical Bug (Blocker):**
- **Pipeline Bug:** In `pipeline.py`, risk evaluation, repair, and logging are inside the `except Exception` block of generation. If Gemini generation succeeds, execution hits the outer exception handler and returns **BLOCK**. Real Gemini requests will ALWAYS block until this try/except scope is fixed.

**Other Limitations:**
- Span repair `.replace()` is brittle.
- LLM judges can fail JSON parsing.
- Sessions are in-memory (lost on restart).
- Single process, no authentication, latency budget easily exceeded (up to 6 Gemini calls per run).
