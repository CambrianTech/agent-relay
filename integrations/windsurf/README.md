# Windsurf Integration

Adds relay messaging to Windsurf (Codeium) AI sessions.

## Setup

After `relay start` and `relay join`, add to your Windsurf rules:

```
Peer-to-peer messaging is available via the relay CLI.
Send: relay send <peer> <message>
Check messages: relay logs 10
Monitor: relay monitor (in terminal)
```

## Usage

Windsurf's Cascade agent can run terminal commands:

```bash
relay send peerName "message here"
relay logs 20
```
