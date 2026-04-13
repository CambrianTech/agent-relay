---
name: relay:send-file
description: Send a file to a paired machine via Agent Relay.
user-invocable: true
allowed-tools: Bash
argument-hint: "<peer> <file-path>"
---

# Send a File via Relay

Run this yourself — don't ask the user to do it.

If `relay` is not on PATH, install it first:
```bash
curl -fsSL https://raw.githubusercontent.com/CambrianTech/agent-relay/main/install.sh | bash
```

Parse the first word of `$ARGUMENTS` as the peer name, the rest as the file path:

```bash
relay send-file $ARGUMENTS
```

If no arguments, ask the user which peer and which file.
