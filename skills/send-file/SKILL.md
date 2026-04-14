---
name: airc:send-file
description: Send a file to a paired machine via AIRC.
user-invocable: true
allowed-tools: Bash
argument-hint: "<peer> <file-path>"
---

# Send a File via Relay

Run this yourself — don't ask the user to do it.

If `airc` is not on PATH, install it first:
```bash
curl -fsSL https://raw.githubusercontent.com/CambrianTech/airc/main/install.sh | bash
```

Parse the first word of `$ARGUMENTS` as the peer name, the rest as the file path:

```bash
airc send-file $ARGUMENTS
```

If no arguments, ask the user which peer and which file.
