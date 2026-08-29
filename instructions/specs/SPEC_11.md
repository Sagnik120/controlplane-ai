# SPEC_11 — Use-Case-Differentiated Latency & Risk Budgets (Live Pipeline)

**Status:** Draft for implementation
**Owns:** `use_case_policies.yaml`, `src/checkers/base.py`, `src/engine/risk_engine.py`, `src/policy/control_policy.py`, `src/orchestrator/pipeline.py`
**Solves:** Upgrade #3 — "configs exist per use-case but checker cost is the same regardless; make customer-facing calls skip/lighten heavy checks vs. internal/batch."
**Builds directly on:** SPEC_10 (parallel dispatch + Tier-0/Tier-1 cascade per checker). SPEC_10 gave every checker a cheap/expensive split; this spec makes **where the cascade threshold sits** a function of *which use case is calling*, not a single global constant. Without this spec, SPEC_10's gates are uniform across all traffic and the PS requirement "different use cases... have very different risk tolerance and latency budgets" is still unmet at the point where cost is actually spent.

---

## 1. What's actually missing, precisely

Per the codebase doc: `use_case_policies.yaml` already defines `tau_low`/`tau_high` per use case for the **decision** layer (`control_policy.py` — whether a *given* risk score results in ALLOW/MODIFY/REGENERATE/HUMAN). That's real risk-tolerance differentiation, but it happens **after** the checkers have already all run at full cost. The gap is that nothing upstream of the decision varies *how much compute gets spent producing the risk score in the first place* — every use case pays for the same SelfCheckGPT depth, the same PII NER pass, the same bias-check frequency, then gets a different threshold applied to the result. That's differentiated risk *tolerance*, not differentiated risk *budget* — and the PS explicitly asks for both ("different risk tolerance **and latency budgets**").

---

## 2. Research synthesis

### 2.1 The core reframe: this is a compute-allocation problem, not a threshold problem
A recent line of work generalizes "adaptive test-time compute" from *pure difficulty* to **consequence/stakes**, which is exactly your customer-facing-vs-internal distinction:

- **"Not All Errors Are Equal: Consequence-Aware Reasoning Compute Allocation"** (2026) makes the argument directly: existing adaptive-compute methods route budget by *predicted difficulty* alone, which implicitly assumes all failures cost the same. They show difficulty and consequence are **approximately orthogonal** — a simple, easy-to-answer customer question can still carry high consequence (e.g., a wrong refund policy statement), while a hard internal query might carry low consequence (an engineer will fact-check it anyway). Their fix: a lightweight predictor estimates *how costly a wrong answer would be*, independent of how hard it is to get right, and routes higher-consequence tasks to bigger compute/verification budgets under a fixed total budget. Reported result: 22–33% reduction in cost-weighted loss versus difficulty-only routing at matched compute. **This is the paper that justifies budgeting by use-case/consequence tier rather than by per-response difficulty alone** — which is precisely what "customer-facing vs. internal" already gives you for free, since the use case *is* your consequence label; you don't even need their learned predictor, you already have the tier at request-admission time. [arXiv:2606.04402]
- **Uncertainty-Aware Budget Allocation (UAB)** (2026) is the general mechanism for *how* to actually reallocate a shared budget once you know relative importance: it treats budget allocation as a constrained optimization instead of uniform per-item allocation, and shows a fixed total budget reallocated by confidence beats uniform allocation with zero extra cost. Useful for framing the total "checker-compute budget per minute" your infra can afford, split unevenly across use-case tiers rather than granting each tier the same per-request allowance. [arXiv:2605.26849]
- **"Reasoning on a Budget"** survey (referenced within the consequence-aware paper) and **CODA (Compute Allocation by Difficulty Awareness)** formalize the general pattern as *utility maximization*: keep spending compute only while marginal risk-detection value exceeds its marginal cost — this is the formal justification for "customer-facing calls skip/lighten heavy checks": for a low-consequence, latency-sensitive tier, the marginal value of one more expensive NLI pass is lower than its latency cost, so the optimal policy is to spend less there by design, not as a corner cut. [arXiv:2603.08659]

