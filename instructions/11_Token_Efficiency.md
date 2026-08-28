# 11_Token_Efficiency.md — Token/Context Efficiency Rules

## STATUS: AUTHORITATIVE. Time and token budget are both scarce. Every wasted token re-reading or
## re-explaining something already documented is time not spent building.

---

## 1. Core Principle

The `instructions/` folder and `06_Memory.md` exist specifically so the agent never needs to re-read
the entire codebase or re-derive context from scratch. Use them as the source of truth instead of
re-scanning files "just in case."

## 2. Rules to Follow

1. **Never re-read files you already read this session** unless you have specific reason to believe
   they changed. Trust your own recent context first.
2. **At the start of a new session**, read ONLY: `06_Memory.md` (most recent entries),
   `docs/progress.md`, and the specific phase section of `04_Phases.md` you're about to work on.
   Do NOT re-read all 11 instruction files every session — read `03_Rules.md` once per session for
   the boundary reminders, and the rest only as needed for the current task.
3. **Do not paste entire file contents back to the human in chat** when a summary will do. If the
   human needs to see full code, they can view the file directly in Antigravity's editor.
4. **Do not regenerate a whole file to make a small change.** Use targeted edits/diffs, not full
   rewrites, when modifying an existing file — full rewrites cost far more tokens and increase the
   risk of accidentally reverting unrelated work.
5. **Batch related questions.** If you need to ask the human 2-3 clarifying things, ask them together
   in one message rather than one at a time across multiple turns.
6. **Avoid speculative exploration.** Don't generate alternate implementations "just in case" one is
   preferred — pick the approach defined in `02_Architecture.md`, implement it, and only explore
   alternatives if explicitly asked or if the defined approach demonstrably fails.
7. **Summarize instead of narrate.** After completing a task, give a short structured summary (what
   changed, what to test) rather than a long narrative of the reasoning process.
8. **Flag context pressure early.** If you (the agent) sense that the current session has grown very
   long and old context may be getting dropped or confused, say so explicitly and suggest the human
   start a fresh session after you update `06_Memory.md` and `docs/progress.md` — don't let a
   degraded/confused response happen silently.
9. **No redundant test reruns.** Only re-run a diagnostic script for a component that actually
   changed, plus the full integration diagnostic at phase boundaries (per `07_Test.md`) — don't
   re-run every single component's test after every unrelated small change.
10. **Keep generated code lean.** Avoid generating large boilerplate, extensive inline comments
    explaining obvious code, or speculative "extensibility" scaffolding not required by the current
    phase — this consumes tokens without adding value for a 3-day build.

## 3. What This Is NOT Permission For

Token efficiency never overrides the rules in `03_Rules.md` — in particular, do not skip diagnostic
runs, do not skip audit logging, and do not skip stop-and-ask conditions to "save tokens." Efficiency
applies to HOW context and code are handled, never to skipping safety/quality/testing steps.
