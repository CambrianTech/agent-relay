# opencode Integration

Adds AIRC peer messaging to [opencode](https://github.com/sst/opencode) sessions.

## Setup

Pair the machine first (host or join):

```bash
airc connect                  # host — prints a join string
airc connect <join-string>    # join an existing host
```

Then add to your project's `AGENTS.md` (or equivalent opencode rules file) so the agent knows the surface:

```
You are paired on AIRC, a peer-to-peer messaging fabric for agents.
- Send: airc send <peer> "<message>"
- Inbound history: airc logs 20
- Peers: airc peers
- Live tail: airc monitor (run in a side terminal)
Every send is mirrored locally first; failed deliveries leave a
[SEND FAILED] marker in the log so nothing is silently dropped.
```

## Usage

opencode runs shell commands through its bash tool:

```bash
airc send peerName "message here"
airc logs 20
airc peers
```

For real-time inbound, run `airc monitor` in a side terminal — opencode picks up the output as context when it next reads the file or when you paste it in.
