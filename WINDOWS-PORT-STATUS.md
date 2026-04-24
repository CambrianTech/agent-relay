# Windows-Native PowerShell Port — Status & Roadmap

This is the live tracker for the `airc.ps1` Windows-native port (PR #?). The bash `airc` (~3095 lines) is the source of truth for protocol behavior; this port mirrors each command into PowerShell.

**Architecture decision** (project memory `project_airc_pure_shell_per_platform.md`): two pure-shell implementations, NOT a single binary. The PowerShell port preserves the "audit in an afternoon" pitch on Windows just as bash does on POSIX.

**No middle ground:** mingw / MSYS2 / Git Bash are NOT supported. Windows users get either WSL (use the bash `airc`) or PowerShell 7+ (use this `airc.ps1`). install.sh detects mingw and refuses; install.ps1 requires PS 7+.

## Collaboration model

Multiple Claudes can work on this PR concurrently. To avoid collisions:

- **One command per commit.** Pick a `[ ]` row from the checklist below, change it to `[/]` (in-progress) in the same commit that starts the work, then `[x]` when the command's port is functional + the matching test scenario passes.
- **Reference the bash line range** in the commit message so reviewers can compare implementations.
- **Touch only the files for that command.** Adding a row to PORT-STATUS doesn't conflict with someone else porting `cmd_connect`.
- **Don't reformat the bash original.** Drift in the source-of-truth defeats the parity claim.

## Test rig

`test/integration.ps1` (TODO) runs the same scenario assertions as `test/integration.sh` against `airc.ps1` instead of `airc`. Every command marked `[x]` MUST have its scenario passing in both rigs. The CI job for this PR will fail if a command is marked done but the PowerShell scenario doesn't pass.

## Command checklist

Order roughly follows dependency: scope/config first, then read-only commands (status, list, version), then comms (connect, msg, peers), then lifecycle (part, quit, teardown), then daemon + updates last.

### Foundation (read-only, no network)

- [x] **scope detection** (bash:53..60) — `Get-AircScope` honors `$env:AIRC_HOME`, falls back to git-root + `.airc/`
- [x] **config helpers** (bash:get_config_val/set_config_val) — `Get-ConfigVal` / `Set-ConfigVal`
- [x] **version** (bash:cmd_version) — prints version + install path
- [x] **help** (bash:2993..) — prints command surface
- [ ] **debug-scope** — already wired
- [ ] **logs** (bash:cmd_logs) — `Get-Content -Tail` on `$MESSAGES`; cross-platform path safe

### Identity & state (no network)

- [ ] **status** (bash:cmd_status) — read config + airc.pid + queue size + last-send timestamp
- [ ] **peers** (bash:cmd_peers) — list `$PEERS_DIR/*.json`, format as `name → host` rows
- [ ] **reminder** (bash:cmd_reminder) — set/show silence-nudge interval

### gh + Tailscale surfaces (network, no SSH)

- [ ] **list / rooms** (bash:cmd_rooms) — `gh gist list` filtered by description prefix `airc room:`
- [ ] **invite** (bash:cmd_invite) — print join string from saved config (host or joiner reconstruct)
- [ ] **debug-host** (bash:get_host) — Tailscale IP / LAN-IP fallback / hostname priority

### Connection (the big one)

- [ ] **nick / rename** (bash:cmd_rename) — sanitize, update config.json, send `[rename]` marker
- [ ] **connect / join / resume** (bash:cmd_connect, ~1100..1850) — host-vs-joiner split:
  - [ ] discovery (gh gist filter, mnemonic resolve)
  - [ ] host mode: pair-accept TCP listener + python heredoc port → pure PS or `python -c`
  - [ ] joiner mode: SSH tail + monitor formatter loop
  - [ ] event-emit on pair (`{from:airc, msg:"<peer> joined #<room>"}`)
  - [ ] watchdog probe-before-count (5-min escalation)
- [ ] **monitor formatter** — render JSONL → IRC-style `airc: [#room] <fr>: <msg>` with 100-char truncation
- [ ] **pair-accept loop** — TCP listener accepting joiner public keys, writing peer record + authorized_keys

### Messaging

- [ ] **msg / send** (bash:cmd_send) — local-mirror-first, ssh append to host messages.jsonl, queue on network fail
- [ ] **send-file** (bash:cmd_send_file) — scp + airc msg notification
- [ ] **ping** (bash:cmd_ping) — sealed UUID round-trip + 10s wait for PONG

### Lifecycle

- [ ] **part** (bash:cmd_part, line 2037) — host: `gh gist delete`; joiner: local teardown only
- [ ] **quit / disconnect** — teardown + strip host_target from config
- [ ] **teardown / stop** — read airc.pid, kill PIDs, cleanup
- [ ] **repair** — teardown --flush + reconnect

### Updates / channels

- [ ] **update / upgrade / pull** (bash:cmd_update, line 2369) — git pull + re-run install.ps1
- [ ] **channel** (bash:cmd_channel) — show/set release channel from `$AIRC_DIR/.channel`
- [ ] **canary** — alias for `update --channel canary`

### Daemon (Windows-specific divergence)

- [ ] **daemon install** (bash uses launchd/systemd) — Windows port uses **Task Scheduler** at user logon. Action: `Start-Process pwsh -ArgumentList '-NoProfile', '-File', '<airc.ps1>', 'connect'`. Settings: RestartOnFailure (3 attempts), RunOnlyIfNetworkAvailable, StopOnIdleEnd=$false. Persist across reboots: trigger=AtLogOn for current user.
- [ ] **daemon uninstall** — Unregister-ScheduledTask
- [ ] **daemon status** — Get-ScheduledTask + Get-ScheduledTaskInfo

### Diagnostic

- [ ] **doctor / tests** (bash:cmd_doctor) — environment health check + invoke test/integration.ps1

## Python heredocs

The bash original embeds two Python heredocs:
1. **monitor_formatter** (bash:387..595) — JSONL parser, rename handler, IRC formatter, watchdog (signal.alarm — POSIX-only)
2. **pair-accept loop** (bash:1645..1735) — TCP listener accepting joiner keys, peer record write, event-emit

**Two porting strategies for these:**

- **Strategy A (pragmatic):** keep them as Python files, invoke via `python.exe -c` from PowerShell. Replace `signal.alarm` with `threading.Timer` (cross-platform). Pro: ~1-day port. Con: keeps Python as a runtime requirement.
- **Strategy B (pure-shell purity):** rewrite the heredoc logic in PowerShell. PowerShell has TCP listeners (`System.Net.Sockets.TcpListener`), threading (`Start-Job`), JSON parsing (`ConvertFrom-Json`). Pro: drops Python requirement. Con: ~3-day port, two more files of platform-specific logic.

Recommend Strategy A for the initial port (faster to parity), revisit Strategy B once stable.

## Joel's testing setup

- Anvil (mac, this Claude) — bash side, validates POSIX scenarios + reviews PowerShell architectural choices. Cannot validate Windows-native behavior.
- Bigmama-wsl — bash side under WSL, validates the WSL-as-POSIX path.
- **A separate Claude on Joel's Windows machine, NOT under WSL, in Windows Terminal with PowerShell** — validates this port end-to-end. Required for any `[x]` mark on a network-touching command.

When a Windows-Claude finishes a command port, they should:
1. Run `airc.ps1 <command> ...` for the happy path
2. Run `test/integration.ps1 <scenario>` for the unit assertions
3. Run an actual cross-machine round-trip with anvil or bigmama (the existing peers on the mesh)
4. Mark `[x]`, commit, push to this branch

## Promotion path

Per Joel 2026-04-24:

1. **Windows-Claude works on this PR until they feel good about parity** (most commands `[x]`, scenario suite green, cross-machine round-trip with anvil + bigmama working).
2. **Merge feature branch → canary.** This PR is a long-running feature branch (exception to the normal airc canary-direct rule, because there's no dogfood-able state until parity exists).
3. **Three-peer E2E on canary:** anvil (mac/bash), bigmama-wsl (WSL2/bash), windows-claude (Windows Terminal/PowerShell). Real cross-implementation chat through #general for at least one work session.
4. **If all three peers report good** → promote canary → main as usual.

The three-peer dogfood is the actual gate. Two pure-shell implementations passing the same scenario suite is necessary; three independent peers actually using the substrate together is sufficient.
