# 03_Rules.md — Hard Rules and Boundaries for the AI Agent

## STATUS: AUTHORITATIVE. These rules override convenience or "best guess" behavior. If a rule
## conflicts with a request, the rule wins — STOP and ask the human instead of silently deciding.

---

## 1. Absolute Rules (never break these)

1. **NEVER execute shell commands yourself, including installs, git commands, server starts, or test
   runs.** You (the agent) must always output the exact command in a code block and ask the human to
   run it in their own terminal, then paste back the output for you to check. This applies to every
   phase, every file, every test. No exceptions, even for "trivial" commands like `mkdir` or `pip list`.
2. **NEVER read, print, log, or hardcode the contents of `.env`.** You may reference that a variable
   like `GEMINI_API_KEY` exists and must be loaded via `os.environ`, but you must never ask the human
   to paste key values into chat, and never write a real key into any file you generate.
3. **NEVER commit `.env`, `__pycache__/`, `node_modules/`, or any secrets to git.** Confirm
   `.gitignore` covers these before the first commit.
4. **NEVER silently change the architecture, tech stack, or folder structure** defined in
   `02_Architecture.md` and `08_Folder_Structure.md`. If you believe a change is necessary, stop and
   explain why, then wait for explicit approval.
5. **NEVER delete a file or overwrite a working component without explicit confirmation** from the
   human first, even if you believe it is broken. Propose the change, wait for a "yes."
6. **NEVER skip logging a decision to the audit log.** Every call through the Control Policy must
   produce an audit record, with no exceptions, including test runs.
7. **NEVER fabricate test results, benchmark numbers, or "it works" claims without the human having
   run the diagnostic script and confirmed the actual terminal output.** If you have not seen real
   output, say so explicitly rather than assuming success.

## 2. Stop-and-Ask Conditions (pause immediately, do not guess)

You must stop and explicitly ask the human before proceeding if:
- You are uncertain which of two reasonable implementations to choose and the choice affects more
  than one file.
- A requested change would touch more than 3 files at once.
- You encounter an error you cannot explain with high confidence after one attempt at diagnosis.
- You are about to introduce a new external dependency/library not already listed in
  `02_Architecture.md`.
- The task in the current phase (see `04_Phases.md`) appears already complete but something seems
  inconsistent with an earlier phase's output.
- Token usage for the current session is getting large and you are at risk of losing earlier context
  (see `11_Token_Efficiency.md`) — say so, and suggest updating `06_Memory.md` before continuing.

## 3. Library and Tooling Boundaries

- **Allowed**: FastAPI, uvicorn, pydantic, python-dotenv, PyYAML, pytest, google-generativeai,
  httpx/requests, standard library (json, asyncio, uuid, datetime, re).
- **Not allowed without asking first**: any ORM/database framework beyond sqlite3 standard library,
  any frontend framework beyond plain HTML/CSS/JS (React only if explicitly approved), any cloud
  service SDK (AWS/GCP/Azure infra), any paid API beyond the Gemini API already planned.
- **Never** silently swap a planned library for a "better" one you prefer. Propose it, explain why,
  wait for approval.

## 4. Error Handling Standards

- Every checker, adapter, and policy function must handle its own failure gracefully — a failing
  checker must not crash the whole request. If a checker errors out, it should return a result with
  `"error": true` and a neutral/conservative risk score (treat unknown as elevated risk, not zero
  risk), and this must be visible in the audit log.
- All API endpoints must return structured error responses (JSON with an `"error"` field), never a
  raw stack trace to the client.
- Any exception during development must be surfaced to the human in full (not summarized away) so
  they can decide whether it's a real bug or acceptable for the prototype's scope.

## 5. Code Quality Rules

- Every module must have a short docstring at the top explaining its single responsibility.
- Functions should do one thing. If a function is doing checker logic AND logging AND formatting,
  split it.
- No dead code / commented-out blocks left in committed files — clean before commit.
- Naming must match the terms used in `01_PRD.md` and `02_Architecture.md` exactly (e.g., always
  `risk_profile`, not `riskScores` in some files and `risk_profile` in others).

## 6. Communication Rules (how you talk to the human during the build)

- After completing each phase (see `04_Phases.md`), summarize in plain language: what was built, what
  was tested, what remains, and update `06_Memory.md` and `docs/progress.md` accordingly (see
  `09_Progress_Tracker.md`).
- Do not use hype language ("production-ready", "enterprise-grade", "fully robust") unless it has
  actually been tested and proven in this session. Describe what was verified, plainly.
- If you are about to make an assumption not covered by any instruction file, state the assumption
  out loud before proceeding, in one line, so the human can correct it immediately if wrong.
