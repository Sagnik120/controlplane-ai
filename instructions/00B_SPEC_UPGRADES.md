# 00B_SPEC_UPGRADES.md — Post-Phase-9 Research Upgrade System

## STATUS: AUTHORITATIVE. Read this AFTER `00_ANTIGRAVITY_START_HERE.md` and BEFORE resuming any
## work, if `docs/progress.md` shows Phases 0-9 as already DONE. This file governs a SECOND stage
## of work that begins only after the original Phase 0-9 build (defined in `04_Phases.md`) is
## complete and stable.

---

## 1. What This Stage Is

`04_Phases.md` built the **working prototype skeleton** — rule-based checkers, a working pipeline,
a dashboard. That work is done (see `06_Memory.md`). This second stage **upgrades the detection and
decision logic inside that already-working skeleton** to research-grade methods, module by module,
for competitive differentiation in judging. It does NOT change the architecture, folder structure,
tech stack, or non-goals defined in `01_PRD.md` / `02_Architecture.md` / `08_Folder_Structure.md`.
Those remain fully authoritative and unchanged.

## 2. Where the actual work items live

All upgrade work is defined in `instructions/specs/`, not in `04_Phases.md`. Structure:

```
instructions/specs/
├── SPEC_TRACKER.md              # <- READ THIS FIRST. Master list, execution order, status per spec.
├── SPEC_01_performance_checker_selfcheckgpt.md
├── SPEC_02_pii_checker_presidio_hybrid.md
├── SPEC_03_decision_logic_conformal_routing.md
└── (more SPEC_NN files will be added over time as new research batches are approved)
```

(Previously these files had numeric-only names like `01_performance_checker_selfcheckgpt.md`, which
collided with `01_PRD.md`, `02_Architecture.md`, `03_Rules.md`, `04_Phases.md` in the parent
`instructions/` folder. They are now namespaced under `instructions/specs/` with a `SPEC_` prefix
and moved out of the flat root — do not put future spec files back in the flat `instructions/` root.)

## 3. Execution rules for this stage (in addition to, not instead of, `03_Rules.md`)

1. `instructions/specs/SPEC_TRACKER.md` is the ONLY authority for "what's next" during this stage.
   Do not treat `04_Phases.md` or `09_Progress_Tracker.md`'s Phase 0-9 checklist as defining
   remaining work — that checklist is closed/historical.
2. Work on exactly ONE `SPEC_NN_*.md` file at a time, strictly in the order
   `SPEC_TRACKER.md` lists them. Do not start SPEC_02 while SPEC_01 is `[~]`.
3. Every spec file is self-contained: it states why the current logic is weak, the exact
   paper/repo it's based on, the data contract, a step-by-step plan mapped to real file paths,
   and a Definition of Done checklist. Follow it literally — do not invent alternate approaches,
   libraries, or designs not named in the spec.
4. A spec's "Touches:" line at the top limits which files may be edited for that spec. Do not
   edit files outside that list unless the spec explicitly says to.
5. New dependencies named inside an approved spec file (e.g. `selfcheckgpt`, `presidio-analyzer`,
   `sentence-transformers`) are PRE-APPROVED — do not re-ask for permission per `03_Rules.md`
   section 3 for a library that is explicitly named inside a spec you are actively implementing.
   Any OTHER new dependency not named in the current spec still requires asking first.
6. `06_Memory.md` and `docs/progress.md` continue to be updated exactly as `09_Progress_Tracker.md`
   describes, but append a new top-level section titled `## Spec Upgrades (Post-Phase-9)` rather
   than inserting entries into the Phase 0-9 checklist.
7. After finishing a spec: verify its Definition of Done checklist item by item, report pass/fail
   explicitly, update `SPEC_TRACKER.md` (`[~]` → `[x]`), update `06_Memory.md` /
   `docs/progress.md`, THEN STOP and wait for explicit go-ahead before opening the next spec.
8. `02_Architecture.md`'s diagrams and data-flow description remain the ground truth for the
   PIPELINE SHAPE (Router → Buffer → Checkers → Risk Engine → Policy → Audit). Specs upgrade what
   happens INSIDE a box in that diagram, never the box structure itself, without an explicit stop-
   and-ask per `03_Rules.md` rule 4.

## 4. Relationship to the Round 1/2 architecture doc

The original concept doc (`ControlPlane (Accenture) (1).md`, if present in your repo/project
files — keep it, do not delete) described 4 Control Policy actions: ALLOW / MODIFY / REGENERATE /
HUMAN. `04_Phases.md` Phase 4 only partially implemented this (see `06_Memory.md` for what actually
shipped). `SPEC_03_decision_logic_conformal_routing.md` is what completes this properly. Treat any
gap between the original concept doc and what Phase 0-9 actually built as EXPECTED and already
accounted for by the spec system — it is not a new bug to fix ad hoc.

## 5. What NOT to do during this stage

- Do not re-run Phase 0-9 diagnostics as blocking gates for spec work — they already passed. Only
  the specific spec's own Definition of Done and any regression-relevant diagnostics
  (`run_all_diagnostics.py`) matter now.
- Do not modify `01_PRD.md`, `02_Architecture.md`, `03_Rules.md`, `08_Folder_Structure.md` to
  describe a specific spec's internal method (e.g. do not rewrite Architecture.md to say
  "Performance Checker uses SelfCheckGPT") — those files describe the stable system shape, not
  swappable internals. The specs themselves are the correct home for that detail.
