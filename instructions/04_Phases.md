# 04_Phases.md — Build Phases

## STATUS: AUTHORITATIVE. Complete phases IN ORDER. Do not start Phase N+1 until Phase N's exit
## criteria are met and confirmed by the human running the diagnostic script for that phase.
## No phase is defined by time or days — only by completion of its exit criteria.

---

## Phase 0 — Project Skeleton

**Goal**: Folder structure, environment, and empty scaffolding exist and run.

Tasks:
- Create the full folder structure exactly as defined in `08_Folder_Structure.md`.
- Create `.env.example` (placeholder keys only, no real values) and a `.gitignore` that excludes
  `.env`, `__pycache__/`, `*.pyc`, `.venv/`.
- Create `requirements.txt` with the libraries listed in `02_Architecture.md`.
- Create a minimal FastAPI app with a single `GET /health` endpoint returning `{"status": "ok"}`.
- Output the exact terminal commands needed to create a virtual environment, install dependencies,
  and run the server. Do not run them yourself.

**Exit criteria**: Human runs the given commands, hits `/health`, confirms `{"status": "ok"}` in
their browser or curl, and pastes the result back.

---

## Phase 1 — LLM Adapter Layer

**Goal**: Prove the model-agnostic interface works before anything else is built on top of it.

Tasks:
- Implement `BaseLLMAdapter` abstract class with `generate_stream(prompt: str) -> Iterator[str]`.
- Implement `MockAdapter` — deterministic canned responses, including at least 3 deliberately flawed
  outputs (one biased-sounding, one containing fake PII, one confidently-wrong-sounding) selectable
  by a keyword in the prompt for demo repeatability.
- Implement `GeminiAdapter` using `google-generativeai`, reading the API key only from environment
  variables via `.env`.
- Write a diagnostic script (see `07_Test.md`) that calls both adapters with the same prompt and
  confirms both return a non-empty stream, logging output to terminal only (no secrets printed).

**Exit criteria**: Human runs the adapter diagnostic script for both `mock` and `gemini` and confirms
output in terminal for both.

---

## Phase 2 — Individual Checkers

**Goal**: Each checker works in isolation before being combined.

Tasks:
- Implement Performance Checker (heuristic-based: hedging phrases, contradiction detection,
  optionally token-probability signal if using Gemini's returned data).
- Implement Safety Checker (keyword/pattern based unsafe content detection, extensible list).
- Implement Bias Checker (heuristic pattern detection for stereotyping/discriminatory phrasing).
- Implement PII Checker (regex/entity detection for emails, phone numbers, SSN-like patterns, names
  near sensitive keywords).
- Implement Cost Monitor (token counting, model tier used, generation time, cost-risk formula).
- Each checker gets its own diagnostic script under `tests/<checker_name>/` that runs it against at
  least 5 hand-crafted inputs (clearly-safe, clearly-flagged, and 1 ambiguous case) and prints
  pass/fail per case.

**Exit criteria**: Human runs each checker's diagnostic script individually, confirms expected
scores appear in terminal for all 5 checkers.

---

## Phase 3 — Risk Engine + Overlap Detection

**Goal**: Combine checker outputs into one RiskProfile, detect overlapping risk categories.

Tasks:
- Implement Risk Engine that calls all checkers (async/parallel where possible) and assembles the
  `risk_profile` object defined in `02_Architecture.md`.
- Implement overlap detection: if two checkers flag the same span of text, mark it as an overlap
  (e.g., `"overlaps_detected": ["performance+pii"]`).
- Diagnostic script that feeds a known overlapping case (fabricated detail about a person) and
  confirms both checkers fire and the overlap is recorded.

**Exit criteria**: Human runs the Risk Engine diagnostic script, confirms a full risk_profile object
prints correctly, including at least one confirmed overlap case.

---

## Phase 4 — Use-Case Policy Config + Control Policy

**Goal**: Same risk profile produces different decisions depending on use case.

Tasks:
- Implement `configs/use_case_policies.yaml` exactly as specified in `02_Architecture.md`.
- Implement Control Policy function: loads thresholds for the given `use_case`, compares against
  the risk profile, returns Decision object (ALLOW/MODIFY/REGENERATE/HUMAN + reason string).
- Diagnostic script: run the SAME fixed risk_profile through all 3 use cases and confirm the decision
  differs where expected (e.g., allowed under chatbot config, escalated to HUMAN under regulated
  config).

**Exit criteria**: Human runs the diagnostic script, confirms differing decisions printed per use
case for identical input risk profile.

---

## Phase 5 — Audit Log

**Goal**: Every decision is durably logged and readable.

Tasks:
- Implement `append_log()` writing to `audit_log.jsonl` using the schema in `02_Architecture.md`.
- Implement a simple `GET /audit-log` endpoint or a read script that lists recent N records.
- Diagnostic script: run 5 requests through the full pipeline, confirm 5 corresponding records exist
  in the audit log with correct fields populated.

**Exit criteria**: Human runs the diagnostic script, confirms audit log file has correct entries,
inspects at least one entry manually for correctness.

---

## Phase 6 — Full Orchestrator Integration

**Goal**: All previous phases wired together into a single `guarded_call()` entrypoint.

Tasks:
- Implement `guarded_call(prompt, use_case, llm_provider)` that runs the entire pipeline from
  Architecture diagram section 1, end to end.
- Implement `POST /generate` FastAPI endpoint calling `guarded_call()`.
- Full integration diagnostic script (see `07_Test.md`) running the 15+ predefined test prompts
  through the real endpoint and confirming decisions match expectations.

**Exit criteria**: Human runs the full integration diagnostic script, confirms all test cases produce
sane, logged, explainable decisions. Any mismatch is flagged and fixed before moving on.

---

## Phase 7 — Dashboard UI

**Goal**: Visual demonstration of the live pipeline.

Tasks:
- Build a minimal dashboard: prompt input, use case dropdown, LLM provider dropdown, live checker
  score display as response streams in, final decision display, and a simple audit log table view.
- Wire it to the `/generate` and `/audit-log` endpoints.

**Exit criteria**: Human manually exercises the dashboard for at least 5 scenarios (one per decision
type plus one use-case-switch comparison) and confirms visually correct behavior.

---

## Phase 8 — Metrics Summary

**Goal**: Aggregate reporting over the test set for the "skeptical stakeholder" requirement.

Tasks:
- Script that reads `audit_log.jsonl` and reports: count per decision type, and a manually-labeled
  false positive/negative estimate over the 15+ test prompts (labels defined by human in
  `07_Test.md`).

**Exit criteria**: Human runs the metrics script, confirms output is readable and correct against
manual expectations.

---

## Phase 9 — Documentation, README, Final Polish

**Goal**: Submission-ready repository.

Tasks:
- Write final `README.md` (implementation approach, architecture, dependencies, execution
  instructions) — content drafted with GPT, verified line-by-line by the human.
- Final pass over `docs/progress.md` to ensure it reflects true final state.
- Confirm `.env` is not committed, confirm `.gitignore` is correct, confirm commit history is clean
  and descriptive (see `10_Git_Discipline.md`).

**Exit criteria**: Human clones the repo fresh into a new folder and successfully runs it using only
the README instructions, with no additional undocumented steps.
