# SPEC_13 — Live HUMAN Feedback Loop via Adaptive Conformal Inference

**Status:** Draft for implementation
**Owns:** `src/feedback/feedback_store.py`, `scripts/recalibrate.py`, new `src/policy/adaptive_calibration.py`, `src/policy/control_policy.py`, `use_case_policies.yaml`
**Solves:** Upgrade #5 — "connect `human_review_queue.jsonl` → `recalibrate.py` into the actual running pipeline, not just an offline script, so you can demo 'system learns from a human override.'"
**Bonus, unprompted but directly relevant:** this spec is also the single best fix for Upgrade #12 on your own list ("clean up conformal prediction claim... either actually compute non-conformity scores... or soften the pitch"). Right now your `control_policy.py` docstring claims Conformal Prediction but the codebase doc admits it's "mostly rule-based dict lookups" with calibration "simulated via YAML configs." This spec makes the conformal claim literally true by wiring the one piece of real conformal-prediction math your system was missing: an **online** update rule, driven by exactly the human-verdict signal you already collect.

---

## 1. What's actually broken, precisely

Per the codebase doc: `feedback_store.py` scrapes `human_review_queue.jsonl` for entries with a `human_verdict`, dedupes, and appends to `calibration_set.jsonl` — but this is "called by `scripts/recalibrate.py` (not the main pipeline)." So today the loop is:
```
human overrides a decision → written to JSONL → sits there → someone manually
runs `recalibrate.py` at some later point → thresholds in `use_case_policies.yaml`
get hand-edited or regenerated → pipeline restarts to pick up new config
```
Every step after "written to JSONL" is offline, manual, and requires a restart. There is no live path from "a human told the system it was wrong" to "the system's behavior changes on the next request." That's the entire gap this spec closes.

---

## 2. Research synthesis

### 2.1 The core mechanism: Adaptive Conformal Inference (ACI) — Gibbs & Candès
This is the single most directly-applicable piece of research for this exact upgrade. Gibbs & Candès (2021) developed **Adaptive Conformal Inference**, which solves precisely your situation: you have a conformal-style threshold (a miscoverage/error-rate target), and you're operating in a live, non-stationary stream where you can't assume past data is representative of the future. Their update rule is a single online gradient step, applied after each new observed outcome:
$$\alpha_{t+1} = \alpha_t + \gamma \left(\alpha - \mathbb{1}[Y_t \notin \hat{C}_t(\alpha_t)]\right)$$
In words: after each new labeled outcome, nudge the working miscoverage level up or down by a step size `γ`, depending on whether the most recent decision turned out to be wrong. This provably converges the *long-run* error rate to your target `α`, **even under arbitrary distribution shift** — no assumption that the data is i.i.d. or stationary, which is exactly your situation (real user traffic drifts over time). [Gibbs & Candès, "Adaptive Conformal Inference Under Distribution Shift," 2021 — arXiv:2106.00170; extended in "Conformal Inference for Online Prediction with Arbitrary Distribution Shifts," JMLR 2024 — arXiv:2208.08401]

**The direct mapping onto your system:**
- $Y_t \notin \hat{C}_t(\alpha_t)$ — "the decision was wrong" — is exactly what a **human override** tells you. If a human reviews a HUMAN-escalated case and says "this should have been ALLOWed," that's one miscoverage observation. If a human confirms "yes, this was correctly flagged," that's a coverage-success observation.
- $\alpha_t$ is exactly your `tau_low`/`tau_high` calibration target per use case — the thing `control_policy.py` currently reads as a static YAML constant.
- The update is **O(1) per feedback event** — no retraining, no batch job, no model — just adjusting one number based on one new labeled outcome. This is what makes it feasible to wire live instead of as an offline script.

### 2.2 Why a single fixed step size isn't quite enough, and the practical fix
The original ACI paper flags its own limitation honestly: optimal performance requires the step size `γ` to match the true (unknown) rate of distribution shift — too large and the threshold jitters on every noisy override, too small and it reacts too slowly to a real shift. Gibbs & Candès' 2024 follow-up ("Conformal Inference for Online Prediction with Arbitrary Distribution Shifts") fixes this by running **multiple experts in parallel, each with a different step size, and aggregating** — adaptive to the shift's size and type without needing to know it in advance. [arXiv:2208.08401]

For a hackathon-scope implementation, running a small ensemble (e.g., 3 step sizes: conservative, moderate, aggressive) and aggregating by a simple weighted vote is a reasonable middle ground between the fragile single-step-size version and the full JMLR paper's machinery — cite this as the "next step" if you don't have time to implement the full multi-expert aggregation, and note explicitly in the demo that you're using a simplified single-γ version for v1 (this kind of honest scoping is exactly what makes a technical judge trust the rest of your claims more, not less).

