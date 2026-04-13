# Cursor Integration

Adds relay messaging to Cursor AI sessions.

## Setup

After `relay start` and `relay join`, add to `.cursorrules`:

```
You have access to a peer-to-peer messaging relay. 
To send messages to other machines: relay send <peer> <message>
To check incoming messages: relay logs 10
To monitor in real-time: relay monitor (run in integrated terminal)
```

## Usage

Cursor's agent can run terminal commands:

```bash
# Send
relay send peerName "message here"

# Recent messages
relay logs 20
```

For real-time notifications, run `relay monitor` in Cursor's integrated terminal.
