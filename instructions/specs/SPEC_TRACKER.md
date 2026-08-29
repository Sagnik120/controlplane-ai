# SPEC_TRACKER.md — Stage 3 Master List (Post SPEC_01–03)

## STATUS: AUTHORITATIVE. This is the ONLY source of truth for "what's next." Do not treat
## `04_Phases.md`, `new_phases.md`, or the old SPEC_01–03 files as defining remaining work — all
## of that is closed/historical. This file supersedes the tracker previously at this path.

---

## 0. How This Stage Works (read before touching anything)

- Each row below is an **upgrade target**, not a spec. A target only becomes workable once a
  `SPEC_NN_<slug>.md` file exists in this same `specs/` folder for it. Sagnik writes/researches
  and hands you that file when he's ready for that item — you do not invent the approach yourself.
- If asked to work on an item that has no corresponding `SPEC_NN_*.md` file yet: **stop and say
  so.** Do not guess a method, do not start editing files "to get ahead." Propose nothing beyond
  restating the problem framing already given below.
- Work on exactly ONE spec at a time, in the priority order below, unless Sagnik explicitly
  reorders it.
- A spec's own "Touches:" line (once written) is the only files you may edit for that spec.
- When a spec is completed and its Definition of Done passes, flip its row to `[x]`, add one line
  to `06_Memory.md` under `## Spec Upgrades (Post-Phase-9)`, update `docs/progress.md`, then STOP
  and wait for the next spec file.

---

## 1. Closed / Done (history — do not reopen without explicit instruction)

