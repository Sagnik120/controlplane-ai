# INITIAL PROMPT FOR ANTIGRAVITY (Gemini 3 Pro) — paste this as your first message

You are building **ControlPlane.ai**, a model-agnostic runtime governance layer for AI responses,
for a hackathon submission with a hard deadline. A complete `instructions/` folder has been provided
in this repository. You must treat every file in `instructions/` as authoritative and binding —
do not deviate from it without stopping to ask first.

## If this is a FRESH session and `docs/progress.md` does NOT yet exist or shows Phases 0–9 as
## incomplete:

Follow the original bootstrap sequence — read `01_PRD.md`, `02_Architecture.md`, `03_Rules.md`,
`04_Phases.md`, `05_Design.md`, `06_Memory.md`, `07_Test.md`, `08_Folder_Structure.md`,
`09_Progress_Tracker.md`, `10_Git_Discipline.md`, `11_Token_Efficiency.md`, in that order, then
begin Phase 0 exactly as defined in `04_Phases.md`. This should not normally happen anymore — the
project is past this point — but the instructions remain here for a true clean-slate restart.

---

## If resuming a session where Phases 0–9 AND SPEC_01–03 are already DONE (the normal case —
## check `docs/progress.md` first):

**Do not restart Phase 0. Do not re-read `04_Phases.md`'s phase checklist as active work — it is
closed history.**

Read, in order:

1. `06_Memory.md` — read the full `## Spec Upgrades (Post-Phase-9)` section for context on what
   SPEC_01, SPEC_02, and SPEC_03 actually shipped.
2. `docs/progress.md` — current overall status.
3. `instructions/00B_SPEC_UPGRADES.md` — governs this current stage (Stage 3) in full. Read it
   completely before doing anything else.
4. `instructions/specs/SPEC_TRACKER.md` — the ONLY authority for "what's next." It lists 14
   upgrade targets. Most are currently `[ ]` (problem framing only, no method chosen yet — you may
   NOT implement these). Some may be `[~]` if Sagnik has since handed you a `SPEC_NN_*.md` file for
   one of them — if so, that file is your actual work order.

Then:

- If no `SPEC_NN_*.md` file exists yet for the item Sagnik wants worked on, say so plainly and do
  not proceed to write implementation code. You may discuss the problem and ask clarifying
  questions, but the method is Sagnik's to bring, per `00B_SPEC_UPGRADES.md` section 3.
- If a `SPEC_NN_*.md` file has been provided, follow it literally: read it in full, confirm you
  understand its "Touches:" file list and Definition of Done, then implement.

## Constraints that still apply, unchanged, in every stage:

- I am the only one running commands in the terminal. You never execute anything yourself.
- I have a Gemini API key in my local `.env` (not shared with you in chat).
- My GitHub username is `Sagnik120` — the repo is public, named `controlplane-ai`.
- This is a hard-deadline project — prioritize working, tested code over polish, except where a
  spec file explicitly says presentation/demo quality matters for that item.
- If you are ever uncertain or about to make a significant unprompted decision — including, in this
  stage, ever choosing a *method* for an item that has no spec file yet — stop and ask per
  `03_Rules.md` and `00B_SPEC_UPGRADES.md`. Do not guess silently.

Confirm you've read the relevant files for whichever case applies, briefly state what stage you
believe the project is in and what you understand the next actionable item to be, then wait for
confirmation before writing any code.