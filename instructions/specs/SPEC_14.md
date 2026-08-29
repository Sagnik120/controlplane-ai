# SPEC_14 — Agent / Tool-Call Risk Gating (Simulated Action Example)

**Status:** Draft for implementation
**Owns:** new `src/agent/action_gate.py`, `src/agent/action_catalog.yaml`, `src/orchestrator/pipeline.py`, `src/policy/control_policy.py`
**Solves:** Upgrade #6 — "add even one simulated example where a flagged response would trigger a downstream action, since the PS explicitly calls out AI agents that take actions, not just chat."
**Why this is a real gap, not a nice-to-have:** every other spec so far (09–13) evaluates and repairs **text**. Nothing in the current pipeline asks "is this response about to *do* something in the world." A recent framework paper makes the exact distinction the PS is drawing: historically LLM safety meant stopping a model from *describing* a harmful act, but agentic systems change the failure mode from "the model said something wrong" to "the model **did** something wrong" — and a wrong action can be irreversible in a way a wrong sentence never is. [ASTRA, arXiv:2511.18114] Your pipeline currently has no concept of this distinction at all.

---

## 1. What "modeling this" actually requires, precisely

You don't need a real email-sending or database-writing integration for the hackathon — the upgrade item says *simulated*. What you do need, to genuinely close this gap rather than paper over it, is:
1. A concept of an **action** as a distinct thing the pipeline can reason about (name, arguments, reversibility, blast radius) — not just more text.
2. A way to connect a flagged risk (from your existing `FinalRiskReport`) to whether that risk **feeds into an action's arguments** — this is the part that makes it a real gate, not a decoration. A hallucination in prose that nobody acts on and a hallucination that becomes the amount in a `update_record` call are not the same severity, even if the underlying text-level risk score is identical.
3. A decision layer for actions that can differ from the decision for the surrounding text — e.g., the text response can be ALLOWed to the user ("I'll process that refund") while the *action itself* is HELD pending confirmation.

---

## 2. Research synthesis

### 2.1 The core architectural precedent: FinHarness — reuse your existing cascade, don't reinvent
**FinHarness** (2026) is the closest published system to what you should build, and it's built from parts you already have. It wraps an agent with three components: a **Query Monitor** (single-turn intent + cross-turn drift — you already have this as `SessionRiskState`'s drift tracking), a **Tool Monitor** that evaluates *each prospective tool call before it executes*, and a **Cascade** module that adaptively routes verification between a lightweight and an advanced-tier judge, only escalating to the expensive check when the cheap one is uncertain. Reported result: cuts attack success rate from 38.3% to 15.0% on their benchmark while barely touching benign-approval rate, using 4.7× fewer expensive-judge calls than checking everything with the advanced judge. [arXiv:2605.27333]

**The direct implication for you:** this is literally your SPEC_10 Tier-0/Tier-1 cascade, applied to one new checker type (a **Tool Monitor**) instead of a fourth text checker. You are not building new infrastructure — you're instantiating the same pattern you already have, on a new input type (a proposed tool call instead of a generated text window).

### 2.2 What the Tool Monitor should actually check — a three-requirement framework already exists
**InjecAgent** (2024) and the related **ToolEmu/"Selectively Quitting"** line of agent-safety benchmarks (arXiv:2403.02691, arXiv:2510.16492, arXiv:2508.13465) converge on the same three requirements for safe tool use, phrased almost identically across papers:
1. **Risk Awareness** — the agent (or, in your case, the gate wrapping it) must recognize when a tool call could compromise privacy/security or cause negative real-world effects.
2. **Avoid Risky Tool Call** — refrain from *directly executing* a risky call.
3. **Risk-Informed Confirmation** — if execution is withheld, the response to the user/operator must clearly explain *why*, so a human can make an informed decision, not just see a generic "blocked."
This is a ready-made rubric for both your gate's logic and its audit-log message — reuse it directly rather than inventing your own risk taxonomy for actions.

