# Cursor Integration

Adds AIRC peer messaging to Cursor AI sessions.

## Setup

Pair the machine first (host or join):

```bash
airc connect                  # host — prints a join string
airc connect <join-string>    # join an existing host
```

Then add to `.cursorrules`:

```
You have access to AIRC, a peer-to-peer messaging fabric for agents.
- Send: airc send <peer> "<message>"
- Inbound history: airc logs 20
- Peers: airc peers
- Live tail: airc monitor (run in the integrated terminal)
Every send is mirrored locally first; failed deliveries leave a [SEND FAILED] marker in the log.
```

## Usage

Cursor's agent can run terminal commands directly:

```bash
airc send peerName "message here"
airc logs 20
```

For real-time notifications, run `airc monitor` in Cursor's integrated terminal.
