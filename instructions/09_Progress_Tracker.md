# 09_Progress_Tracker.md — Progress Tracking Protocol

## STATUS: AUTHORITATIVE. This defines how `docs/progress.md` must be maintained. Its purpose is
## so the human (Sagnik) can look at ONE file and instantly know what's done, what's left, and what's
## broken — without reading code or chat history.

---

## 1. Location

`docs/progress.md` — created at the start of Phase 0, updated continuously, never deleted or reset.

## 2. Required Structure of `docs/progress.md`

```markdown
# ControlPlane.ai — Progress Tracker

Last updated: <ISO date/time>

## Overall Status: <NOT STARTED / IN PROGRESS / STABLE / BLOCKED>

## Stage
Stage 3 — Post-Phase-9, Post-SPEC-01-03 hardening/demo-readiness upgrades.
See `instructions/00B_SPEC_UPGRADES.md` and `instructions/specs/SPEC_TRACKER.md`.

## Phase 0-9 Checklist (CLOSED — historical record only, do not treat as active work)
- [x] Phase 0 — Project Skeleton
- [x] Phase 1 — LLM Adapter Layer
- [x] Phase 2 — Individual Checkers
- [x] Phase 3 — Risk Engine + Overlap Detection
- [x] Phase 4 — Use-Case Policy Config + Control Policy
- [x] Phase 5 — Audit Log
- [x] Phase 6 — Full Orchestrator Integration
- [x] Phase 7 — Dashboard UI
- [x] Phase 8 — Metrics Summary
- [x] Phase 9 — Documentation & Final Polish

## Stage 2 Specs (CLOSED — historical record only)
- [x] SPEC_01 — Performance Checker (SelfCheckGPT)
- [x] SPEC_02 — PII Checker (Presidio hybrid)
- [x] SPEC_03 — Decision Logic (Conformal tiered routing)
- [x] SPEC_04 — Bias/Safety Checkers (LLM-as-judge) — checker-quality upgrade, not one of the 14
      Stage 3 tracker items
- [x] SPEC_06 — Multi-turn session risk tracking (semantic drift + cumulative PII) — new
      capability, not one of the 14 Stage 3 tracker items; keeps session storage in-memory by
      design (does not solve item #12)

## Stage 3 Upgrade Targets (ACTIVE — see SPEC_TRACKER.md for full detail)
- [x] 04 — Real REGENERATE (SPEC_09)
- [ ] 05 — Fix latency (parallel checkers, conditional heavy checks)
- [ ] 06 — Differentiate latency/risk budget by use case, live
- [x] 07 — Real semantic overlap detection (SPEC_05)
- [x] 08 — Live HUMAN feedback loop (SPEC_07, manually-triggered by design)
- [ ] 09 — Agent/tool-call risk modeling
- [ ] 10 — Fully async pipeline
- [ ] 11 — Metrics/monitoring dashboard
- [ ] 12 — Session state off in-memory dict (confirmed still open — `session_state.py` uses a
      module-level `self.sessions = {}` dict)
- [ ] 13 — Audit/feedback logs off JSONL
- [ ] 14 — Fix fragile span splicing (confirmed still broken — `pipeline.py` line 88 uses
      `.replace(span_text, replacement, 1)`)
- [ ] 15 — Governance/config layer polish
- [ ] 16 — Clean up conformal prediction claim
- [ ] 17 — Small polish pass

## Currently In Progress
- <one line: which Stage 3 item number, which SPEC_NN file, which specific task within it>

## Completed (most recent first)
- <date/time> — <what was completed> — <diagnostic script result: X/Y passed>

## Known Issues / Blockers
- <anything broken, stubbed, or waiting on a human decision, with enough detail to resume later>

## Explicit Deviations From Instruction Files
- <any place where the actual build diverged from instructions/*.md, and why, with a pointer to
  which file/line it affects>
```

## 3. Update Rules

- Update this file at MINIMUM: after every Stage 3 spec's Definition of Done passes, and any time
  work pauses (e.g., end of a work session) even mid-spec.
- The "Completed" section is append-only, newest entry on top — never delete old entries.
- If something is marked complete here, it MUST have a corresponding diagnostic pass recorded in
  `06_Memory.md`'s `## Spec Upgrades (Post-Phase-9)` section — these two files must never
  contradict each other. If they do, treat it as a bug and flag it to Sagnik immediately.
- Do not check off a Stage 3 item above until its `SPEC_NN_*.md` file exists AND its Definition of
  Done has passed — an item with no spec file yet stays `[ ]` regardless of how well-understood the
  problem is.
- This file is written for a reader who has NOT been following the build in real time — assume zero
  prior context per entry, but keep entries short (2-3 lines each).

## 4. Relationship to 06_Memory.md

- `06_Memory.md` is for the AGENT's own context recovery (dense, technical, phase-by-phase /
  spec-by-spec).
- `docs/progress.md` is for the HUMAN's quick status check (readable, checklist-style, less
  technical detail, more "what can I tell people about where we are").
- Both must be updated together — never update one without the other.