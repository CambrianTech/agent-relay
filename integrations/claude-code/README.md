# Claude Code Integration

AIRC ships first-class skills for Claude Code — no manual hook wiring needed.

## Setup

Install (puts `airc` on PATH and installs the skills):

```bash
curl -fsSL https://raw.githubusercontent.com/CambrianTech/airc/main/install.sh | bash
```

Then in any Claude Code tab:

```
/connect                  # host — Claude prints the join string
/connect <join-string>    # join an existing host
```

The skill spawns `airc connect` under the Monitor tool, so inbound messages surface as notifications inside Claude Code automatically.

## Skills

| Skill | What it does |
|-------|-------------|
| `/connect [join]` | Host or join — pairs and starts streaming inbound |
| `/send <peer> <msg>` | Send (peer is required); mirror-first, `[SEND FAILED]` marker on wire failure |
| `/rename <new>` | Rename this identity, broadcasts `[rename]` to paired peers |
| `/send-file <peer> <path>` | Send a file via scp under the airc identity key |
| `/doctor [scenario]` | Run the integration suite (33 assertions) |
| `/teardown [--flush]` | Kill THIS scope's airc processes (and wipe state with --flush) |

## Manual Bash usage

If you'd rather drive the CLI directly:

```
Monitor(persistent=true, command="airc connect")
Bash("airc send peerName 'message here'")
```

## Scope isolation

Multiple Claude tabs can each run `/connect` in different `AIRC_HOME` dirs — `airc teardown` only kills its own scope's processes. Validated by `/doctor`.