### 2.3 Modeling review delay and congestion (why the loop can't be naive)
Human feedback doesn't arrive instantly — there's a queue, and queue depth varies. **"Learning to Defer in Content Moderation"** (Lykouris & Weng, MIT) formalizes exactly your HUMAN-tier decision as an *admission decision* to a review queue, and explicitly models the fact that **feedback delay is endogenous** — it depends on how many cases you're admitting and how fast humans can clear them, not a fixed external delay. Two lessons transfer directly:
1. Don't update `alpha_t` synchronously inside the request path that triggered the HUMAN escalation — the human verdict arrives later, asynchronously, so the ACI update must happen as a **separate consumer process** reacting to verdicts as they land, decoupled from the request that generated the escalation.
2. If your review queue is backing up, that's itself a signal — the paper's framework suggests the *admission* threshold (how readily you escalate to HUMAN in the first place) should be sensitive to review capacity, not just to risk score. This directly serves the PS's alert-fatigue concern: a system that keeps escalating to HUMAN while the queue is already backed up is making the fatigue problem worse, not better. [arXiv:2402.12237]

### 2.4 Real precedent that this is not a theoretical-only idea
A patented content-moderation system (voice-chat moderation, cited generally as production precedent) implements a simpler but directly analogous live loop: an automated-action threshold starts conservative, human moderators review borderline-scored content, and **as accumulated moderator feedback confirms the system is reliable at a given score band, the automation threshold is progressively lowered to admit more automated (non-human) decisions at that band** — a live, observable "system learns from moderator feedback" behavior, described in exactly the terms your upgrade item asks to demo. This is useful less as an algorithm to copy (it's coarser than ACI) and more as evidence that "live threshold movement from human feedback" is an established, demoable production pattern, not a research toy. [content-moderation threshold-adjustment patent — image-ppubs.uspto.gov/dirsearch-public 12341619]

### 2.5 Vocabulary/schema reuse for structured feedback ingestion
Microsoft's **NPO** framework (2025) for continual alignment monitoring uses a clean three-way taxonomy for structured feedback ingestion: **likes** (explicit confirmation), **overrides** (explicit correction), and **abstentions** (human declined to judge / insufficient info). Adopting this exact taxonomy for `human_verdict` values in `human_review_queue.jsonl` (rather than an ad hoc string) gives you a principled schema: overrides are miscoverage events (feed into ACI negatively), likes are coverage-confirmation events (feed into ACI positively), and abstentions are excluded from the ACI update entirely rather than being silently miscounted either way. [arXiv:2507.21131]

---

## 3. Proposed architecture: Live ACI Feedback Loop

```
   Pipeline escalates a case to HUMAN
                 │
                 ▼
   human_review_queue.jsonl  (unchanged — still the audit-trail write)
                 │
                 │  (async, decoupled from request path — per §2.3)
                 ▼
   FeedbackConsumer  (new: watches for new human_verdict entries,
                       NOT invoked by a manual script anymore)
                 │
        classify verdict per §2.5 taxonomy: like | override | abstain
                 │
                 ▼
   AdaptiveCalibrator.update(use_case, risk_dimension, verdict)
        — applies the ACI gradient step from §2.1, per use case AND
          per risk dimension (performance/PII/bias each get their own
          alpha_t, since they have different acceptable miscoverage —
          ties directly to SPEC_11's per-tier risk tolerance)
                 │
                 ▼
   in-memory alpha_t store (Redis-backed once Upgrade #11 lands;
   in-process dict + periodic snapshot to SQLite for v1 — same
   ephemeral-storage caveat the codebase doc already flags elsewhere)
                 │
                 ▼
   control_policy.py reads CURRENT alpha_t live on every request
   — no restart needed, no manual recalibrate.py run needed
                 │
                 ▼
   scripts/recalibrate.py  — REPURPOSED, not deleted: runs periodically
   (e.g. nightly) as a reconciliation/sanity job — recomputes alpha_t
   from the full calibration_set.jsonl from scratch and checks it hasn't
   drifted far from the live online estimate; alerts if it has (this is
   your safety net against the online process silently going wrong)
```

### 3.1 `AdaptiveCalibrator` — the new component
```python
class AdaptiveCalibrator:
    def __init__(self, initial_alphas: dict, step_size: float = 0.05,
                 min_alpha: float = 0.01, max_alpha: float = 0.5):
        # initial_alphas seeded from today's use_case_policies.yaml tau values —
        # YAML becomes the PRIOR, not the fixed value (important framing for judges:
        # "we didn't throw away the calibrated config, we made it the starting point
        # of a live-updating estimator")
        self.alphas = initial_alphas.copy()
        self.gamma = step_size
        self.min_alpha, self.max_alpha = min_alpha, max_alpha   # safety rails, §3.3

    def update(self, use_case: str, risk_dimension: str, was_miscovered: bool):
        key = (use_case, risk_dimension)
        alpha = self.alphas[key]
        target = self.alphas_target[key]   # the original design target, e.g. 0.05
        alpha_new = alpha + self.gamma * (target - int(was_miscovered))
        self.alphas[key] = clip(alpha_new, self.min_alpha, self.max_alpha)  # §3.3
        self._log_audit(key, alpha, alpha_new, was_miscovered)  # for dashboard, §5
```

### 3.2 Decoupled async consumer, not a synchronous call in the request path
Per §2.3's delay/congestion lesson, the consumer that applies `AdaptiveCalibrator.update()` runs as an independent asyncio task (or a lightweight background worker) that polls/subscribes to new entries in `human_review_queue.jsonl` (or, better, an internal in-process event emitted by whatever admin/reviewer endpoint records a verdict — avoid filesystem polling if you already have a direct code path, and keep the JSONL purely as the audit trail per SPEC's general logging discipline). This guarantees a human reviewer being slow, or a burst of reviews arriving at once, never blocks or slows down live user-facing requests — the live pipeline only ever *reads* the current `alpha_t`, it never waits on feedback processing.