### 2.2 Precedent for literally two different pipelines by request class
- **AdaServe** and the broader multi-SLO LLM serving literature (JITServe, SLOs-Serve, HyperFlexis, ProServe) all converge on the same systems pattern for *inference itself*: classify each incoming request into a small number of SLO/priority tiers at admission time, then give each tier a genuinely different execution path (different speculative-decoding depth, different token budget, different queue priority) rather than one path with a shared threshold. The direct transferable lesson for your `RiskEngine` is architectural: **tier assignment happens once, at the top of the pipeline, and everything downstream reads that tier** — not "each checker independently decides how hard to try." This avoids tier-drift, where PII checking ends up lenient but performance checking ends up strict for the same request just because they were tuned separately. [arXiv:2501.12162 (AdaServe); arXiv:2504.20068 (JITServe); arXiv:2508.15919 (HyperFlexis); arXiv:2512.12928 (ProServe)]
- **ProServe** specifically formalizes *why* uniform-threshold approaches under-serve high-priority traffic: it introduces a "Token-level Deadline-aware Gain" that quantifies how much service gain comes from meeting one tier's SLO versus another — the transferable idea for you is to stop thinking of use-case config as "which threshold to apply" and start thinking of it as "how much of my shared checker capacity does this tier deserve," which is a resource-allocation framing, not a rule-lookup framing. [arXiv:2512.12928]

### 2.3 Fusing this with your existing Conformal-Prediction framing (control_policy.py)
- **"Conformal Thinking: Risk Control for Reasoning on a Compute Budget"** (2026) is the single most directly-reusable paper here, because it does *exactly* what your `control_policy.py` docstring claims to do (conformal prediction) but explicitly ties it to a **compute budget constraint**, not just an error-rate constraint. Their setup: reasoning models decide how long to think based on confidence; they add a conformal risk-control layer on top that gives a statistical guarantee on accuracy while respecting a token budget. The mapping onto your system is almost one-to-one: replace "how long to think" with "how deep to check," and you get a principled way to say *"customer-facing gets a smaller compute budget, but conformal calibration guarantees its false-negative rate stays under X% anyway."* This is also the answer to Upgrade #12 in your list (soften/substantiate the conformal claim) — implementing this properly here gives you a legitimate conformal-prediction story to point to, rather than dressed-up YAML lookups. [arXiv:2602.03814]

---

## 3. Proposed architecture: Use-Case Tier → Checker Budget Profile

### 3.1 One tier assignment, read everywhere (per §2.2's AdaServe lesson)
```python
@dataclass
class UseCaseTier:
    name: str                          # "customer_facing_chat", "internal_copilot", "decision_support_batch"
    latency_budget_ms: int             # hard ceiling for the whole risk-evaluation pass
    consequence_level: str             # "low" | "medium" | "high" — per §2.1, independent of difficulty
    checker_budget: "CheckerBudgetProfile"
```
`pipeline.py` resolves the tier **once**, at request admission (already has the use-case ID from the incoming request/config), and passes the resolved `UseCaseTier` object down through `risk_engine.evaluate(window, context, tier)` so every checker reads the same tier object — avoiding the tier-drift risk called out in §2.2.

### 3.2 `CheckerBudgetProfile` — the actual lever this spec adds
This is what was missing per §1: today SPEC_10's Tier-0/Tier-1 gate uses one global `uncertain_threshold`. Make it a profile:
```yaml
# use_case_policies.yaml
customer_facing_chat:
  consequence_level: "medium"           # per Not-All-Errors-Equal: latency-sensitive but not lowest-consequence
  latency_budget_ms: 400
  checker_budget:
    performance:
      tier0_uncertain_band: [0.30, 0.70]   # wide "confident enough" zone -> most windows skip Tier-1
      selfcheck_num_samples: 2             # reduce from default 3 stochastic samples when Tier-1 does fire
      max_tier1_calls_per_response: 1      # hard cap regardless of how many windows are uncertain
    pii:
      tier0_mode: "pattern_only_unless_hit"   # regex first, NER only on a hit (SPEC_10 §2.2)
    bias:
      check_frequency: "every_4th_window"
    regenerate:
      max_attempts: 1                        # from SPEC_09, tie the budget through to REGENERATE too

internal_decision_support:
  consequence_level: "high"
  latency_budget_ms: 3000
  checker_budget:
    performance:
      tier0_uncertain_band: [0.15, 0.85]      # narrow "confident enough" zone -> most windows DO get Tier-1
      selfcheck_num_samples: 5                # increase beyond default for higher scrutiny
      max_tier1_calls_per_response: null      # no cap
    pii:
      tier0_mode: "always_full_ner"
    bias:
      check_frequency: "every_window"
    regenerate:
      max_attempts: 2

internal_batch_pipeline:
  consequence_level: "high"
  latency_budget_ms: null                     # no per-response ceiling — batch is not user-facing latency
  checker_budget:
    performance:
      tier0_uncertain_band: [0.05, 0.95]       # nearly always escalate to Tier-1
      selfcheck_num_samples: 5
      allow_best_of_n_regenerate: true         # from SPEC_09 §1.5 — batch can afford multi-sample regen
      best_of_n: 3
```
This is the concrete answer to "make customer-facing calls skip/lighten heavy checks vs internal/batch" — the *same* Tier-0 gate mechanism from SPEC_10 now has different operating points per tier, and the number of stochastic samples SelfCheckGPT itself draws (a direct cost lever, not just a gate) also varies.

