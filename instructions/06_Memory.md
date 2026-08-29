# 06_Memory.md — Living Memory Log

## STATUS: LIVING DOCUMENT. Append to this file — never delete prior entries. This is how you
## (the agent) recover context after a session reset without re-reading the entire codebase.
## Update this after completing EACH phase, and any time you pause mid-phase for the day.

---

## How to Use This File (instructions to the agent)

1. At the start of any new session, read this file FIRST, in full, before touching any code.
2. After finishing a phase (or a meaningful chunk of work within a phase), append a new entry below
   using the template.
3. Never rewrite or delete previous entries — this is an append-only log, like a diary. If something
   from an earlier entry turns out to be wrong, add a NEW entry correcting it; do not edit history.
4. Keep each entry short and factual — no more than ~10 lines. This file is meant to be cheap to
   re-read, not a full report (that's what `docs/progress.md` is for).

### Entry Template

```
## [Phase X — short label] — <status: DONE / IN PROGRESS / BLOCKED>
- What was built: ...
- What was tested and confirmed by human: ...
- What is still stubbed/incomplete: ...
- Any deviation from the instruction files, and why: ...
- Next immediate step: ...
```

---

## Log Entries

## [Phase 0 — Project Skeleton] — DONE
- What was built: Folder structure, .env.example, .gitignore, requirements.txt, FastAPI scaffold with /health endpoint.
- What was tested and confirmed by human: Health check endpoint is running successfully via uvicorn.
- What is still stubbed/incomplete: All logic components.
- Any deviation from the instruction files, and why: none
## [Phase 1 — LLM Adapter Layer] — DONE
- What was built: BaseLLMAdapter interface, MockAdapter (with flawed cases), GeminiAdapter (using `google-genai`), and deep diagnostic tests.
- What was tested and confirmed by human: All 12/12 deep diagnostic tests passed (including edge cases and empty prompts).
- What is still stubbed/incomplete: Checkers and orchestrator.
- Any deviation from the instruction files, and why: Replaced deprecated `google-generativeai` with `google-genai`.
- Next immediate step: Phase 2 — Implement Individual Checkers (Performance, Safety, Bias, PII) and Cost Monitor.

## [Phase 2 — Individual Checkers] — DONE
- What was built: Pydantic Base CheckerResult, Performance Checker, Safety Checker, Bias Checker, PII Checker, Cost Monitor.
- What was tested and confirmed by human: run_all_diagnostics.py executed and showed SYSTEM STATUS: STABLE.
- What is still stubbed/incomplete: Risk Engine combining these checkers.
- Any deviation from the instruction files, and why: None.
- Next immediate step: Phase 4 — Implement Use-Case Policy Config and Control Policy.

## [Phase 4 — Use-Case Policy Config + Control Policy] — DONE
- What was built: UseCasePolicy and ControlDecision schemas, ControlPolicy logic module.
- What was tested and confirmed by human: test_policy_diagnostic.py executed 8/8 scenarios perfectly.
- What is still stubbed/incomplete: Audit log for decisions.
- Any deviation from the instruction files, and why: None.
- Next immediate step: Phase 5 — Implement Audit Log.

## [Phase 5 — Audit Log] — DONE
- What was built: O(1) performance JSONL AuditLogger.
- What was tested and confirmed by human: test_audit_diagnostic.py verified file creation and JSON schema integrity.
- What is still stubbed/incomplete: Full pipeline integration (Phase 6).
- Any deviation from the instruction files, and why: Upgraded from standard JSON array to JSONL (JSON Lines) to allow O(1) appending and prevent memory crashes on large log files.
- Next immediate step: Phase 6 — Implement Full Orchestrator.

## [Phase 6 — Full Orchestrator Integration] — DONE
- What was built: PipelineOrchestrator that ties LLM, Risk Engine, Control Policy, and Audit Logger together.
- What was tested and confirmed by human: End-to-end diagnostic ran flawlessly across all scenarios, including catastrophic system failure handling.
- What is still stubbed/incomplete: FastAPI integration and Dashboard UI (Phase 7).
- Any deviation from the instruction files, and why: Added an extreme edge-case handler for pipeline exceptions to guarantee audit logging even during server crashes.
- Next immediate step: Phase 7 — Build Dashboard UI and FastAPI routes.

## [Phase 7 — Dashboard UI] — DONE
- What was built: FastAPI routes (`/api/chat`, `/api/policies`), static file mounting, and an ultra-premium HTML/JS/CSS dashboard.
- What was tested and confirmed by human: API diagnostic confirmed routing, health checks, and fallback mechanisms work.
- What is still stubbed/incomplete: Real Gemini LLM integration (currently using MockAdapter for zero-cost demo UI testing).
- Any deviation from the instruction files, and why: Defaulted the `dependencies.py` to `MockAdapter` so you do not drain your free Gemini API credits while testing the UI.
- Next immediate step: Phase 8 — Metrics Summary (Dashboard additions).

## Spec Upgrades (Post-Phase-9)

## [Spec 01 — Performance Checker SelfCheckGPT] — DONE
- What was built: Implemented PerformanceChecker using SelfCheckGPT ensemble (NLI + BERTScore) with thread-safe inference and aggressive sample/result caching.
- What was tested and confirmed by human: End-to-end performance diagnostic overlapping with PII and real-world multi-threading.
- What is still stubbed/incomplete: Cache key could theoretically mismatch across providers if same prompt/response happens exactly but provider differs.
- Any deviation from the instruction files, and why: None.
- Next immediate step: Spec 02.

## [Spec 02 — PII Checker Presidio Hybrid] — DONE
- What was built: Rewrote PII Checker with a Microsoft Presidio hybrid pipeline, custom Piiranha NER HuggingFace model, noisy-OR aggregation, and context-word boosting edge-case resolution.
- What was tested and confirmed by human: Deep real-world diagnostics testing internal vs external policies, obfuscated text, and false-positive resilience.
- What is still stubbed/incomplete: None.
- Any deviation from the instruction files, and why: Used `pii_min_confidence=0.6` in customer support policy per spec definition.
- Next immediate step: Spec 03.

## [Spec 03 — Conformal Tiered Routing] — DONE
- What was built: Rewrote `control_policy.py` to route requests into ALLOW, MODIFY, REGENERATE, or HUMAN based on Conformal Prediction calibrated thresholds (`tau_low`, `tau_high`). Added a span-coverage percentage logic to distinguish targeted MODIFY vs total REGENERATE. Intercepted HUMAN decisions in `audit_logger.py` to write to a dedicated JSONL queue.
- What was tested and confirmed by human: Calibration script ran successfully and wrote boundaries to YAML. Conformal policy diagnostic passed all 5 edge cases (ALLOW, MODIFY, REGENERATE, HUMAN, Overlap Promotion).
- What is still stubbed/incomplete: None.
- Any deviation from the instruction files, and why: None.
- Next immediate step: Wait for instruction.

your existing "Spec Upgrades (Post-Phase-9)" entries, as a new dated entry.)
[Stage 3 Kickoff — Instruction Files Restructured] — DONE
What was built: N/A (documentation restructure, not code). Deleted specs/SPEC_01_*.md, specs/SPEC_02_*.md, specs/SPEC_03_*.md, and the old specs/SPEC_TRACKER.md. Replaced with a new specs/SPEC_TRACKER.md listing the 14 Stage 3 upgrade targets (numbered #04-#17) as problem-statements-only, no method prescribed. Updated 00_ANTIGRAVITY_START_HERE.md, 00B_SPEC_UPGRADES.md, 08_Folder_Structure.md, 09_Progress_Tracker.md to reflect Stage 3.
What was tested and confirmed by human: N/A — instruction-file change only.
What is still stubbed/incomplete: All 14 Stage 3 items are [ ] — no SPEC_NN files written yet. Awaiting Sagnik's research on item #04 (real REGENERATE) first, per SPEC_TRACKER.md priority order.
Any deviation from the instruction files, and why: SPEC_01-03's implementation-detail files were deleted (outcomes preserved as summaries in SPEC_TRACKER.md section 1 and in this file's prior entries above) to stop the agent re-reading closed work as if it were active.
Next immediate step: wait for specs/SPEC_04_<slug>.md (or whichever item Sagnik researches first) before writing any Stage 3 implementation code.