### 3.3 Safety rails — bounding how far live feedback can move a threshold
Because this is a live, external-input-driven update (a human's judgment, potentially inconsistent or even adversarial if review-queue access isn't tightly controlled), unbounded ACI updates are a real risk: a small number of aggressive overrides could swing a threshold further than intended before anyone notices. Three concrete guards, directly motivated by §2.2's step-size fragility discussion:
- **Hard floor/ceiling** on `alpha_t` (`min_alpha`/`max_alpha`) so no sequence of overrides can push a threshold to an unsafe extreme (e.g., PII miscoverage tolerance should never drift above some hard ceiling regardless of feedback).
- **Rate limiting** on how much `alpha_t` can move per unit time (e.g., cap cumulative drift per hour), which is the practical analogue of choosing a conservative `γ` from §2.2's ensemble idea without needing the full multi-expert machinery for v1.
- **`recalibrate.py` as an offline auditor** (per the architecture diagram) — periodically recomputes calibration from scratch and flags if the live online estimate has drifted implausibly far from the ground-truth batch estimate, giving you a way to *detect* if the live loop has gone wrong even in a simplified v1 implementation.

### 3.4 Congestion-aware HUMAN admission — **DEFERRED, not v1**
Per §2.3's second lesson, `control_policy.py`'s HUMAN-routing decision could in principle also react to a live queue-depth signal — if `human_review_queue`'s unresolved backlog exceeds a configured threshold, temporarily raise the bar for HUMAN escalation rather than continuing to pile into an already-backed-up queue.

**Decision: explicitly out of scope for this spec / v1.** Reasons, for the record:
1. It changes what a HUMAN decision means under load, in a way that's hard to justify live to a judge in a few seconds ("a risky response got less scrutiny because other requests were also queued" is a defensible engineering tradeoff in writing, but sounds like lowering the safety bar under pressure when said out loud).
2. It couples a *scheduling* concern (queue admission) with the *calibration* concern this spec is actually about (ACI), which muddies the causal story of the core demo moment in §5 — a judge should be able to attribute a threshold change to the exact override just made, not wonder whether background queue state also moved it.
3. A hackathon demo won't have enough concurrent traffic to make a congestion signal meaningfully fire anyway, so the implementation cost buys little demo value right now.
4. It's a clean additive extension later — nothing in `AdaptiveCalibrator` (§3.1–§3.3) depends on whether this exists, so it can be built post-hackathon without any rework of the ACI plumbing.

If a judge asks about alert fatigue under sustained load specifically, this section is the citable answer ("we scoped it, deferred it for demo-clarity reasons, here's the design") — Lykouris & Weng (§2.3) remains the reference to point to.

---

## 4. Step-by-step implementation guide

