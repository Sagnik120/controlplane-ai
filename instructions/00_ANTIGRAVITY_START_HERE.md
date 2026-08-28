# INITIAL PROMPT FOR ANTIGRAVITY (Gemini 3 Pro) — paste this as your first message

You are building **ControlPlane.ai**, a model-agnostic runtime governance layer for AI responses,
for a hackathon submission with a hard deadline. A complete `instructions/` folder has been provided
in this repository. You must treat every file in `instructions/` as authoritative and binding —
do not deviate from it without stopping to ask me first.

## Before you write any code, do the following in order:

1. Read `instructions/01_PRD.md` in full — this defines WHAT we are building and why.
2. Read `instructions/02_Architecture.md` in full — this defines HOW it is built (stack, patterns,
   data flow, config schemas).
3. Read `instructions/03_Rules.md` in full — these are hard boundaries. The most important one:
   **you must never execute shell/terminal commands yourself.** Whenever a command needs to be run
   (installing dependencies, running the server, running git commands, running tests), output the
   exact command in a code block and ask me to run it in my own terminal and paste back the result.
   You then read that result and proceed accordingly. Do not assume success without seeing my output.
4. Read `instructions/04_Phases.md` in full — this defines the exact sequence of phases you must
   follow, in order, without skipping ahead. Each phase has explicit exit criteria that I must
   confirm before you move to the next phase.
5. Read `instructions/05_Design.md` — only relevant once you reach Phase 7, but read it now for
   context.
6. Read `instructions/06_Memory.md` — you must append a structured entry to this file after
   completing each phase, following the template inside it exactly.
7. Read `instructions/07_Test.md` in full — every phase has a required diagnostic script. You write
   the script, I run it, you read the output I paste back and confirm pass/fail. No phase is
   "done" until its diagnostic passes.
8. Read `instructions/08_Folder_Structure.md` — this is the ONLY folder structure to use. Create it
   exactly as specified in Phase 0.
9. Read `instructions/09_Progress_Tracker.md` — you must keep `docs/progress.md` updated per this
   spec, in sync with `06_Memory.md`, after every phase.
10. Read `instructions/10_Git_Discipline.md` — you never run git commands yourself. You output the
    exact `git add` / `git commit` commands for me to run after each meaningful unit of work, using
    the commit message format specified there.
11. Read `instructions/11_Token_Efficiency.md` — follow these efficiency rules for how you manage
    context and communicate, but never let them override the rules in 03_Rules.md.

## Then do this:

- Confirm to me, in a short summary, that you've read and understood all 11 files, and briefly
  restate: (a) what ControlPlane.ai is, (b) what tech stack we're using, (c) what Phase 0 requires.
- Then begin Phase 0 exactly as defined in `04_Phases.md`: create the full folder structure from
  `08_Folder_Structure.md`, the `.env.example`/`.gitignore` (already present — verify they match
  spec), `requirements.txt`, and a minimal FastAPI app with a `/health` endpoint.
- Output the exact terminal commands I need to run to set up a virtual environment, install
  dependencies, and start the server.
- Stop there and wait for me to confirm the health check works before proceeding to Phase 1.

## Constraints to keep in mind throughout:

- I am the only one running commands in the terminal. You never execute anything yourself.
- I have a Gemini API key I will add to my local `.env` (not shared with you in chat).
- My GitHub username is `Sagnik120` — the repo will be public, name it `controlplane-ai`.
- This is a hard deadline project — prioritize working, tested code over polish at every phase
  except Phase 7 (Design) and Phase 9 (final docs), where presentation quality matters for judging.
- If you are ever uncertain or about to make a significant unprompted decision, stop and ask me
  per the stop-and-ask conditions in `03_Rules.md` — do not guess silently.

Confirm you've read everything, then begin.
