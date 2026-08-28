# ControlPlane.ai — Round 2 Upgrade Tracker

This file tracks which research-backed upgrade specs have been written and which are still pending.
Each spec is a **standalone, independently implementable** `.md` file your coding agent can follow
without needing the others in context. Feed them to the agent ONE AT A TIME.

Legend: `[ ]` not started · `[~]` spec written, not yet coded · `[x]` coded + tested

---

## Batch 1 — Detection Layer (core "checking mechanism" novelty)

- [x] `01_performance_checker_selfcheckgpt.md`
  Replaces hard-coded hedge-phrase regex in `performance_checker.py` with a black-box,
  zero-resource hallucination/uncertainty detector based on **SelfCheckGPT** (Manakul et al.,
  EMNLP 2023) — sampling + consistency scoring. No model internals needed → fits the
  "consume via API" constraint from the PS.

- [x] `02_pii_checker_presidio_hybrid.md`
  Replaces static regex PII detection with a **Presidio-style hybrid pipeline**
  (regex + checksum recognizers + transformer NER model, e.g. `piiranha`/`bert-base-NER`
  from HuggingFace) plus a context-window scoring layer. Directly answers the PS line about
  "dedicated PII/entity detection."

## Batch 2 — Decision Logic Layer (directly answers "blocked, edited, or escalated")

- [x] `03_decision_logic_conformal_routing.md`
  Upgrades `control_policy.py` from fixed `if score > threshold` rules to a
  **conformal-prediction-calibrated tiered router** (ALLOW / MODIFY / REGENERATE / HUMAN)
  with statistical coverage guarantees instead of arbitrary thresholds. This is the
  single highest-novelty change for judges — it's the difference between "we picked 0.7
  because it felt right" and "we can state a mathematically guaranteed error rate."

## Batch 3 — Not yet written (say "continue" to generate next)

- [ ] `04_bias_safety_llm_as_judge.md` — Replace keyword-based bias/safety checkers with a
  lightweight secondary-LLM-as-judge pattern + calibrated rubric (G-Eval / RAGAS-style).
- [ ] `05_overlap_aware_risk_engine.md` — Replace the static +0.15 overlap penalty with
  dynamic severity-weighted overlap scoring.
- [ ] `06_multiturn_context_window.md` — Rolling-window multi-turn risk compounding.
- [ ] `07_feedback_loop_active_learning.md` — Human-override feedback → threshold/model tuning.
- [ ] `08_intelligent_edit_repair.md` — Replace static `[REDACTED BY POLICY]` with targeted
  span-level repair (RAG + micro-repair prompt), matching the original MODIFY design in
  `ControlPlane (Accenture) (1).md`.

---

## How to use these files with your coding agent

1. Give the agent **one spec file at a time**, in the batch order above.
2. Each spec contains: the source technique + citation, why it's better than current logic,
   exact data contracts (inputs/outputs), a step-by-step implementation plan mapped to your
   existing `src/` file structure, and a "Definition of Done" checklist.
3. After the agent finishes a spec, update this tracker (`[~]` → `[x]`) before moving to the next.
4. Do NOT hand the agent multiple specs at once — it increases hallucination risk on which
   files to touch. One spec = one PR = one focused task.
