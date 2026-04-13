# OpenAI Codex CLI Integration

Adds relay messaging to Codex CLI sessions.

## Setup

After `relay start` and `relay join`, add to your project instructions:

```
Monitor the relay for incoming messages by running: relay monitor
Send messages with: relay send <peer> <message>
```

## Usage

Codex can run shell commands directly:

```bash
# Send
relay send peerName "message here"

# Check recent messages
relay logs 10
```

For real-time monitoring, run `relay monitor` in a background terminal — Codex will see output in its context.
