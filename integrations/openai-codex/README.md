# OpenAI Codex CLI Integration

Adds AIRC peer messaging to Codex CLI sessions.

## Setup

Pair the machine first (host or join):

```bash
airc connect                  # host — prints a join string
airc connect <join-string>    # join an existing host
```

Then add to your project instructions so Codex knows the surface:

```
You are paired on AIRC. Send messages with:
  airc send <peer> "message"
List peers with `airc peers`. Recent activity with `airc logs 20`.
For a live tail of inbound messages, run `airc monitor` in a side terminal.
```

## Usage

Codex can run shell commands directly:

```bash
airc send peerName "message here"
airc logs 10
airc peers
```

For real-time inbound, run `airc monitor` in a background terminal — Codex sees the output in its context.