### 3.3 Latency budget as a circuit breaker, not just a target
Per JITServe's "imprecise request information, refine as generation progresses" idea, treat `latency_budget_ms` as a live circuit breaker inside `risk_engine.evaluate()`, not just a planning number:
```python
async def evaluate(self, window_text, context, tier: UseCaseTier):
    deadline = time.monotonic() + (tier.latency_budget_ms / 1000 if tier.latency_budget_ms else float("inf"))
    ...
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*futures), timeout=remaining_time(deadline))
    except asyncio.TimeoutError:
        # degrade gracefully: use whichever Tier-0-only results completed,
        # mark missing dimensions as "unknown, not skipped-silently" (reuses SPEC_10 §3.4's
        # exception-handling contract so a timeout is treated the same as a checker crash)
        results = self._partial_results_with_timeout_markers(futures)
```
For `customer_facing_chat`, if Tier-1 SelfCheckGPT would blow the 400ms budget, the circuit breaker returns the Tier-0-only signal and routes to Control Policy with an explicit "under-verified" flag rather than either (a) silently blocking until done (defeats the latency purpose) or (b) silently treating it as ALLOW (defeats the safety purpose). Control Policy should treat "under-verified + medium/high consequence" as a nudge toward HUMAN or a lighter MODIFY rather than a full pass — this is the live version of §2.3's conformal-with-compute-budget guarantee: you're explicitly trading verification depth for latency, and saying so in the audit trail, rather than trading it away silently.

### 3.4 Where consequence and difficulty diverge (the §2.1 finding, applied)
Don't assume "customer-facing = always lighter." Per the consequence-aware paper's finding that difficulty and consequence are roughly orthogonal, a customer-facing use case can still have specific **high-consequence sub-flows** (e.g., a customer-facing chatbot that can also process a refund or read back an account balance) that deserve the internal tier's scrutiny even though the overall use case is "customer-facing/low-latency." Support a per-request override:
```python
if request_context.get("action_type") in HIGH_CONSEQUENCE_ACTIONS:  # e.g. "refund", "account_change"
    effective_tier = escalate_tier(base_tier)  # borrow internal_decision_support's checker_budget
```
This also directly sets up Upgrade #6 (agent/tool-call risk) — the same `action_type` field that triggers a tier escalation here is the natural hook for "flagged response would trigger a downstream action."

---

## 4. Step-by-step implementation guide

