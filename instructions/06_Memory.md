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
- Next immediate step: Wait for instruction.
