---
name: relay:update
description: Update Agent Relay to the latest version from GitHub.
user-invocable: true
allowed-tools: Bash
argument-hint: ""
---

# Update Agent Relay

Run these commands yourself — don't ask the user to do it.

```bash
cd ~/.agent-relay-src && git pull --ff-only && ./install.sh
```

Then report what changed by running `git -C ~/.agent-relay-src log --oneline -5`.
