# 10_Git_Discipline.md — Git & Commit Protocol

## STATUS: AUTHORITATIVE. The agent NEVER runs git commands. The agent always outputs the exact
## git command(s) for the human to run in their own terminal, and waits for confirmation before
## treating any change as "saved."

---

## 1. Why This Matters

Every meaningful change must be recoverable. If Antigravity breaks something while iterating, the
human must be able to `git log`, find the last good commit, and revert — without losing hours of
work. This is the actual purpose of frequent commits, not the raw count.

## 2. Commit Granularity Rule

**One logical change per commit — not one line per commit.** A high commit count is a natural
side-effect of disciplined small commits across a 3-day build with many files and phases, not a
target to hit by artificially splitting single changes. Example of correct granularity:
- ✅ `feat(adapters): add BaseLLMAdapter interface and MockAdapter`
- ✅ `test(adapters): add diagnostic script for mock and gemini adapters`
- ✅ `fix(pii-checker): correct regex for SSN pattern detection`
- ❌ `add import statement` (too granular, adds noise)
- ❌ `finish entire Phase 2` (too broad, loses recoverability if something in it breaks)

A reasonable target is one commit per completed task/sub-task in `04_Phases.md` — across ~10 phases
each with 3-6 tasks, plus test scripts, doc updates, and fixes, 1000+ commits is realistically
achievable over the full build without artificial padding, especially given the iterative nature of
an agent writing code interactively.

## 3. Commit Message Format

```
<type>(<scope>): <short description>

<optional longer body if the change needs explanation>
```

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `config`
Scope: the folder/component affected, e.g. `adapters`, `pii-checker`, `risk-engine`, `policy`,
`audit`, `dashboard`, `instructions`

## 4. Workflow the Agent Must Follow

1. After completing a discrete piece of work (one file's worth of logic, one diagnostic script, one
   config addition), the agent outputs:
   ```
   git add <specific files, never "git add ." blindly unless confirming .gitignore is correct>
   git commit -m "<type>(<scope>): <description>"
   ```
2. The human runs this in their terminal.
3. The agent does NOT proceed to assume the commit succeeded — if confirmation is needed, ask the
   human to paste `git log --oneline -5` output back.
4. Never suggest `git push --force` under any circumstance without an explicit, standalone request
   and explanation of consequences.
5. Before the very first commit, the agent must output the commands to verify `.gitignore` is
   working correctly (e.g., `git status` should NOT show `.env` as untracked-but-stageable in a
   dangerous way — confirm it's ignored).

## 5. Branching (kept simple given solo/small-team + time constraint)

- Work directly on `main` for the duration of the hackathon build unless the human explicitly wants
  a feature-branch workflow. Simplicity favors shipping over process overhead here.
- If 2-3 people join later (per `08_Folder_Structure.md` ownership split), THEN introduce
  per-person feature branches (`feature/adapters`, `feature/policy-engine`, etc.) merged via PRs —
  but this is a future-state instruction, not for the current solo sprint.

## 6. Recovery Instructions (keep this handy)

If something breaks and needs to be rolled back, the agent should output (for the human to run):
```
git log --oneline          # find the last known-good commit hash
git checkout <hash> -- <specific file>     # restore just one file, OR
git reset --hard <hash>                    # full rollback (destructive — confirm with human first)
```
Always prefer restoring a single file over a full hard reset when possible, to avoid losing
unrelated good work made after the bad change.

## 7. Repository Info

- GitHub username: `Sagnik120`
- Repo should be created as public (required by the problem statement submission format).
- Suggested repo name: `controlplane-ai` (or `controlplane-ai-round2` if `controlplane-ai` is taken).
