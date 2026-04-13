# Claude Code Integration

Adds real-time relay messaging to Claude Code sessions.

## Setup

After `relay start` and `relay join`, add to your project's `CLAUDE.md`:

```
When starting a session, run: relay monitor
Use `relay send <peer> <message>` to message other machines.
```

Or add a hook in `.claude/settings.json`:

```json
{
  "hooks": {
    "session_start": ["relay monitor"]
  }
}
```

## Usage in Claude Code

```
# Monitor (persistent — notifies Claude on each incoming message)
Monitor(persistent=true, command="relay monitor")

# Send
Bash("relay send peerName 'message here'")
```
