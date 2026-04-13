---
name: relay:monitor
description: Start monitoring for incoming relay messages from paired machines.
user-invocable: true
allowed-tools: Bash, Monitor
argument-hint: "[peer-name-filter]"
---

# Start Relay Monitor

Run this yourself — don't ask the user to do it.

If `relay` is not on PATH, install it first:
```bash
curl -fsSL https://raw.githubusercontent.com/CambrianTech/agent-relay/main/install.sh | bash
```

Start a persistent background monitor for incoming relay messages:

```
Monitor(persistent=true, command="relay monitor $ARGUMENTS")
```

This runs until the session ends. Each incoming message appears as an inline notification.
