# Spec 03 — Upgrade `control_policy.py` with Conformal-Prediction-Calibrated Tiered Routing

**Status:** Ready to implement
**Touches:** `src/policy/control_policy.py`, `src/policy/schemas.py`, `configs/use_case_policies.yaml`,
`src/audit/audit_logger.py` (append calibration metadata)
**Depends on:** Specs 01/02 producing well-formed `risk_score` + `confidence` per checker
(already true today, this spec only changes how those scores are *used*, not how they're
produced)
**This is your highest-novelty pitch item** — decision logic is what separates "just a checker
that flags things" from an actual **governed control system**, which is literally the term your
own architecture doc uses ("Control Policy").

---

## 1. Why the current logic is weak

Current `control_policy.py`: deterministic `if score > threshold: BLOCK`. Per the roadmap doc,
only supports `ALLOW`, `BLOCK`, and a static-string `REDACT` — no `MODIFY`/`REGENERATE`/`HUMAN`
distinction, despite your own architecture doc (`ControlPlane (Accenture) (1).md`) explicitly
designing **four** actions: ALLOW / MODIFY / REGENERATE / HUMAN.

Deeper problem the roadmap doesn't fully call out: **the thresholds themselves (0.7, 0.5,
whatever) are arbitrary.** A judge who knows ML can ask "why 0.7 and not 0.6?" and you have no
principled answer. This is the single most common weak point in hackathon "responsible AI"
pitches — everyone has thresholds, nobody can justify them statistically.

## 2. The research this is based on

**Framework:** Conformal Prediction (CP) — a distribution-free statistical calibration method.
Recent LLM-specific applications directly relevant here:

- *Conformal Prediction with Large Language Models for Multi-Choice Question Answering*
  (Kumar et al., 2023, arXiv:2305.18404) — shows CP-derived uncertainty is strongly correlated
  with accuracy and can be used for **selective classification** (deciding when to trust vs.
  abstain), without requiring model retraining or internal access — "model agnostic and easy to
  implement... due to intensive computing costs and limited API access."
- *Mitigating LLM Hallucinations via Conformal Abstention* (Yadkori et al., 2024,
  arXiv:2405.01563) — directly frames CP as an **abstention mechanism**: decide when the model
  should refuse/escalate rather than answer.
