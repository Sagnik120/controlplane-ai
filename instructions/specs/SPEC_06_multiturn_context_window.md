# SPEC_06 — Add Multi-Turn Compounding Risk Tracking via Rolling Session Context

**Status:** Ready to implement
**Touches:** `src/orchestrator/pipeline.py` (or `guarded_call.py` per `08_Folder_Structure.md`),
new `src/session/` module, `src/audit/audit_logger.py` (session_id field), `configs/use_case_policies.yaml`
**Independent of:** all other specs — this wraps the existing per-turn pipeline with a session
layer; it does not require any specific checker implementation to be upgraded first.

---

## 1. Why the current logic is weak

Per `codebase_analysis_and_roadmap.md`: `orchestrator/pipeline.py` evaluates each response payload
in **total isolation** — no session/conversation state at all. Per `01_PRD.md` section 5 (Explicit
Non-Goals), this was intentionally deferred: *"a very simple 'risk accumulates across turns in a
session' counter"* was flagged as acceptable if time allows, full implementation otherwise
deferred. This spec is that deferred work, now scoped properly with research backing rather than
an ad hoc counter.

This directly matters for the PS, which explicitly calls it out: *"Multi-turn conversations and AI
agents that take actions... introduce compounding risk, where one questionable output can shape
several downstream decisions."* A single-turn-only checker cannot catch: (a) gradual manipulation
across turns where no single turn looks unsafe in isolation, or (b) PII fragments disclosed across
multiple turns that only become identifying when combined.

## 2. The research this is based on

Two directly relevant, recent papers, covering the two distinct sub-problems your PS names:

1. **Temporal Context Awareness (TCA)** — Kulkarni & Namer, 2025, arXiv:2503.15560. Defends against
   multi-turn manipulation by continuously analyzing three signals across the conversation:
   **semantic drift** (how far the current turn's topic/intent has moved from the conversation's
   stated purpose), **cross-turn intention consistency** (does the user's apparent goal stay
   coherent, or does it shift in a way consistent with a gradual jailbreak/social-engineering
   pattern), and **evolving conversational patterns** generally. This is the right technique for
   catching the case where each individual turn passes single-turn Safety/Bias checks but the
   *trajectory* of the conversation is concerning — which is exactly the PS's "compounding risk"
   framing, not just "did this one message look bad."

2. **CAMP (Cumulative Agentic Masking and Pruning)** — Panjwani, 2025, arXiv:2604.16521. Formally
   defines **Cumulative PII Exposure (CPE)** as a session-level metric: individual PII fragments
   disclosed across separate turns (a name in turn 2, a city in turn 5, an employer in turn 9) may
   each be sub-threshold for a per-turn PII checker, but **combined, they re-identify a specific
   person**. CAMP's finding, directly quoted in essence: standard per-turn baselines expose the
   full accumulated profile because they never look at the conversation as a whole; CAMP detects
   the combination risk and intervenes before a re-identification threshold is crossed. This is a
   precise, citable justification for why your existing per-turn PII checker (SPEC_02) is
   necessary but not sufficient, and gives you a second, distinct multi-turn risk type to
   demonstrate beyond "conversation drifting toward something bad."

Both papers describe the same **architectural shape**: maintain a **rolling session state** object
that accumulates signals across turns (not full replay of every turn's text through every checker
again, which would blow your latency budget) and periodically evaluate the accumulated state
against its own thresholds, separate from any single turn's per-turn risk profile.

## 3. Design

