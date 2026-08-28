# SPEC_07 — Feedback Loop: Recalibrate Conformal Thresholds from Human-Reviewed Cases

**Status:** Ready to implement
**Touches:** `src/policy/control_policy.py`, `scripts/calibrate_thresholds.py` (from SPEC_03),
new `src/feedback/feedback_store.py`, `data/human_review_queue.jsonl` (already exists per SPEC_03)
**Depends conceptually on:** SPEC_03's conformal calibration mechanism (reuses its formula) —
if SPEC_03 isn't coded yet, this spec still stands alone as a design doc, but cannot run until
SPEC_03's `scripts/calibrate_thresholds.py` exists.

---

## 1. Why this is needed

Per `01_PRD.md` non-goals, a full learning system was explicitly deferred. Per
`codebase_analysis_and_roadmap.md`: "No mechanism exists to learn from mistakes." The PS asks
directly: *"how flagged or overridden cases feedback to improve detection quality over time."*
A static calibration (SPEC_03) computed once from a small seed set will drift as real traffic
diverges from that seed set — this closes the loop without requiring model fine-tuning (out of
scope per `01_PRD.md`).

## 2. The idea (no single paper — synthesized from established practice)

This is standard **active learning / human-in-the-loop recalibration**, not a novel technique to
cite — the credible claim is "we close the loop that conformal prediction requires to stay valid
over time," not "we invented a new algorithm." Split-conformal calibration (SPEC_03) is only
statistically valid for data drawn from the same distribution as the calibration set — as real
traffic accumulates and a human reviewer confirms/overrides `HUMAN`-escalated or borderline cases,
those labeled examples are exactly what conformal calibration is designed to be re-run on. This is
the textbook conformal-prediction maintenance loop (see Angelopoulos & Bates, arXiv:2107.07511,
already cited in SPEC_03, §5 "online/adaptive conformal prediction").

## 3. Design

1. Every record written to `data/human_review_queue.jsonl` (SPEC_03) gets an added field once a
   human resolves it: `human_verdict: "confirm_risk" | "override_allow" | "override_block"`.
2. A new `FeedbackStore` (`src/feedback/feedback_store.py`) reads resolved review-queue entries
   plus any human override recorded elsewhere in the audit log, and appends them to
   `data/calibration_set.jsonl` (the same file SPEC_03's calibration script reads) — this makes the
   calibration set grow over time instead of staying frozen at its original 30-100 seed examples.
3. `scripts/calibrate_thresholds.py` (already built in SPEC_03) is re-run periodically — for a
   hackathon prototype, expose it as a manual `scripts/recalibrate.py` command the human runs, not
   an automated cron job (matches `03_Rules.md`'s "agent never runs commands" constraint and avoids
   over-scoping).
4. Log every recalibration event (old thresholds, new thresholds, calibration set size, delta) to
   `data/calibration_history.jsonl` — this is your "did the system actually get better" audit trail
   for the pitch, and a concrete answer to the PS's "metrics to a skeptical stakeholder" ask.

## 4. Step-by-step implementation plan

**Step 1** — Extend `human_review_queue.jsonl` schema with `human_verdict` and `resolved_at`
fields; add a minimal CLI or dashboard form field for the human to record a verdict on a queued
item (reuse existing dashboard, don't build a new UI surface).

**Step 2** — Implement `FeedbackStore.harvest_new_examples()`: reads unresolved-turned-resolved
queue entries since the last harvest, converts each into a calibration example
(`{response, risk_scores, ground_truth_label}`), appends to `data/calibration_set.jsonl`, dedupes
by request_id.

**Step 3** — Wrap SPEC_03's calibration script call in `scripts/recalibrate.py`: harvest new
examples, re-run `calibrate_thresholds.py`, diff old vs. new thresholds, write to
`data/calibration_history.jsonl`, print a human-readable summary.

**Step 4** — Add a safety rail: refuse to recalibrate if fewer than N new examples (e.g. 10) have
been harvested since the last run — prevents thrashing thresholds on tiny noisy batches. Make N a
config value in `configs/use_case_policies.yaml`.

## 5. Definition of Done

- [ ] `human_verdict` capturable per review-queue entry.
- [ ] `FeedbackStore` harvests resolved entries into the growing calibration set, deduped.
- [ ] `scripts/recalibrate.py` runs end-to-end, produces a before/after threshold diff.
- [ ] `data/calibration_history.jsonl` logs every recalibration event.
- [ ] Diagnostic: seed calibration set, simulate 15 human-resolved review items (mix of confirms/
      overrides), run recalibration, confirm thresholds shift in the expected direction (e.g. more
      overrides of over-flagged ALLOW-worthy cases → `tau_low` relaxes slightly).
- [ ] Pitch framing: "we didn't have time to build automatic fine-tuning, so we built the
      statistically correct maintenance loop for our conformal thresholds instead — this is the
      textbook mechanism, not a shortcut."