1. **Extend `human_review_queue.jsonl` schema** to record `human_verdict` using the §2.5 taxonomy (`"like"` / `"override"` / `"abstain"`) plus which `use_case` and `risk_dimension` the original decision concerned — needed for the per-dimension `alpha_t` keying in §3.1.
2. **Build `src/policy/adaptive_calibration.py`** implementing `AdaptiveCalibrator` (§3.1), seeded from current `use_case_policies.yaml` `tau_low`/`tau_high` as the initial/target values.
3. **Build the async `FeedbackConsumer`** (§3.2) — simplest viable version for a hackathon timeline is a lightweight polling loop on `human_review_queue.jsonl` (watch file mtime / new-line count) running as a background `asyncio` task started alongside the main app; note in the roadmap doc that a real deployment would replace this with a proper event queue (ties into your existing Postgres/Redis upgrade plan, not new scope for this spec).
4. **Wire `control_policy.py`** to read `alpha_t` from a shared `AdaptiveCalibrator` instance (dependency-injected, same discipline as SPEC_10/12's shared-embedder pattern) instead of the static YAML value directly — YAML values become `initial_alphas`/`alphas_target`, read once at startup.
5. **Repurpose `scripts/recalibrate.py`** into the periodic reconciliation auditor described in §3.3, rather than the primary update mechanism — update its docstring/README description to reflect the new role, since a judge reading your code should see the story is coherent, not two competing update paths.
6. **Add audit logging** (`AdaptiveCalibrator._log_audit`) writing before/after `alpha_t` values with timestamps to whatever store Upgrade #10 (SQLite/Postgres) establishes — this is the literal data your demo will show moving live.
7. **Do not implement §3.4** (queue-depth-aware HUMAN admission) for this pass — deferred by design, see §3.4 for the reasoning. Steps 1–6 are the complete v1 scope.

---

## 5. The demo moment this unlocks
This is the concrete answer to "so you can demo 'system learns from a human override'":
1. Send a request that gets flagged and routed to HUMAN.
2. Have a human reviewer mark it as an `"override"` (i.e., "this was actually fine, shouldn't have been escalated").
3. Show the audit log entry: `alpha_t` for that `(use_case, risk_dimension)` moved from its prior value to a new value, with the exact ACI equation from §2.1 annotated next to it.
4. Send a **second, similar** request in the same demo session and show it now passes through at a tier that would have escalated it before the override — live behavior change, no restart, no manual script run, attributable to one specific human decision you just made on stage.

This is a stronger demo than "we have a recalibration script" because it's synchronous with the conversation, visibly tied to the exact override just performed, and backed by a named, citable algorithm rather than "we update some numbers."

---

## 6. Metrics to add to the dashboard (Upgrade #8)
- **Live `alpha_t` trajectory per use case / risk dimension** — a time-series chart is the single most compelling artifact this spec produces for a judge.
- **Override vs. like ratio** — a rough proxy for how well-calibrated the system already is (high override rate = system frequently disagreeing with humans = threshold has room to move).
- **Online-vs-batch drift** — the gap `recalibrate.py`'s periodic full recompute finds versus the live estimate, per §3.3's auditor role — demonstrates the safety net is actually functioning, not just present in the architecture diagram.
- **Human review queue depth over time** — worth tracking and displaying even without §3.4's routing logic wired to it; it's useful operational visibility on its own, and sets up §3.4 as a clean future addition if the deferred decision is revisited.

---

## 7. Testing checklist
- Unit test: `AdaptiveCalibrator.update` matches the ACI equation exactly for a hand-computed sequence of miscoverage/coverage events (regression-test the math itself, not just that it runs).
- Unit test: floor/ceiling clipping (§3.3) actually bounds `alpha_t` under an adversarial sequence of all-override feedback.
- Unit test: `"abstain"` verdicts are excluded from the update (don't silently count as either coverage or miscoverage).
- Integration test: an override written to `human_review_queue.jsonl` is picked up by `FeedbackConsumer` and reflected in `control_policy.py`'s live read within a bounded time window, without a process restart.
- Integration test: `recalibrate.py`'s batch recomputation and the live `alpha_t` converge to within a small tolerance over a simulated feedback stream, validating §3.3's auditor role actually catches drift when deliberately introduced in a test.

---

## 8. Reference list

- Gibbs & Candès, "Adaptive Conformal Inference Under Distribution Shift," 2021 — arXiv:2106.00170
- Gibbs & Candès, "Conformal Inference for Online Prediction with Arbitrary Distribution Shifts," JMLR 2024 — arXiv:2208.08401
- Lykouris & Weng, "Learning to Defer in Content Moderation: The Human-AI Interplay," MIT — arXiv:2402.12237
- Gaikwad & Doke, "NPO: Learning Alignment and Meta-Alignment through Structured Human Feedback," Microsoft, 2025 — arXiv:2507.21131
- Content-moderation live-threshold-adjustment system (voice chat moderation, moderator-feedback-driven automation threshold) — image-ppubs.uspto.gov/dirsearch-public 12341619