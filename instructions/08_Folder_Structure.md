# 08_Folder_Structure.md — Canonical Project Structure

## STATUS: AUTHORITATIVE. This is the ONLY folder structure to use. Do not create alternate/parallel
## structures. This is written assuming 2-3 people may work on this codebase in parallel in the
## future — folder boundaries exist so different people can own different folders without collisions.

---

## Full Canonical Structure

```
controlplane-ai/
│
├── instructions/                      # planning docs — read-only reference for the agent, not app code
│   ├── 00_ANTIGRAVITY_START_HERE.md
│   ├── 00B_SPEC_UPGRADES.md
│   ├── 01_PRD.md
│   ├── 02_Architecture.md
│   ├── 03_Rules.md
│   ├── 04_Phases.md                   # CLOSED/historical — Phase 0-9 checklist only
│   ├── 05_Design.md
│   ├── 06_Memory.md
│   ├── 07_Test.md
│   ├── 08_Folder_Structure.md
│   ├── 09_Progress_Tracker.md
│   ├── 10_Git_Discipline.md
│   ├── 11_Token_Efficiency.md
│   └── specs/
│       └── SPEC_TRACKER.md            # <- only file here until a new spec is handed over
│           # SPEC_NN_<slug>.md files are added ONE AT A TIME here as Sagnik hands them over,
│           # continuing numbering from SPEC_04 onward. SPEC_01-03 have been deleted from this
│           # folder — their outcomes are summarized in SPEC_TRACKER.md section 1 and in
│           # 06_Memory.md. Do not recreate SPEC_01-03 files. Do not pre-write a SPEC_NN file for
│           # an item still marked `[ ]` in SPEC_TRACKER.md — that is Sagnik's to bring.
│
├── scripts/                      # one-off utility scripts, e.g. recalibrate.py
│   └── recalibrate.py
│
├── src/
│   ├── __init__.py
│   ├── adapters/                      # OWNER: whoever works on LLM integrations
│   │   ├── __init__.py
│   │   ├── base_adapter.py
│   │   ├── mock_adapter.py
│   │   ├── gemini_adapter.py
│   │   └── openai_adapter.py          # optional/stretch
│   │
│   ├── checkers/                      # OWNER: whoever works on detection logic
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── performance_checker.py     # SelfCheckGPT-based (SPEC_01, done)
│   │   ├── safety_bias_checker.py     # LLM-as-judge w/ keyword pre-filter (SPEC_04, done)
│   │   └── pii_checker.py             # Presidio hybrid (SPEC_02, done)
│   │
│   ├── engine/                        # OWNER: combines checker outputs
│   │   ├── __init__.py
│   │   └── risk_engine.py             # noisy-OR + severity-multiplier overlap scoring (SPEC_05, done)
│   │
│   ├── policy/                        # OWNER: governance/decision logic
│   │   ├── __init__.py
│   │   ├── control_policy.py          # conformal tiered routing (SPEC_03, done); REGENERATE
│   │   │                              # branch wired to checkpoint-backtrack regen (SPEC_09, done)
│   │   └── schemas.py
│   │
│   ├── session/                       # OWNER: multi-turn session risk state
│   │   ├── __init__.py
│   │   └── session_state.py           # drift + cumulative PII tracking (SPEC_06, done); still an
│   │                                  # in-memory dict — target for item #12 (awaiting spec)
│   │
│   ├── repair/                        # OWNER: MODIFY-path span repair
│   │   ├── __init__.py
│   │   └── span_repair.py             # LLM micro-repair + Presidio anonymizer routing (SPEC_08,
│   │                                  # done) — BUT splice in pipeline.py line 88 still uses
│   │                                  # str.replace, confirmed fragile — target for item #14 (awaiting spec)
│   │
│   ├── feedback/                      # OWNER: human review / calibration feedback loop
│   │   ├── __init__.py
│   │   └── feedback_store.py          # harvests to calibration_set.jsonl (SPEC_07, done);
│   │                                  # triggered manually via scripts/recalibrate.py by design
│   │
│   ├── audit/                         # OWNER: logging/audit trail
│   │   ├── __init__.py
│   │   ├── logger.py                  # JSONL today — target for item #13 (awaiting spec)
│   │   └── reader.py
│   │
│   ├── orchestrator/                  # OWNER: ties everything together
│   │   ├── __init__.py
│   │   └── pipeline.py                # fully synchronous today — target for item #10 (awaiting spec)
│   │
│   ├── api/                           # OWNER: FastAPI routes
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── routes.py
│   │
│   └── dashboard/                     # OWNER: frontend
│       ├── index.html
│       ├── styles.css
│       └── app.js                     # target for item #11 (metrics dashboard, awaiting spec)
│
├── configs/
│   ├── use_case_policies.yaml         # latency_budget_ms exists but unused at runtime — item #06
│   └── model_registry.yaml
│
├── tests/                             # mirrors src/ structure exactly, see 07_Test.md
│   ├── adapters/
│   ├── performance_checker/
│   ├── responsibility_checkers/
│   ├── cost_monitor/
│   ├── risk_engine/
│   ├── control_policy/
│   ├── integration/
│   └── run_all_diagnostics.py
│
├── docs/
│   ├── progress.md                    # see 09_Progress_Tracker.md
│   └── metrics_report.md              # generated by Phase 8 script; base for item #11
│
├── data/
│   ├── audit_log.jsonl                # target for item #13 (move off JSONL, awaiting spec)
│   ├── human_review_queue.jsonl       # target for item #08 (awaiting spec)
│   └── calibration_set.jsonl
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── LICENSE
```

## Rules for This Structure

1. **One folder = one responsibility.** If a new piece of logic doesn't clearly belong in an existing
   folder, stop and ask before inventing a new top-level folder.
2. **Every `src/` subfolder mirrors into a `tests/` subfolder with the same name.** Non-negotiable.
3. **No logic lives directly in `src/` root.** Everything belongs inside a named subfolder.
4. **`instructions/` is never imported by application code.** Documentation only.
5. **If 2-3 people work in parallel later**, the intended split is: Person A owns `adapters/` +
   `checkers/`, Person B owns `engine/` + `policy/` + `session/` + `feedback/`, Person C owns
   `api/` + `dashboard/` + `orchestrator/` + `audit/` + `repair/`. Preserve these boundaries even
   if only one person is working right now.
6. **Config values never live in code.** Anything environment- or use-case-dependent goes in
   `configs/*.yaml`.
7. **The "target for item #NN" comments above are pointers, not permission.** They tell you which
   file a future spec will likely touch — they do not mean you may start editing that file before
   the corresponding `SPEC_NN_*.md` exists. See `00B_SPEC_UPGRADES.md` section 3.