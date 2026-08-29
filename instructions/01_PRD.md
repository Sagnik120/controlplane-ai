# 01_PRD.md — Product Requirements Document

## STATUS: AUTHORITATIVE. Read this file first, in full, before writing any code.

---

## 1. What We Are Building

**ControlPlane.ai** is a **model-agnostic runtime governance layer** for AI-generated responses.
It does NOT generate responses itself. It wraps around any existing LLM (Gemini, OpenAI, a local
model, or a mocked/simulated model) and, while a response is being generated, continuously scores
it across three risk families:

1. **Performance risk** — is the response likely wrong / hallucinated / low-confidence?
2. **Responsibility risk** — is it unsafe, biased, or leaking PII/confidential data?
3. **Cost risk** — is this response consuming more compute/time than the task justifies?

Based on the combined risk profile, ControlPlane decides one of four actions:

- **ALLOW** — release the response as-is
- **MODIFY** — repair only the problematic span, then release
- **REGENERATE** — discard and regenerate with adjusted prompt/model/constraints
- **HUMAN** — escalate to a human reviewer, do not auto-release

This is NOT a chatbot. This is NOT a new LLM. It is a **middleware/wrapper layer** that sits between
a calling application and an LLM provider's API.

---

## 2. Why This Exists (Problem Statement, do not deviate from this framing)

Enterprises deploy AI across many different use cases (customer-facing chatbots, internal copilots,
regulated decision-support tools) simultaneously. Each use case has a different risk tolerance and
latency budget. Today, bad AI outputs (hallucinations, bias, PII leaks, runaway cost) are discovered
**after** a user has already acted on them. ControlPlane moves detection to be **continuous and live**,
during generation, not after the fact.

Constraints that MUST shape every design decision:
- We only have access to the **input/output layer** of the LLM (prompt in, tokens out). We do NOT
  assume access to model internals/weights/hidden states in the primary build. (A "grey-box" mode
  using logits/token-probabilities is a stretch feature, not a requirement.)
- Different use cases need different risk tolerance and different latency budgets. This must be a
  **configuration**, not a hardcoded behavior.
- Risk categories overlap (a fabricated fact about a real person is both a hallucination AND a PII
  issue). The system should surface this overlap, not silently pick one category and ignore the other.
- There is often no ground truth to check a claim against. Confidence-based estimation is acceptable;
  we are not required to prove correctness/incorrectness with certainty.
- Over-flagging causes alert fatigue; under-flagging causes liability. Thresholds must be tunable,
  not fixed on principle.
- Every decision must be **logged and explainable** (audit trail) for governance purposes.

---

## 3. Target Users (for framing/demo purposes)

- **Enterprise AI platform teams** who operate multiple GenAI use cases at once and need one
  governance layer across all of them, instead of building bespoke safety code per project.
- **Compliance/risk stakeholders** who need an audit trail and metrics they can defend to a regulator
  or skeptical executive.
- **End users of the underlying AI product** (indirect beneficiary) — they experience fewer confidently
  wrong, biased, or leaking responses, without knowing ControlPlane exists.

---

## 4. Core Features (Must-Have for Round 2 Prototype)

These are REQUIRED. Do not skip any of these. Do not silently substitute a simpler feature without
flagging it to the user first.

1. **LLM Adapter Layer** — a common interface (`generate_stream()` or equivalent) implemented by
   at least: (a) a real Gemini adapter, (b) a Mock/Simulated adapter that returns deterministic
   canned outputs including deliberately-flawed ones for demo purposes, and (c) optionally one more
   real provider if time allows. ControlPlane must call ONLY the interface, never a provider directly.
2. **Streaming Buffer** — collects generated output in small windows (token or sentence based)
   before it is checked, simulating real-time interception.
3. **Performance Checker** — produces a performance-failure risk score (0.0–1.0) using heuristics
   (e.g., hedging language detection, self-contradiction, confidence signals) — NOT a requirement to
   solve hallucination detection perfectly, just produce a reasoned score.
4. **Responsibility Checkers** — three sub-checkers: Safety, Bias, PII. Each outputs an independent
   risk score AND flags whether it overlaps with another checker's flagged span (e.g., PII checker
   and Performance checker both flag the same sentence → surfaced as an "overlapping risk" case).
5. **Cost Monitor** — tracks tokens used, model tier used, generation time, and computes a cost-risk
   score (e.g., "small task run on large model" = high cost risk).
6. **Risk Engine** — combines all scores into a single risk profile object (not a single average
   number). Must retain all individual sub-scores.
7. **Use-Case Policy Config** — a config file (see 02_Architecture.md) defining different thresholds
   per use case (e.g., `customer_support_chatbot`, `internal_knowledge_assistant`,
   `decision_support_regulated`). The Control Policy must load the correct config based on which
   use case is active, and the SAME underlying checkers must produce DIFFERENT decisions for the
   same input depending on which use case is selected. This must be demoable live (switch a dropdown,
   same prompt, different outcome).
8. **Control Policy** — applies the loaded thresholds to the risk profile and returns exactly one of
   ALLOW / MODIFY / REGENERATE / HUMAN, with a human-readable reason string.
9. **Audit Log** — every single decision is appended as a structured record (timestamp, use case,
   risk profile, policy applied, decision, reason, latency) to a local file/DB. Must be viewable
   (simple table view or endpoint).
10. **Dashboard / UI** — a visual view showing: the live checker scores as a response streams, the
    final risk profile, the decision taken, and a way to switch use case and LLM provider live.
11. **Metrics Summary** — over a batch of test prompts, report basic aggregate stats: how many
    ALLOW/MODIFY/REGENERATE/HUMAN, and a manually-labeled false positive/negative estimate over the
    test set (see 07_Test.md).

## 5. Explicit Non-Goals (Do NOT build these — do not let scope creep in)

- No mobile app.
- No user authentication / login system.
- No production-grade database (SQLite or flat JSON files are sufficient).
- No real-time regulatory rule engine per geography — acknowledge this as a "pluggable policy config"
  concept only, do not hardcode actual laws.
- No fully-solved hallucination detection research problem — heuristic/confidence-based scoring is
  sufficient and expected.
- No actual production deployment/hosting — local run via clear README instructions is sufficient.
- No fine-tuning or training any model.
- No feedback-loop learning system that improves over time — describe as future roadmap, do not build.
- No multi-turn conversation state management beyond a basic session risk accumulator stub — if time
  allows, add a very simple "risk accumulates across turns in a session" counter; if time doesn't
  allow, log it as a documented future extension, do not attempt a full implementation.

## 6. Definition of Done for the Round 2 Deliverable

The prototype is considered complete when:
- A user can pick a use case + LLM provider from the dashboard, submit a prompt, and see the response
  stream in with live checker scores, ending in a visible ALLOW/MODIFY/REGENERATE/HUMAN decision.
- The exact same prompt produces a different decision when the use case is switched (proving the
  policy config layer works).
- At least 15 predefined test prompts (see 07_Test.md) run through the system with logged results.
- The audit log contains a full explainable trail for every decision made during testing.
- A metrics summary can be generated from the audit log.
- The README allows a judge to clone the repo and run it with the documented commands only.