### 3.1 Session state object (new, lightweight — not a database)
```
SessionRiskState:
    session_id: str
    turn_count: int
    # For TCA-style drift tracking:
    initial_intent_embedding: Optional[vector]     # embedding of first user message/stated purpose
    last_n_turn_embeddings: List[vector]            # rolling window, e.g. last 5 turns
    semantic_drift_score: float                     # cosine distance of latest turn from initial intent
    # For CAMP-style cumulative PII tracking:
    accumulated_pii_entities: Dict[entity_type, List[{value, turn_index, confidence}]]
    cumulative_pii_exposure_score: float             # see §3.3
    # General accumulation:
    per_turn_risk_history: List[{turn_index, risk_profile, decision}]
    session_risk_trend: "stable" | "escalating" | "de-escalating"
```
Store this **in-memory, keyed by `session_id`**, for the hackathon prototype (a Python dict in the
orchestrator process is sufficient — do not add Redis/a database, per `01_PRD.md`'s non-goals and
`03_Rules.md`'s dependency boundaries). Note in `docs/progress.md` that persistence across server
restarts is a documented limitation, not a bug, for this prototype scope.

### 3.2 Semantic drift signal (TCA-inspired)
- Embed each user turn using a lightweight sentence-embedding model (reuse
  `sentence-transformers`, already a dependency from SPEC_01's BERTScore variant — do not add a
  second embedding library).
- On turn 1, store the embedding as `initial_intent_embedding`.
- On each subsequent turn, compute cosine distance between the current turn's embedding and
  `initial_intent_embedding`, AND between the current turn and the previous turn (drift from start,
  and drift from immediate predecessor — TCA's "cross-turn intention consistency").
- If drift-from-start exceeds a configurable threshold AND the trend across recent turns is
  monotonically increasing (not just one noisy spike), raise `semantic_drift_score` and treat it as
  an additional risk input to that turn's Control Policy decision — not a replacement for per-turn
  checkers, an addition.

### 3.3 Cumulative PII exposure signal (CAMP-inspired)
- Every time SPEC_02's PII checker fires (even below its own per-turn threshold — this is the key
  point CAMP makes: **do not gate this on the per-turn checker having already flagged the response**,
  collect every detected entity regardless of confidence), append the entity to
  `accumulated_pii_entities` for that session.
- Define a simple, explainable **re-identification proxy score**: count of *distinct entity types*
  accumulated across the session (e.g. PERSON + LOCATION + ORGANIZATION + a date = 4 distinct
  identifying fragments), since the actual re-identification-risk math CAMP uses is more involved
  than a hackathon prototype needs — state this simplification explicitly as a scoped-down proxy,
  not a full re-implementation of CAMP's formal CPE metric.
- If distinct-entity-type count crosses a configurable threshold (e.g. 3+), raise
  `cumulative_pii_exposure_score` and escalate that turn's decision even if the current turn's own
  PII checker alone would have allowed it.

### 3.4 How this feeds the existing pipeline (does not replace it)
- After the existing per-turn Risk Engine produces its `FinalRiskReport` (unchanged), the
  orchestrator now ALSO updates `SessionRiskState` and checks the two session-level signals above.
- If either session-level signal crosses its threshold, this is surfaced to `control_policy.py` as
  an **additional risk input**, alongside (not replacing) the per-turn risk profile — reuse SPEC_03's
  tiered ALLOW/MODIFY/REGENERATE/HUMAN structure; a session-level escalation should generally push
  toward HUMAN, since a compounding pattern across turns is exactly the "automated confidence is
  low, conflicting signals" case that action was designed for.
- Add `session_id`, `semantic_drift_score`, and `cumulative_pii_exposure_score` to the audit log
  schema so this is visible in governance review, per `02_Architecture.md`'s audit schema section.

## 4. Step-by-step implementation plan

**Step 1 — Create `src/session/session_state.py`**
Define the `SessionRiskState` dataclass/Pydantic model from §3.1, and a `SessionStore` class
wrapping an in-memory dict (`Dict[str, SessionRiskState]`) with `get_or_create(session_id)` and
`update(session_id, turn_result)` methods.

**Step 2 — Wire `session_id` through the API layer**
- `src/api/routes.py`: accept an optional `session_id` in the `/generate` (or `/chat`) request body;
  if absent, generate a new UUID and return it to the client so the dashboard can persist it across
  turns in the same browser session.

**Step 3 — Implement semantic drift tracking**
- Add embedding computation (reusing `sentence-transformers`) in `session_state.py`.
- Implement the drift-from-start and drift-from-previous cosine distance calculations.
- Add the monotonic-trend check (e.g., last 3 drift measurements all increasing) before flagging,
  to avoid a single noisy/off-topic-but-harmless turn triggering a false escalation.

**Step 4 — Implement cumulative PII tracking**
- Hook into the existing PII checker's output (SPEC_02) to append entities to session state
  regardless of that turn's own risk_score threshold, per §3.3.
- Implement the distinct-entity-type counting proxy score.

**Step 5 — Wire session signals into `control_policy.py`**
- Add `session_risk_input: Optional[SessionRiskState]` as an additional parameter alongside the
  existing `FinalRiskReport` in the decision function.
- If session-level thresholds are crossed, bias the decision toward `HUMAN` per §3.4 — implement
  this as an explicit override rule stacked on top of SPEC_03's calibrated tiers, not a silent
  threshold change to the per-turn calibration.

**Step 6 — Config knobs**
```yaml
session_risk:
  drift_window_size: 5                    # rolling window of turns for drift calculation
  drift_threshold: 0.55                   # cosine distance threshold
  require_monotonic_trend: true
  cumulative_pii_distinct_type_threshold: 3
  session_escalation_action: "HUMAN"      # what session-level breach forces
```

## 5. Definition of Done

- [ ] `SessionRiskState` and `SessionStore` implemented, session persists in-memory across turns
      within a server process lifetime.
- [ ] Semantic drift score computed per turn using reused `sentence-transformers` embeddings, with
      monotonic-trend gating to avoid single-turn false positives.
- [ ] Cumulative PII exposure proxy score computed across all turns in a session, independent of
      any single turn's own PII risk threshold.
- [ ] `control_policy.py` accepts session-level signals as an additional input and can override
      toward HUMAN when session thresholds are crossed, without changing SPEC_03's per-turn
      calibration.
- [ ] Audit log includes `session_id`, `semantic_drift_score`, `cumulative_pii_exposure_score` per
      entry.
- [ ] Diagnostic script simulates two realistic multi-turn sessions: (1) a gradual-drift scenario
      (5 turns, each individually benign, drifting steadily toward a sensitive topic) — confirm
      escalation triggers by turn 4-5 but not turn 1-2; (2) a fragmented-PII scenario (name in turn
      1, employer in turn 3, city in turn 5, none individually above the per-turn PII threshold) —
      confirm cumulative exposure triggers HUMAN escalation despite every individual turn passing.
- [ ] Pitch deck slide cites: Temporal Context Awareness (Kulkarni & Namer, arXiv:2503.15560) for
      the drift/consistency mechanism, and CAMP (Panjwani, arXiv:2604.16521) for the cumulative PII
      exposure concept — with the explicit, honest claim: "we implement a scoped-down proxy of
      CAMP's formal Cumulative PII Exposure metric, not the full paper's method, appropriate for a
      prototype demonstrating the mechanism."
