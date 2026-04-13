---
name: relay:uninstall
description: Remove Agent Relay — unlinks skills, removes binary, cleans up.
user-invocable: true
allowed-tools: Bash
argument-hint: ""
---

# Uninstall Agent Relay

Run the uninstall script yourself:

```bash
~/.agent-relay-src/uninstall.sh
```

Then ask the user if they also want to remove data. Only delete after they confirm:
- `rm -rf ~/.agent-relay-src` — removes the source
- `rm -rf ~/.agent-relay` — removes keys, peers, and message history
