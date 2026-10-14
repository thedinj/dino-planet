---
name: devlog
description: Write a short devlog entry for Dino Planet describing what changed this session, saved under docs/devlog/. Use when the user asks for a devlog, a session write-up or a summary of recent changes.
argument-hint: "[extra notes or focus]"
disable-model-invocation: true
---

# /devlog

Write up this session's work for the owner, who reads it later to remember what happened
and why. Extra notes from the user: `$ARGUMENTS`.

## Gather

- This conversation: what was asked, what was built, decisions and their reasons, dead ends.
- `git log` since the last devlog entry (check the newest file in `docs/devlog/`; if there
  is none, use today's commits), plus `git status` / `git diff --stat` for uncommitted work.
- Test count from the latest `dotnet test` run, and any screenshots taken.

Describe only what actually happened. Don't fill gaps with guesses. If something wasn't
verified (no screenshot, tests not run), say so.

## Write

File: `docs/devlog/YYYY-MM-DD.md` (today's date). If it already exists, append a new
`## <short title>` section rather than overwriting.

```markdown
# YYYY-MM-DD

## <short title of the session's main change>

**What changed**
- One bullet per player-visible or architecture-level change, in plain words.
  Name the files or systems only when that helps (e.g. "new `Charge` behavior in Core").

**Why / decisions**
- The choices that weren't obvious, and the alternative that was rejected.

**Numbers touched**
- Tuning or asset values that changed, old → new (skip if none).

**State**
- Tests: N passing. Smoke/screenshot: checked / not checked.
- Uncommitted: yes/no.

**Next**
- Loose ends and good follow-ups, 1–4 bullets.
```

Keep it under about 40 lines. Leave out empty sections. Write for a hobbyist owner, not a
code reviewer: say what changed in the game first, then the code.

Afterwards show the path. Don't commit unless asked.
