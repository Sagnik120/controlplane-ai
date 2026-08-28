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

## Phase Checklist
- [ ] Phase 0 — Project Skeleton
- [ ] Phase 1 — LLM Adapter Layer
- [ ] Phase 2 — Individual Checkers
- [ ] Phase 3 — Risk Engine + Overlap Detection
- [ ] Phase 4 — Use-Case Policy Config + Control Policy
- [ ] Phase 5 — Audit Log
- [ ] Phase 6 — Full Orchestrator Integration
- [ ] Phase 7 — Dashboard UI
- [ ] Phase 8 — Metrics Summary
- [ ] Phase 9 — Documentation & Final Polish

## Currently In Progress
- <one line: which phase, which specific task within it>

## Completed (most recent first)
- <date/time> — <what was completed> — <diagnostic script result: X/Y passed>

## Known Issues / Blockers
- <anything broken, stubbed, or waiting on a human decision, with enough detail to resume later>

## Explicit Deviations From Instruction Files
- <any place where the actual build diverged from instructions/*.md, and why, with a pointer to
  which file/line it affects>
```

## 3. Update Rules

- Update this file at MINIMUM: after every phase completes, and any time work pauses (e.g., end of
  a work session) even mid-phase.
- The "Completed" section is append-only, newest entry on top — never delete old entries, this is
  the project's history at a glance.
- If something is marked complete here, it MUST have a corresponding diagnostic pass recorded in
  `06_Memory.md` — these two files must never contradict each other. If they do, treat it as a bug
  and flag it to the human immediately.
- This file is written for a reader who has NOT been following the build in real time — assume zero
  prior context per entry, but keep entries short (2-3 lines each).

## 4. Relationship to 06_Memory.md

- `06_Memory.md` is for the AGENT's own context recovery (dense, technical, phase-by-phase).
- `docs/progress.md` is for the HUMAN's quick status check (readable, checklist-style, less
  technical detail, more "what can I tell people about where we are").
- Both must be updated together — never update one without the other.
