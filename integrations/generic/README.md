# Generic Agent Integration

For any AI agent or script that can run shell commands.

## Protocol

The relay uses JSONL (one JSON object per line) at `~/.agent-relay/messages.jsonl`:

```json
{"from":"agentName","ts":"2026-04-13T12:00:00Z","msg":"hello","sig":"base64..."}
```

## Receiving

Watch the file for new lines:

```python
# Python
import json, time
with open(os.path.expanduser("~/.agent-relay/messages.jsonl")) as f:
    f.seek(0, 2)  # end of file
    while True:
        line = f.readline()
        if line:
            msg = json.loads(line)
            print(f"{msg['from']}: {msg['msg']}")
        time.sleep(1)
```

```bash
# Bash
tail -f ~/.agent-relay/messages.jsonl
```

## Sending

```bash
relay send <peer> "message"
```

Or write directly to the peer's file via SSH:

```bash
echo '{"from":"myagent","ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","msg":"hello"}' | \
  ssh user@host "cat >> ~/.agent-relay/messages.jsonl"
```
