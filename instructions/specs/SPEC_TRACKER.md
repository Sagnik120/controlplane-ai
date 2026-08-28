# SPEC_TRACKER.md — Master tracker for research-upgrade specs (Post-Phase-9 stage)

Legend: `[ ]` not started · `[~]` spec written, not yet coded · `[x]` coded + tested

## Batch 1 — Detection Layer
- [x] `SPEC_01_performance_checker_selfcheckgpt.md`
- [~] `SPEC_02_pii_checker_presidio_hybrid.md`

## Batch 2 — Decision Logic Layer
- [x] `SPEC_03_decision_logic_conformal_routing.md`

## Batch 3 — Detection Layer
- [x] `SPEC_04_bias_safety_llm_as_judge.md`

## Batch 4 — Aggregation & Session Layer
- [x] `SPEC_05_overlap_aware_risk_engine.md`
- [x] `SPEC_06_multiturn_context_window.md`

## Batch 5 — Governance Loop (ALL SPECS NOW WRITTEN)
- [~] `SPEC_07_feedback_loop_active_learning.md`
  Reuses SPEC_03's conformal calibration script; harvests human-reviewed queue items into a
  growing calibration set; recalibrates thresholds periodically with a before/after audit trail.
- [~] `SPEC_08_intelligent_edit_repair.md`
  Real span-level MODIFY: LLM micro-repair for Performance/Bias/Safety spans, Presidio
  AnonymizerEngine for PII spans, splice + re-verify before release, escalate to REGENERATE on
  failed re-check. Strongest live-demo moment.

---
All 8 planned specs are now written. Execute strictly in numeric order per the rules in
`00B_SPEC_UPGRADES.md`. Update `[~]` -> `[x]` only after each spec's Definition of Done passes on
real terminal output.