| # | Spec file (deleted, kept here for record) | What it shipped |
|---|---|---|
| 01 | `SPEC_01_performance_checker_selfcheckgpt.md` | Performance Checker rebuilt on SelfCheckGPT (NLI + BERTScore ensemble) |
| 02 | `SPEC_02_pii_checker_presidio_hybrid.md` | PII Checker rebuilt on Presidio + Piiranha NER + noisy-OR aggregation |
| 03 | `SPEC_03_decision_logic_conformal_routing.md` | Control Policy rebuilt on conformal-prediction tiered routing (tau_low/tau_high) |
| 04 | `SPEC_04_bias_safety_llm_as_judge.md` | Bias/Safety Checkers rebuilt on calibrated LLM-as-judge (taxonomy-in-prompt for safety, anti-over-flagging rubric for bias), with a keyword pre-filter kept only as a latency-saving trigger, not the verdict. Does **not** map to any of the 14 Stage 3 tracker items below — this is a checker-quality upgrade in the same spirit as SPEC_01/02, not a hardening item. |
| 05 | `SPEC_05_overlap_aware_risk_engine.md` | Static `+0.15` overlap penalty replaced with noisy-OR combination + an editable category-pair severity-multiplier matrix (`configs/overlap_severity_matrix.yaml`). **Fulfills tracker item #07** (real semantic/severity-aware overlap detection). |
| 06 | `SPEC_06_multiturn_context_window.md` | New `src/session/session_state.py` — `SessionRiskState` tracking semantic drift (TCA-style, cosine distance from initial + previous turn) and cumulative PII exposure (CAMP-style, distinct-entity-type counting) across a session, feeding `control_policy.py` as an additional HUMAN-escalation input. Does **not** map to any of the 14 tracker items directly — it's new capability, not one of the 14. **Important:** this spec explicitly keeps session state in-memory (`Dict[str, SessionRiskState]`) by design, citing `01_PRD.md`'s non-goals — it does **not** solve item #12 (session state off in-memory dict / Redis). #12 remains open. |
| 07 | `SPEC_07_feedback_loop_active_learning.md` | `FeedbackStore` harvests resolved `human_review_queue.jsonl` entries into a growing `calibration_set.jsonl`; `scripts/recalibrate.py` re-runs SPEC_03's calibration and logs before/after thresholds to `calibration_history.jsonl`. **Fulfills tracker item #08** (live HUMAN feedback loop). |
| 08 | `SPEC_08_intelligent_edit_repair.md` | `src/repair/span_repair.py` — LLM micro-repair path for Performance/Bias/Safety spans, Presidio `AnonymizerEngine` deterministic path for PII spans, splice-and-reverify before release (escalates to REGENERATE if a repair doesn't pass re-check). **Spec called for character-offset-based splicing, but the shipped code does not match this** — `src/orchestrator/pipeline.py` line 88 uses `repaired_text.replace(span_text, replacement, 1)`, a string-search replace. Confirmed against the running codebase. This means item **#14 (fragile splicing) is still open** — SPEC_08 did not close it despite its own stated design. |
| 09 | `SPEC_09_regeneration_backtrack_resample.md` | Real REGENERATE — Checkpoint-Backtrack Regeneration (CBR): backtrack to last clean span checkpoint, targeted regen prompt with localized checker verdict, re-verify tail, capped at 2 backtrack escalations before HUMAN. **Fulfills tracker item #04**. |

These are functioning in the live pipeline. Do not re-derive, re-explain, or re-justify them unless
a new spec explicitly asks you to touch `performance_checker.py`, `pii_checker.py`,
`control_policy.py`, `span_repair.py`, `risk_engine.py`, `session_state.py`,
`feedback_store.py`, `bias_checker.py`, `safety_checker.py`, or `pipeline.py`'s REGENERATE branch
again.

**File numbering:** `SPEC_04` through `SPEC_09` are all now accounted for (see table above). The
next genuinely new spec file should be numbered `SPEC_10` (one higher than the highest existing
spec file).

---

## 2. Pending — Upgrade Targets (Stage 3)

Legend: `[ ]` no spec written yet — do not start · `[~]` spec handed to you, in progress ·
`[x]` spec's Definition of Done passed and confirmed by Sagnik

Ordered by priority. This order reflects impact-on-demo-score, not necessarily the order Sagnik
will hand you specs in — if he hands you SPEC_09 for item 4 before item 1 has a spec, follow the
spec you were given.

### Tier A — makes the demo airtight (do these first)

- [x] **04 — Real REGENERATE.** DONE via `SPEC_09_regeneration_backtrack_resample.md`
  (Checkpoint-Backtrack Regeneration). Backtracks to the last span checkpoint that passed all
  three checkers cleanly, builds a targeted regeneration prompt containing the clean prefix plus
  the specific failed checker's verdict (not a generic "try again"), regenerates only the tail with
  the same model, re-verifies through the Risk Engine, and caps escalation at 2 backtrack attempts
  (checkpoint → half-response) before falling through to HUMAN.
  **Touched:** `src/repair/span_repair.py` (new `regenerate_from_checkpoint()`),
  `src/orchestrator/pipeline.py` (REGENERATE branch now calls it, loops on `attempt_num`),
  `src/policy/control_policy.py` (now exposes `last_clean_checkpoint_id`), plus a new synthetic
  test fixture (span 1–2 clean, span 3 PII failure) confirming only span 3+ regenerates.
  **Verify before marking fully closed:** confirm Sagnik has run the new test fixture and
  `run_all_diagnostics.py` and both passed — if not yet confirmed, treat as `[~]` in practice even
  though the spec content is complete.

- [ ] **05 — Fix latency (core PS requirement).** The 3 checkers run sequentially, not via
  `asyncio.gather`. Additionally, the SelfCheckGPT-based Performance Checker (SPEC_01) runs on
  every single request regardless of need, and it is the most expensive component in the pipeline
  by a wide margin. "Don't slow the AI down" is explicit in both problem statements — this is the
  single biggest scoring risk in the current build. Awaiting spec.
  **Touches (expected):** `src/engine/risk_engine.py`, `src/checkers/performance_checker.py`,
  `src/orchestrator/guarded_call.py`.

- [ ] **06 — Differentiate latency/risk budget by use case, live.** `configs/use_case_policies.yaml`
  already defines a `latency_budget_ms` per use case, but the checker cost is currently identical
  regardless of which use case is active — the config value is not actually read by anything that
  changes runtime behavior. Customer-facing calls should be able to skip or lighten heavy checks
  vs. internal/batch calls. Awaiting spec. Depends conceptually on #05 being done first (nothing to
  differentiate until checking is conditional).
  **Touches (expected):** `src/policy/policy_loader.py`, `src/engine/risk_engine.py`.

