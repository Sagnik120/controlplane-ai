# 07_Test.md — Testing & Diagnostics Protocol

## STATUS: AUTHORITATIVE. Testing is not optional polish — a broken checker or policy bug can make
## the whole system produce wrong governance decisions silently. Treat every diagnostic run as a
## gate, not a suggestion.

---

## 0. Hard Rule Reminder

The agent NEVER runs test commands itself. The agent writes/updates the diagnostic script, then
outputs the exact terminal command for the human to run. The human pastes back the terminal output.
The agent reads that output and reports pass/fail per case — it does not assume success.

---

## 1. Test Folder Structure (mirrors src/ exactly)

```
tests/
├── adapters/
│   └── test_adapters_diagnostic.py
├── performance_checker/
│   └── test_performance_diagnostic.py
├── responsibility_checkers/
│   ├── test_safety_diagnostic.py
│   ├── test_bias_diagnostic.py
│   └── test_pii_diagnostic.py
├── cost_monitor/
│   └── test_cost_diagnostic.py
├── risk_engine/
│   └── test_risk_engine_diagnostic.py
├── control_policy/
│   └── test_control_policy_diagnostic.py
├── integration/
│   └── test_full_pipeline_diagnostic.py
└── run_all_diagnostics.py     # runs every script above in sequence, prints a final summary table
```

## 2. Per-Component Diagnostic Requirements

Every diagnostic script must, at minimum:
1. Print which component is being tested and what it depends on.
2. Run at least 5 hand-crafted cases: 1 clearly-clean, 1 clearly-flagged (obvious), 1 ambiguous/
   borderline, 1 edge case (empty input, extremely long input, or malformed input), 1 case designed
   to test the overlap/interaction with another component if relevant.
3. For each case, print: input (truncated), expected outcome, actual outcome, PASS/FAIL.
4. End with a summary line: `X/5 PASSED`. If any FAIL, print the failing case in full detail.
5. Never let one failing case stop the whole script — collect all results, then report.

## 3. Deep System-Level Diagnostics (run after EVERY phase, not just at the end)

In addition to the per-component tests above, `run_all_diagnostics.py` must:
- Run every individual diagnostic script in sequence.
- Additionally run a **full end-to-end smoke test**: submit one prompt through the complete
  `guarded_call()` pipeline per use case (3 total), confirm no exceptions are raised, confirm an
  audit log entry is created for each, confirm the decision returned is one of the 4 valid values.
- Print a final table: component name | pass count | fail count | overall status.
- If ANY component fails, print a clear `SYSTEM STATUS: NOT STABLE — DO NOT PROCEED TO NEXT PHASE`
  banner. If all pass: `SYSTEM STATUS: STABLE`.

This full run must be done by the human after completing EVERY phase in `04_Phases.md`, not only at
project end — this is the mechanism that prevents a broken Phase 2 checker from silently corrupting
Phase 6 integration.

## 4. Required Test Prompt Set (the 15+ prompts referenced in PRD/Phases)

Define this concrete set in `tests/integration/test_prompts.py` as a Python list of dicts, each with
`id`, `prompt`, `use_case`, `expected_decision` (best guess, human-labeled), `category` (one of:
clean, hallucination, bias, pii, cost, overlap, ambiguous, multi-turn-stub). Minimum categories to
cover:
1. A clean factual prompt (expect ALLOW across all use cases).
2. A prompt engineered to produce a confidently-wrong/hallucinated answer (via MockAdapter's flawed
   canned response) — expect MODIFY or REGENERATE depending on use case.
3. A prompt that surfaces biased/stereotyped phrasing — expect MODIFY or HUMAN depending on severity.
4. A prompt that leaks fake PII (SSN/email pattern) — expect MODIFY or HUMAN.
5. A prompt engineered to be expensive/inefficient (long unnecessary generation for a trivial
   question) — expect flag on cost_risk specifically.
6. A prompt where the flawed detail is BOTH a hallucination AND a PII issue (a fabricated fact about
   a named real-sounding person) — expect `overlaps_detected` populated, and decision at least MODIFY.
7. A genuinely ambiguous prompt with no clear right answer — expect HUMAN or a borderline ALLOW,
   used to demonstrate the alert-fatigue tuning tradeoff.
8. At least 8 more varied prompts spanning the above categories with different phrasing, to prove
   the system isn't just pattern-matching a handful of keywords.

## 5. "Deep Diagnostic" Definition (why this matters more than usual)

Because ControlPlane's entire value proposition is trustworthy governance, a silent bug (e.g., PII
checker always returning 0.0 due to a regex typo) is worse than a visible crash — it would let real
issues through undetected while looking like it works. Therefore:
- Every checker's diagnostic script MUST include at least one case where the expected score is HIGH
  (not just low/clean cases) — a checker that never fires is a failing checker even if it never
  crashes.
- After any code change to a checker, adapter, or policy file, re-run that component's diagnostic
  AND the full `run_all_diagnostics.py` — not just the component in isolation — because thresholds
  and combined scoring can interact in non-obvious ways.

## 6. Metrics / False Positive-Negative Estimation (Phase 8 support)

- Human manually labels each of the 15+ test prompts with a "should this have been flagged" ground
  truth (yes/no) before running the batch.
- The metrics script compares actual decisions against these labels and reports:
  - False positive rate: % of "should be ALLOW" prompts that got MODIFY/REGENERATE/HUMAN.
  - False negative rate: % of "should be flagged" prompts that got ALLOW.
  - Overall agreement rate.
- This output must be reproducible by re-running the script — do not hand-write these numbers into
  the README from memory.
