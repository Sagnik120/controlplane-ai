# 00B_SPEC_UPGRADES.md — Stage 3 Upgrade System (supersedes the Stage 2 version of this file)

## STATUS: AUTHORITATIVE. Read this AFTER `00_ANTIGRAVITY_START_HERE.md` and BEFORE resuming any
## work. `docs/progress.md` should show Phases 0–9 DONE and SPEC_01–03 DONE. This file governs a
## THIRD stage of work: hardening and demo-readiness upgrades on top of the already-working,
## already-upgraded skeleton. It does NOT change the architecture, folder structure, tech stack, or
## non-goals defined in `01_PRD.md` / `02_Architecture.md` / `08_Folder_Structure.md`. Those remain
## fully authoritative and unchanged.

---

## 1. What Changed From Stage 2

Stage 2 (governed by the previous version of this file) took the Phase 0–9 rule-based prototype and
upgraded three specific modules to research-grade methods: the Performance Checker (SelfCheckGPT),
the PII Checker (Presidio hybrid), and the Control Policy (conformal-prediction tiered routing).
Those three specs are DONE, shipped, and tested. **Do not reopen them without an explicit new spec
file asking you to.**

Stage 3 is different in kind, not just in content: it is not primarily about swapping a detection
*method* for a more advanced one inside an already-correct box. It is about closing the gap between
"the routing logic is correct" and "the system actually behaves correctly under real conditions" —
REGENERATE that doesn't regenerate, latency that would fail a live demo, session state that breaks
under concurrent load, and so on. Some Stage 3 items are still detection/method upgrades (e.g. the
overlap detector); most are systems/engineering correctness upgrades.

## 2. Where the work items live now

```
instructions/specs/
└── SPEC_TRACKER.md              # <- READ THIS FIRST. The only current authority for "what's next."
```

The old `SPEC_01_performance_checker_selfcheckgpt.md`, `SPEC_02_pii_checker_presidio_hybrid.md`,
`SPEC_03_decision_logic_conformal_routing.md`, and the old `SPEC_TRACKER.md` have been **deleted**
from this folder. Their outcomes are preserved as a one-row-each summary at the top of the new
`SPEC_TRACKER.md` and in `06_Memory.md`'s `## Spec Upgrades (Post-Phase-9)` section — nothing about
what they built is lost, only the now-irrelevant implementation-detail files are gone.

New spec files for Stage 3 will be added to this same `specs/` folder one at a time, named
`SPEC_NN_<slug>.md` continuing the numbering from where SPEC_03 left off (i.e. the next one is
`SPEC_04...` — note this is the *file* number, distinct from the item `#04–#17` numbering used
inside `SPEC_TRACKER.md` to reference the 14 upgrade targets; the tracker will make clear which
spec file, when written, corresponds to which tracker item).

## 3. Critical rule specific to Stage 3: no unwritten specs

**Every Stage 2 spec file fully specified its own method** (the paper/repo it was based on, the
exact library, the data contract). Some Stage 3 items in `SPEC_TRACKER.md` are currently written
as **problem statements only** — they describe what's wrong and which files are likely affected,
deliberately without naming the fix. This is intentional: Sagnik is researching the approach for
each one and will hand you the actual method inside a numbered `SPEC_NN_*.md` file when it's ready.

Therefore, in addition to `03_Rules.md`:

1. If `SPEC_TRACKER.md` lists an item as `[ ]` (no spec file written), **you may discuss and clarify
   the problem, but you may not write implementation code for it.** Proposing a method when asked
   "what do you think the approach should be" is fine as a conversation; silently building it is not.
2. Once a `SPEC_NN_*.md` file exists for an item, treat it exactly as Stage 2 specs were treated:
   it is self-contained, states the method/paper/library, defines the data contract, gives a
   step-by-step plan mapped to real file paths, and a Definition of Done. Follow it literally.
3. A spec's "Touches:" line limits which files may be edited for that spec. The "Touches (expected)"
   lines currently in `SPEC_TRACKER.md` are Sagnik's best guess written before the method is chosen
   — the actual spec file's "Touches:" line is authoritative once it exists, even if it differs from
   the tracker's guess.
4. New dependencies named inside an approved, currently-active `SPEC_NN_*.md` file are pre-approved,
   same as the Stage 2 rule in `03_Rules.md` section 3. Any other new dependency still requires
   asking first.
5. Work on exactly ONE spec at a time, in `SPEC_TRACKER.md`'s priority order unless Sagnik
   explicitly reorders it.
6. After finishing a spec: verify its Definition of Done item by item, report pass/fail explicitly,
   update `SPEC_TRACKER.md` (`[ ]` → `[~]` when you receive it, `[~]` → `[x]` when done), update
   `06_Memory.md` / `docs/progress.md`, THEN STOP and wait for the next spec.

## 4. Relationship to the original architecture doc and Stage 2

`02_Architecture.md`'s diagrams and data-flow description remain ground truth for the **pipeline
shape** (Router → Buffer → Checkers → Risk Engine → Policy → Audit). Stage 3 items upgrade what
happens inside or around that shape — including, for items like #04 (real REGENERATE) and #10
(async pipeline), the *control flow between* boxes, not just internals of one box. Because of this,
some Stage 3 specs may legitimately need to touch `guarded_call.py` / orchestration code in ways
Stage 2 specs never did. This is expected and pre-authorized by this file — it does not require a
separate stop-and-ask under `03_Rules.md` rule 4 *as long as the box structure in the Architecture
diagram itself is unchanged* (still Router → Buffer → Checkers → Risk Engine → Policy → Audit, in
that order). If a spec would actually change that box structure, stop and ask regardless.

## 5. What NOT to do during this stage

- Do not re-run Phase 0–9 diagnostics or the SPEC_01–03 diagnostics as blocking gates for Stage 3
  work — they already passed. Only the active spec's own Definition of Done, plus
  `run_all_diagnostics.py` for regression safety, matter now.
- Do not modify `01_PRD.md`, `02_Architecture.md`, `03_Rules.md`, `08_Folder_Structure.md` to
  describe a specific spec's internal method — those files describe the stable system shape, not
  swappable internals. The specs themselves are the correct home for that detail.
- Do not write or scaffold a `SPEC_NN_*.md` file yourself "to save time" for an item still marked
  `[ ]` in the tracker. Sagnik is deliberately researching these before handing them over.