1. **Extend `use_case_policies.yaml` schema** (§3.2) — add `checker_budget` block alongside the existing `tau_low`/`tau_high`. Validate with a Pydantic schema in `src/policy/schemas.py` so a malformed YAML fails fast at startup, not mid-request.
2. **Thread `UseCaseTier` through the call chain**: `pipeline.py` resolves tier once from the incoming request's use-case ID → passes to `risk_engine.evaluate(..., tier)` → `risk_engine` passes the relevant `checker_budget.<checker_name>` sub-config into each `checker.run(window, context, budget)` call (extends the `BaseChecker` interface from SPEC_10 §3.1 with a `budget` parameter).
3. **Update `PerformanceChecker.tier0_gate`** to read `budget.tier0_uncertain_band` instead of a hardcoded constant; update `tier1_check` to read `budget.selfcheck_num_samples` and pass it into the SelfCheckGPT sampling call; enforce `budget.max_tier1_calls_per_response` as a per-request counter.
4. **Update `PIIChecker.tier0_gate`** to branch on `budget.tier0_mode` (`pattern_only_unless_hit` vs `always_full_ner`).
5. **Update bias/safety checker** to read `budget.check_frequency` and maintain a per-turn window counter to decide whether this window's bias pass actually runs (ties to your original ControlPlane.ai doc's "bias can be evaluated less frequently" note).
6. **Add the circuit breaker** (§3.3) to `risk_engine.evaluate` using `asyncio.wait_for`; add the "under-verified" flag to `FinalRiskReport`.
7. **Update `control_policy.py`** to treat `under_verified=True` as a factor that shifts the decision toward HUMAN/MODIFY rather than ALLOW, scaled by `consequence_level` — this is where the conformal-budget idea from §2.3 actually gets enforced.
8. **Thread `max_regenerate_attempts` / `allow_best_of_n_regenerate` from `checker_budget.regenerate`** into `RegenerationEngine` (SPEC_09 §3.5 already anticipated this field name — this spec is what actually wires it per-tier live instead of as a flat config).
9. **Add the `action_type` escalation hook** (§3.4) at the point `pipeline.py` first parses the incoming request, before tier resolution.

---

## 5. Metrics to prove this works (extends SPEC_10 §4 and feeds Upgrade #8's dashboard)
- **Mean/p95 risk-evaluation latency, broken out by use-case tier** — should now visibly diverge (customer-facing tight, internal/batch loose), where SPEC_10 alone would show all tiers converging to the same number.
- **Tier-1 invocation rate, broken out by use-case tier** — the direct evidence that "skip/lighten heavy checks" is actually happening, not just configured.
- **Under-verified rate per tier** — how often the circuit breaker fires; a non-zero-but-low rate for customer-facing is expected and healthy, a high rate means the latency budget is set unrealistically tight for the checker cost.
- **Cost-weighted miss rate by consequence tier** — directly reusable framing from the consequence-aware paper (§2.1): are you spending disproportionately more compute catching low-consequence errors than high-consequence ones? If so, the budget split is wrong even if latency numbers look good.

---

## 6. Testing checklist
- Unit test: same risk score, different tiers → different Tier-0/Tier-1 routing (proves the band actually varies, not just decision thresholds downstream).
- Unit test: circuit breaker fires correctly at `latency_budget_ms` and produces `under_verified=True` with partial results, not an exception.
- Unit test: `action_type` escalation correctly upgrades a customer-facing request's effective budget for a flagged high-consequence action.
- Integration test: simulate identical flawed text through `customer_facing_chat` and `internal_decision_support` tiers; assert internal tier catches it (Tier-1 fires) while customer-facing tier's Tier-0-only pass may miss it — then assert Control Policy still escalates the customer-facing miss to HUMAN once `under_verified` is factored in, demonstrating the safety net promised in §3.3.
- Load test: confirm `max_tier1_calls_per_response` actually bounds worst-case latency for customer-facing traffic under adversarial input designed to keep triggering Tier-0 uncertainty.

---

## 7. Reference list

- Wen, He, He, "Not All Errors Are Equal: Consequence-Aware Reasoning Compute Allocation," 2026 — arXiv:2606.04402
- Nguyen, Gupta, Le, "Uncertainty-Aware Budget Allocation for Adaptive Test-Time Reasoning," Deakin University, 2026 — arXiv:2605.26849
- Wu, Xie, Zhang, Xiao, "CODA: Difficulty-Aware Compute Allocation for Adaptive Reasoning," Fudan University — arXiv:2603.08659
- "Conformal Thinking: Risk Control for Reasoning on a Compute Budget," 2026 — arXiv:2602.03814
- "AdaServe: Accelerating Multi-SLO LLM Serving with SLO-Customized Speculative Decoding" — arXiv:2501.12162
- "JITServe: SLO-aware LLM Serving with Imprecise Request Information" — arXiv:2504.20068
- "HyperFlexis: Joint Design of Algorithms and Systems for Multi-SLO Serving and Fast Scaling" — arXiv:2508.15919
- "ProServe: Unified Multi-Priority Request Scheduling for LLM Serving" — arXiv:2512.12928