- [x] **07 — Real semantic overlap detection.** DONE via `SPEC_05_overlap_aware_risk_engine.md`.
  Noisy-OR combination of overlapping checker scores + editable severity-multiplier matrix per
  category pair, with the paradigm case (fabricated fact about a named person = Performance+PII
  overlap) weighted highest (1.8x). Note: this is severity-weighting, not embedding-similarity
  span matching — the underlying span-intersection detection itself was reportedly left as-is
  (spec says "keep the existing span-intersection detection logic... don't rewrite what isn't
  broken"). If two checkers flag semantically-identical but non-overlapping character spans, that
  may still be missed — confirm with Sagnik whether this residual gap matters for the demo or is
  acceptable as scoped.
  **Touched:** `src/engine/risk_engine.py`, new `configs/overlap_severity_matrix.yaml`.

- [x] **08 — Live HUMAN feedback loop.** DONE via `SPEC_07_feedback_loop_active_learning.md`.
  `FeedbackStore` harvests resolved `human_review_queue.jsonl` entries into a growing
  `calibration_set.jsonl`; `scripts/recalibrate.py` re-runs SPEC_03's calibration script and logs
  before/after threshold diffs to `calibration_history.jsonl`. Note: this is a manually-triggered
  script the human runs (not an automated live loop inside the running server), by explicit design
  per `03_Rules.md`'s "agent never runs commands" constraint — confirm this framing ("we built the
  statistically correct maintenance loop, triggered on demand" rather than "fully automatic") is
  what gets said in the pitch, since "live" could be overclaimed otherwise.
  **Touched:** `src/feedback/feedback_store.py`, `scripts/recalibrate.py`,
  `data/human_review_queue.jsonl` (extended schema), `data/calibration_history.jsonl` (new).

### Tier B — makes it feel enterprise-serious

- [x] **09 — Agent/tool-call risk modeling.** DONE via `SPEC_14.md`.
  Preemptively intercepts agent tool calls (actions) before execution. Utilizes a deterministic `action_catalog.yaml` (blast radius / reversibility) for Tier-0 screening, and reuses `SemanticOverlapDetector` to check if action arguments overlap with any flagged text risks. Only triggers a Tier-1 LLM judge if escalation criteria are met, explicitly splitting the text-level decision (e.g. ALLOW) from the action-level decision (e.g. HOLD).
  **Touched:** `src/agent/action_gate.py`, `src/agent/action_catalog.yaml`, `src/orchestrator/pipeline.py`, `src/audit/audit_logger.py`, `tests/test_spec_14_action_gate.py`.

- [ ] **10 — Fully async pipeline.** `adapters/` and `orchestrator/pipeline.py` are fully
  synchronous. A single request currently blocks the Python thread for the full duration of
  generation + checking + repair + re-checking. This is a prerequisite for #05 being real rather
  than cosmetic. Awaiting spec.
  **Touches (expected):** `src/adapters/*.py`, `src/orchestrator/guarded_call.py`,
  `src/api/routes.py`.

- [ ] **11 — Metrics/monitoring dashboard.** No current answer to "how do you report
  trustworthiness to a skeptical stakeholder" — the PS asks this explicitly. Need: false
  positive/negative rate, per-tier (ALLOW/MODIFY/REGENERATE/HUMAN) counts, cost saved. Awaiting
  spec. Builds on the existing `docs/metrics_report.md` script from Phase 8 — extend, don't
  duplicate.
  **Touches (expected):** new `src/dashboard/` additions, a metrics endpoint in `src/api/routes.py`.

- [ ] **12 — Session state off in-memory dict.** **CONFIRMED still open** (verified against the
  running codebase). `session_state.py` stores everything in a module-level `self.sessions = {}`
  dict — purely in-memory, will drop data or fail outright under concurrent load or multiple pods.
  SPEC_06 (multi-turn session risk tracking) built the risk logic on top of this same dict by
  explicit design and did not address the storage backend — a judge would spot this as the
  real production-readiness gap it is. Needs Redis or an equivalent, or at minimum a convincing
  fake + documented next step. Awaiting spec.
  **Touches (expected):** `src/session/session_state.py`.

### Tier C — "next steps if judges ask about scaling" polish

- [ ] **13 — Audit/feedback logs off JSONL.** `audit_log.jsonl` and `human_review_queue.jsonl` have
  no concurrency safety and no queryability, which #11's dashboard will need. SQLite is sufficient
  per `02_Architecture.md`'s existing storage constraint (no Postgres/MySQL/cloud DB). Awaiting spec.
  **Touches (expected):** `src/audit/logger.py`, `src/audit/reader.py`, `src/feedback/feedback_store.py`.

- [ ] **14 — Fix fragile span splicing.** **CONFIRMED still broken** (verified directly against
  the running codebase, not just inferred from the spec text). `SPEC_08_intelligent_edit_repair.md`
  specified character-offset-based splicing, but the shipped code in `src/orchestrator/pipeline.py`
  (line 88) actually does `repaired_text = repaired_text.replace(span_text, replacement, 1)` — a
  string-search replace, not an offset-based one. If the flawed sentence's exact text repeats
  elsewhere in the response, or whitespace/formatting shifts between detection and repair, this
  breaks. Genuinely awaiting a spec — SPEC_08 did not close this despite its own stated design.
  **Touches (expected):** `src/orchestrator/pipeline.py` (line 88 area), `src/repair/span_repair.py`.

- [ ] **15 — Governance/config layer polish.** `configs/use_case_policies.yaml` is currently only
  editable by hand. A small admin UI or CLI to adjust it live would let Sagnik demo "here's how
  we'd vary this by geography/regulation" instead of just describing it. Awaiting spec.
  **Touches (expected):** new `scripts/` or `src/dashboard/` addition — TBD by spec.

- [ ] **16 — Clean up the conformal prediction claim.** SPEC_03 (`control_policy.py`) is currently
  mostly rule-based YAML threshold lookups dressed in conformal-prediction language. Either
  actually compute non-conformity scores against a real calibration set, or soften the pitch
  language so a technical judge can't catch the gap. Awaiting spec — this is a judgment call
  Sagnik needs to make explicitly (fix the math vs. fix the claim), not something to guess at.
  **Touches (expected):** `src/policy/control_policy.py`, `scripts/recalibrate.py`, pitch deck
  language (outside this codebase).

- [ ] **17 — Small polish pass.** README/demo script, consistent logging format across all
  modules, graceful error handling around checker failures (what happens if the PII checker itself
  crashes mid-request — verify `03_Rules.md` section 4's "neutral/conservative risk score on
  failure" rule actually holds for every checker), and unit test coverage for the new REGENERATE
  path once #04 exists. Awaiting spec — likely split into several small specs rather than one.
  **Touches (expected):** `README.md`, various, plus new `tests/` files.

---

## 3. Explicit Non-Rule

**Do not merge, reorder, skip, or combine these items on your own initiative.** If two items look
related enough to do together (e.g. #10 async makes #05 and #06 easier), say so and propose it —
but wait for Sagnik's go-ahead before treating it as one unit of work. The numbering above is fixed
so it stays referenceable in conversation and in `06_Memory.md` entries.