## [Spec 12 — Semantic Overlap] — DONE
- What was built: Rewrote `SemanticOverlapDetector` to use `all-MiniLM-L6-v2` cosine similarity and character IoU to group overlapping flagged spans together into `OverlapGroup` objects, applying noisy-OR escalation.
- What was tested and confirmed by human: Overlap triggers properly.
- What is still stubbed/incomplete: Cross-encoder reranking.
- Any deviation from the instruction files, and why: Replaced CrossEncoder with Bi-Encoder for latency.
- Next immediate step: Spec 13.

## [Spec 13 — ACI Live Feedback] — DONE
- What was built: `AdaptiveCalibrator` and `FeedbackConsumer` for real-time live Conformal Inference based on human override feedback.
- What was tested and confirmed by human: `test_spec_13_aci_feedback.py` confirms boundaries shift correctly.
- What is still stubbed/incomplete: Human admission congestion control.
- Any deviation from the instruction files, and why: Dropped human congestion control (queue math) per user request to defer to v2.
- Next immediate step: Spec 14.

## [Spec 14 — Agent/Tool-Call Risk Gating] — DONE
- What was built: `ActionRiskChecker` Tier-0 catalog gate and Tier-1 LLM judge that separates action block decisions from text decisions, leveraging `SemanticOverlapDetector` for context-aware risk matching.
- What was tested and confirmed by human: `demo_spec_14_actions.py` confirms overlap formatting injects correctly and short-circuits on catalog blast_radius.
- What is still stubbed/incomplete: Nothing.
- Any deviation from the instruction files, and why: JSON flattening and lower cosine threshold needed for embedder to match actions.
- Next immediate step: Wait for instruction.