### 2.3 Catching the risk *before* the action fires, not after
**InferAct** (2024) is the right conceptual model for *timing*: it evaluates an agent's reasoning trajectory **preemptively**, before a risky or irreversible action executes, using Theory-of-Mind-style belief reasoning to ask "would a human, seeing what I'm about to do, want to intervene?" — and only then alerts for human confirmation. Their own framing example is directly analogous to yours: an incorrect `buy-now` action in an online-shopping agent is exactly the same *shape* of problem as an incorrect `update_record`/`send_email` action in an enterprise support agent — a single bad step with consequences that can't be undone by a later, better response. [arXiv:2407.11843]

The practical lesson: **the gate must sit between "decision made" and "action executed,"** not run as a post-hoc audit after the action already fired. Your existing pipeline already has the right shape for this (Control Policy decides, *then* whatever happens next happens) — this spec just adds a new node in that sequence specifically for actions.

### 2.4 Reversibility and blast radius as the key severity dimensions
Across this literature (FinHarness's framing of "irreversible mid-trajectory tool calls" as the thing boundary filters miss; InferAct's framing around irreversible actions specifically; ASTRA's system-prompt-level guardrail examples like "never extend the robotic arm more than 2 meters" as a blast-radius constraint) the two dimensions that actually matter for deciding how hard to gate an action are:
- **Reversibility**: can a human undo this after the fact with reasonable effort? (a draft email sitting unsent vs. an email that already left the outbox; a record with a pending-approval status vs. a record already committed)
- **Blast radius**: how many people/systems does one action affect? (one customer's record vs. a bulk update; one recipient vs. a mailing list)

This gives you a compact, defensible way to classify actions without needing a large taxonomy — a 2×2 (reversible/irreversible × low/high blast radius) is enough to drive real gating decisions and is easy to explain to a judge in one sentence.

### 2.5 Consequence framing reuses SPEC_11 directly — this is not new machinery
SPEC_11 (§3.4) already introduced a `HIGH_CONSEQUENCE_ACTIONS` escalation hook and explicitly flagged it as "the natural hook for Upgrade #6." This spec is that hook, made concrete. The "Not All Errors Are Equal" consequence-aware framing from SPEC_11 §2.1 applies directly here too: an action-triggering flow should be treated as high-consequence **regardless of which use-case tier the request otherwise belongs to** — a customer-facing chatbot that can also issue a refund should get the internal/high-scrutiny checker budget *for that specific turn*, exactly as SPEC_11 designed for.

---

## 3. Proposed architecture

### 3.1 Action representation and catalog
```yaml
# src/agent/action_catalog.yaml
send_email:
  reversibility: "irreversible"     # once sent, sent
  blast_radius: "variable"          # depends on recipient count — computed at call time
  requires_confirmation_by_default: true

update_record:
  reversibility: "reversible_with_audit"   # can be corrected, but leaves a trail / real-world effect meanwhile
  blast_radius: "single_entity"
  requires_confirmation_by_default: true

update_record_bulk:
  reversibility: "reversible_with_audit"
  blast_radius: "many_entities"
  requires_confirmation_by_default: true   # always, regardless of content risk score — blast radius alone justifies it

read_record:
  reversibility: "reversible"
  blast_radius: "single_entity"
  requires_confirmation_by_default: false   # read-only, no gate needed unless PII risk is independently high
```
This catalog is deliberately small and hand-authored (per §2.4's 2×2 framing) — it does not need to be exhaustive or ML-driven for a hackathon demo; it needs to be *legible*, so a judge can see exactly why an action was gated.

### 3.2 `ActionRiskChecker` — the Tool Monitor (per §2.1's FinHarness mapping)
```python
class ActionRiskChecker(BaseChecker):   # same interface as SPEC_10's checkers — reuses the cascade
    def tier0_gate(self, proposed_action: ProposedAction, context) -> Tier0Result:
        catalog_entry = self.action_catalog[proposed_action.name]
        if catalog_entry.blast_radius in ("many_entities",) or catalog_entry.reversibility == "irreversible":
            return Tier0Result(needs_tier1=True, risk=1.0)   # always escalate, cheap rule, no model call needed
        # cheap check: does this action's arguments overlap (per SPEC_12's semantic overlap
        # detector, reused directly) with any span already flagged by performance/PII/bias?
        overlap = self.overlap_detector.check_action_args_against_flags(
            proposed_action.arguments, context.flagged_spans)
        return Tier0Result(needs_tier1=overlap.found, risk=overlap.max_risk if overlap.found else 0.0)

    def tier1_check(self, proposed_action, context) -> Tier1Result:
        # only reached for genuinely ambiguous/high-consequence cases (per FinHarness's
        # cascade — most actions resolve at tier0 via the catalog + overlap check alone)
        return self._llm_judge_action(proposed_action, context)  # per §3.4's confirmation-response pattern
```
Note this is not a new architecture — it's `BaseChecker` (SPEC_10) with the overlap detector (SPEC_12) as its cheap gate. This is the concrete payoff of having built those two specs first: this checker is mostly composition, not new logic.

### 3.3 Where this sits in `pipeline.py`
```
Generate response → Risk Engine (parallel checkers, SPEC_10) → Control Policy decision (ALLOW/MODIFY/REGENERATE/HUMAN)
                                                                              │
                                            if the response includes a proposed tool call:
                                                                              ▼
                                                        ActionRiskChecker.run(proposed_action, context)
                                                                              │
                                       ┌──────────────────────────┬──────────┴───────────┐
                                       ▼                          ▼                       ▼
                                 EXECUTE                    HOLD (confirmation)      BLOCK entirely
                          (action risk low,             (per InjecAgent's           (action risk severe —
                           text-level decision            Requirement 3, §2.2 —      e.g. bulk update with
                           was ALLOW/MODIFY)               user-facing message         high overlap risk)
                                                            explains why, per §2.2)
```
Critically: the **text-level decision and the action-level decision are independent outputs**, per §2.3's "sits between decision and execution" lesson. A MODIFY-repaired response can still be shown to the user while its associated action is HELD — this is a stronger, more honest behavior than either always coupling them (over-blocks safe text) or never separating them (under-protects the action).

### 3.4 The Risk-Informed Confirmation message (per §2.2's Requirement 3)
When an action is HELD, the message shown to the operator/reviewer must state, plainly: which flagged content triggered the hold, which checker flagged it, and what the action would have done. Reuse `FinalRiskReport.overlap_groups` (SPEC_12) directly here if the flagged content and the action arguments were connected via the semantic overlap detector — this gives you a genuinely explainable hold reason ("the account balance in this update_record call matches text flagged by the Performance checker as an unsupported claim, risk=0.81") rather than a generic "action blocked."

---

## 4. The simulated example (what you actually build for the demo)

**Scenario: customer support agent, hallucinated refund amount → blocked `update_record` call.**

1. **Setup**: a customer-facing support agent (use case: `customer_facing_chat` per SPEC_11) is asked about a refund. The underlying LLM, without solid grounding in retrieved order data, generates: *"I've processed a refund of $340.00 to your account, reference #RF-88213."* — and, because this is an agent, also emits a tool call: `update_record(account_id="cust_4471", field="refund_status", value={"amount": 340.00, "ref": "RF-88213"})`.
2. **Text-level check (existing pipeline, SPEC_09–12 all apply unchanged)**: Performance checker flags the amount and reference number as unsupported by any retrieved order/refund record — this is a hallucination, Tier-1 SelfCheckGPT fires (per SPEC_10/11's cascade), risk score ~0.78.
3. **Action-level check (this spec, new)**: `ActionRiskChecker.tier0_gate` sees `update_record` in the catalog as `reversible_with_audit` / `single_entity` — not an automatic Tier-1 escalation on catalog grounds alone, but the cheap overlap check (§3.2, reusing SPEC_12) finds that the flagged hallucinated span ("$340.00... RF-88213") **is** the action's argument payload — overlap found, escalate to Tier-1.
4. **Tier-1 action judgment**: confirms the mismatch is severe enough to warrant a hold (per InferAct's preemptive-evaluation framing, §2.3) — the action is about to commit a fabricated refund amount to a real customer record.
5. **Decision split (§3.3)**: the text response is REGENERATEd (per SPEC_09 — the checkpoint-backtrack loop rewrites the response without inventing a refund amount, instead asking the system/agent to look up the real order first) **and** the original `update_record` call is BLOCKed outright, never reaching execution, with the §3.4 confirmation message logged.
6. **What's on screen for the judge**: a clear before/after — "here's the response and the tool call the agent was about to fire; here's the flagged span; here's why the action specifically was blocked, distinct from the text being separately regenerated; here's the audit entry."

**A second, smaller example worth having ready** (shows the catalog-driven, cheap-path case, contrasting with the overlap-driven case above): a request that would trigger `update_record_bulk` — the catalog entry alone (`blast_radius: many_entities`) is enough to force Tier-1 / HOLD regardless of content risk score, demonstrating that blast radius, not just content flagging, is an independent gating axis (per §2.4) — this is a fast, cheap-to-implement second beat for the demo that shows the system isn't *only* reactive to flagged text.

---

## 5. Step-by-step implementation guide

1. **Define `ProposedAction` schema** in `src/policy/schemas.py`: `name`, `arguments: dict`, `char_offset_in_response` (where in the generated text the action was proposed/justified, for overlap-checking against flagged spans).
2. **Author `action_catalog.yaml`** (§3.1) with 4–6 illustrative actions — enough for the two demo scenarios in §4, not an exhaustive taxonomy.
3. **Build `ActionRiskChecker`** in `src/agent/action_gate.py`, implementing `BaseChecker`'s interface (§3.2) — reuses `SemanticOverlapDetector` from SPEC_12 as its Tier-0 signal source, and a small LLM-judge micro-prompt (structured like the `access_risk(decision, rationale)` tool-call pattern used in agent-safety-judge literature — APPROVE/HOLD/BLOCK output, with a rationale string reused directly as the §3.4 confirmation message) for Tier-1.
4. **Wire into `pipeline.py`** at the point described in §3.3 — after Control Policy's text-level decision, before any action-executor call. For the hackathon demo, the "action executor" can be a stub/mock that just logs "WOULD HAVE CALLED: update_record(...)" — you are not required to build a real CRM/email integration, per the upgrade's own "simulated" framing.
5. **Extend the audit logger** (whatever store Upgrade #10 establishes) with an `action_decisions` table/log distinct from `text_decisions`, so the dashboard (Upgrade #8) can report them separately — "N actions held, M blocked, of which X were caught only because of the semantic-overlap check, not the catalog alone" is a strong, specific metric for a judge.
6. **Script the two demo scenarios from §4** as fixed, reproducible test inputs (not live-generated each time) so the demo is reliable — note this explicitly as a demo-reliability choice, not a limitation, in your presentation notes.

---

## 6. Testing checklist
- Unit test: catalog-only escalation (`update_record_bulk`) forces Tier-1/HOLD even when the overlap detector finds nothing — proves blast radius is an independent gating axis, not just a content-risk proxy.
- Unit test: overlap-driven escalation (the refund scenario) correctly connects a flagged span to an action's arguments via SPEC_12's detector, and is *not* triggered when a flagged span exists elsewhere in the response but doesn't feed the action's arguments (regression test against over-blocking unrelated actions).
- Unit test: text-level and action-level decisions can diverge (assert a case where text is ALLOWed/MODIFYed while the action is independently HELD) — this is the core architectural claim of §3.3 and should be directly testable, not just asserted in prose.
- Integration test: the two §4 scenarios run end-to-end through the mock action executor and produce the exact audit log entries described.

---

## 7. Reference list

- "FinHarness: An Inline Lifecycle Safety Harness for Finance LLM Agents," 2026 — arXiv:2605.27333
- "InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents," 2024 — arXiv:2403.02691
- "Check Yourself Before You Wreck Yourself: Selectively Quitting Improves LLM Agent Safety" — arXiv:2510.16492
- "LM Agents May Fail to Act on Their Own Risk Knowledge" — arXiv:2508.13465
- "InferAct: Inferring Safe Actions for LLMs-Based Agents Through Preemptive Evaluation and Human Feedback," 2024 — arXiv:2407.11843
- "ASTRA: Agentic Steerability and Risk Assessment Framework," 2026 — arXiv:2511.18114
- "MAGE: Safeguarding LLM Agents against Long-Horizon Threats via Shadow Memory" (APPROVE/REJECT security-judge tool-call pattern referenced in §3.2/§5) — arXiv:2605.03228
- "From Risk Classification to Action Plan Remediation: A Guardrail Feedback Driven Framework for LLM Agents" — arXiv:2606.05805
