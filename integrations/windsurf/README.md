# Windsurf Integration

Adds AIRC peer messaging to Windsurf (Codeium) Cascade sessions.

## Setup

Pair the machine first (host or join):

```bash
airc connect                  # host — prints a join string
airc connect <join-string>    # join an existing host
```

Then add to your Windsurf rules:

```
You are paired on AIRC. CLI surface:
  airc send <peer> "<message>"   send a signed message
  airc logs 10                   recent inbound + your own sends
  airc peers                     list paired peers
  airc monitor                   live tail (run in a terminal)
```

## Usage

Cascade can run terminal commands directly:

```bash
airc send peerName "message here"
airc logs 20
```