- *API is Enough: Conformal Prediction for Large Language Models without Logit-Access* (Su et al.,
  2024) — critically, this variant is designed for exactly your constraint: **no logits, no
  internals, API-only access** (matches the PS's "enterprises consume a foundation model via API").
- *UCCI: Calibrated Uncertainty for Cost-Optimal LLM Cascade Routing* (2025, arXiv:2605.18796) —
  applies calibrated uncertainty specifically to **routing decisions under a cost budget**, which
  maps almost exactly onto your Risk Engine's Performance+Cost+Responsibility multi-signal setup.

**Core idea in plain terms:**
> Instead of hand-picking a threshold like "risk > 0.7 = block," you hold out a small calibration
> set of past (response, true-label) pairs — e.g., from your audit log or a seed set you construct
> — and compute, for a chosen error tolerance α (e.g., "we accept a 5% chance of letting through a
> response we shouldn't have"), the exact score cutoff that **guarantees** that error rate
> *on average*, no matter what the raw checker scores' distribution looks like. This gives you a
> **provable, stated error bound** instead of a guessed number — a materially stronger claim to
> make to judges ("skeptical stakeholder," per the PS's own "Metrics & monitoring" section) than
> "we tuned it until it looked right."

## 3. Design: four calibrated tiers instead of one threshold

Map conformal calibration onto your **existing** four-action design (ALLOW/MODIFY/
REGENERATE/HUMAN) using **two independently calibrated thresholds** per risk dimension, forming
three tiers of increasing severity — this keeps it implementable in hackathon time while still
being genuinely calibrated (not just "two more arbitrary numbers," see §4):

```
risk_score < τ_low(α_low)                      → ALLOW
τ_low(α_low) ≤ risk_score < τ_high(α_high)      → MODIFY   (if issue is localized: see span data
                                                              from Spec 01/02) or REGENERATE
                                                              (if issue is diffuse/whole-response)
risk_score ≥ τ_high(α_high)                     → HUMAN
```

Where `τ_low` and `τ_high` are **not chosen by hand** — they are the calibrated quantiles from
conformal calibration (see §4), one per risk dimension (performance/safety/bias/PII/cost), and
combined via the existing Risk Engine profile (this spec does not change the Risk Engine's
aggregation, only how `control_policy.py` consumes its output).

**MODIFY vs REGENERATE decision rule** (this resolves the current codebase's missing
distinction directly, using data you now have from Specs 01/02):
- If flagged risk maps to **one or few contiguous spans** covering < X% of the response
  (spans available from Spec 01's `sentence_scores` and Spec 02's `entities`) → **MODIFY**
  (targeted repair of just that span, per your architecture doc's RAG+micro-repair design).
- If flagged risk is **diffuse across the whole response**, or performance risk itself is high
  everywhere (SelfCheckGPT flags most sentences as inconsistent) → **REGENERATE**.
- This threshold (X%) is a policy config value, not calibrated — document it plainly as a design
  choice, not a statistical claim, to keep your pitch's calibration claims honest and defensible
  under questioning.

## 4. How to actually calibrate τ_low / τ_high (concrete, no hand-waving)

You do **not** need a large labeled dataset — this is the key practical trick for a hackathon
timeline:

1. **Build a small calibration set** (30–100 examples is enough to demonstrate the method,
   state this sample-size caveat honestly in the pitch): take your `mock_adapter.py`'s
   keyword-triggered test cases (bias/unsafe/pii keywords) plus a handful of clean control
   examples, and hand-label each as "should have been allowed" / "should have been blocked."
   This becomes `data/calibration_set.jsonl`.
2. Run your full checker pipeline (Specs 01/02 + existing bias/safety checkers) over the
   calibration set to get a `risk_score` for each example.
3. For each risk dimension, compute the **conformal quantile**:
   given target error rate α (e.g., α=0.10 meaning "at most 10% of truly-bad responses slip past
   the low threshold"), sort the calibration scores of the *known-bad* examples and take the
   `⌈(n+1)(1-α)⌉`-th smallest score as `τ_low`. Use a stricter α (e.g., 0.02) for `τ_high` (the
   HUMAN escalation boundary) since false negatives there are more costly.
4. **This is standard split-conformal calibration** — cite Angelopoulos & Bates, *A Gentle
   Introduction to Conformal Prediction*, arXiv:2107.07511, as the general-audience reference for
   the formula if judges ask for the math.
5. Store `τ_low`, `τ_high`, `α_low`, `α_high`, and the calibration-set size in
   `configs/use_case_policies.yaml` per use case — different use cases get different α (customer-
   facing chatbot: stricter/lower α; internal research tool: looser/higher α), which is your
   direct, quantified answer to the PS's "different risk tolerance... rarely works well
   everywhere" line.

```yaml
control_policy:
  customer_facing_chatbot:
    alpha_low: 0.05     # 5% tolerance for under-flagging at ALLOW boundary
    alpha_high: 0.01    # 1% tolerance for under-flagging at HUMAN boundary
    modify_span_threshold_pct: 25   # spans covering <25% of response -> MODIFY, else REGENERATE
  internal_knowledge_assistant:
    alpha_low: 0.15
    alpha_high: 0.05
    modify_span_threshold_pct: 40
```

## 5. Data contract

### Input
```
ControlDecisionInput:
    risk_profile: RiskProfile        # existing output of RiskEngine (unchanged)
    calibrated_thresholds: {dimension: {tau_low: float, tau_high: float}}  # loaded at startup from calibration run
    localized_spans: List[Span]      # from Spec 01/02 checkers, if any
    use_case_policy: UseCasePolicy
```

### Output (extends existing `ControlDecision` schema)
```
ControlDecision:
    action: "ALLOW" | "MODIFY" | "REGENERATE" | "HUMAN"
    triggering_dimension: str            # which risk dimension crossed the boundary
    calibration_metadata: {
        alpha_used: float,
        tau_used: float,
        calibration_set_size: int
    }
    target_spans: List[Span]             # populated only for MODIFY
    reasoning: str                       # human-readable audit trail, e.g. "PII risk 0.81 exceeded
                                          #  calibrated tau_high=0.78 (alpha=0.01, n=64 calibration
                                          #  examples) -> escalated to HUMAN"
```
The `calibration_metadata` and `reasoning` fields are what make your audit log (already required
by the PS: "clear audit trail behind every decision") *statistically defensible* instead of just
"policy said so." This is a strong, concrete answer to give when judges probe governance.

## 6. Step-by-step implementation plan

**Step 1 — Add a standalone calibration script** `scripts/calibrate_thresholds.py`
- Loads `data/calibration_set.jsonl`, runs the pipeline, computes `τ_low`/`τ_high` per dimension
  per use case using the split-conformal quantile formula in §4.
- Writes results into `configs/use_case_policies.yaml` under `control_policy.<use_case>`.
- Run this once before the demo, and re-run it live during the pitch on a few new examples to
  *show* judges the calibration mechanism working — this is a strong demo moment.

**Step 2 — Rewrite `src/policy/control_policy.py`**
- Load calibrated thresholds at startup (from YAML, not hard-coded).
- Implement the three-tier comparison in §3.
- Implement the MODIFY-vs-REGENERATE span-coverage rule in §3.
- Populate `reasoning` and `calibration_metadata` on every decision.

**Step 3 — Update `src/policy/schemas.py`**
- Add `MODIFY` and `HUMAN` to the `ControlDecision.action` enum (currently only
  `ALLOW`/`BLOCK`/`REDACT` per the roadmap doc).
- Add `calibration_metadata`, `target_spans`, `reasoning` fields.

**Step 4 — Update `src/audit/audit_logger.py`**
- Ensure the new fields are serialized to `data/audit_log.jsonl` — this becomes your
  "Metrics & monitoring" pitch artifact: you can compute realized false-positive/negative rates
  against the calibration guarantee after the demo and show they roughly match the target α.

**Step 5 — HUMAN action stub**
- Since full human-review UI is out of scope for this spec, implement `HUMAN` as: return a
  fallback "this response is under review" message to the end user, and append the full payload
  to `data/human_review_queue.jsonl`. This alone satisfies the Round 2 roadmap's gap #2
  (Human-in-the-Loop Escalation) at a prototype level without needing a full reviewer UI.

## 7. Definition of Done

- [ ] `control_policy.py` uses calibrated `τ_low`/`τ_high` loaded from YAML, not hard-coded
      constants.
- [ ] All four actions (ALLOW/MODIFY/REGENERATE/HUMAN) are implemented and reachable.
- [ ] `scripts/calibrate_thresholds.py` exists and can be re-run on new calibration data.
- [ ] `ControlDecision` includes `reasoning` and `calibration_metadata` in every audit log entry.
- [ ] `HUMAN` action writes to `data/human_review_queue.jsonl` and returns a fallback response.
- [ ] Pitch deck slide cites: Angelopoulos & Bates (arXiv:2107.07511) for the general method,
      Kumar et al. (arXiv:2305.18404) and Su et al. ("API is Enough") for the LLM-specific,
      logit-free application — with the explicit claim: "our thresholds carry a stated,
      calibrated error guarantee, not a guessed number."
