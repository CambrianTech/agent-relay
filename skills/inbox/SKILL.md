---
name: airc:inbox
description: Show unread AIRC messages since this scope's last inbox check and advance the cursor. Use this for Codex/non-Monitor catch-up before acting.
user-invocable: true
allowed-tools: Bash
argument-hint: "[--peek] [--reset] [--since <ts|Ns|Nm|Nh>]"
---

# airc inbox

Run this yourself — don't ask the user.

## Execute

```bash
airc inbox                  # unread since last inbox check, then advance cursor
airc inbox --peek           # unread without advancing cursor
airc inbox --reset          # mark current time as read
airc inbox --since 5m       # override cursor for this check
```

`airc inbox` is the Codex/non-Monitor catch-up verb. It wraps `airc logs --since` with a per-scope cursor file, so future checks read only new messages instead of relying on the agent to remember and replay the last timestamp manually.

## When to use

- Before replying to the user about AIRC state.
- Before sending into AIRC from Codex or another non-Monitor runtime.
- After `airc join`, `airc resume`, `airc update`, or any long local task.
- Any time the user asks whether someone replied while Codex was working.

## Notes

- Alias: `airc poll`, `airc codex-poll`.
- Claude Code still gets push-like behavior from Monitor. Codex cannot receive UI interrupts, so this skill makes the polling cursor explicit and repeatable.
- `--peek` is useful for status checks where you do not want to mark messages read.
