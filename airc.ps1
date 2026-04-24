#!/usr/bin/env pwsh
# airc.ps1 — Windows-native PowerShell port of `airc` (the bash original)
#
# Architecture (see project memory project_airc_pure_shell_per_platform.md):
#   - Two pure-shell implementations of the same protocol:
#     - `airc` (bash + inline Python heredocs) — POSIX (macOS, Linux, WSL)
#     - `airc.ps1` (PowerShell)                 — Windows native
#   - Skills (slash commands) are platform-blind. They invoke the verb;
#     the install layer ensures the right binary is on PATH.
#   - Drift mitigation: tests/integration.ps1 (parallel to test/integration.sh)
#     runs the same scenario suite against this implementation.
#
# Hard requirements on Windows:
#   - PowerShell 7+ (Core). Windows PowerShell 5.1 lacks several features
#     this script uses (ternary, null-coalesce, modern threading).
#   - OpenSSH client + ssh-keygen + ssh-agent (built into Windows 10+).
#   - gh CLI (https://cli.github.com/) authenticated with gist scope.
#   - Tailscale Windows client (https://tailscale.com/download/windows).
#   - Python 3 for the watchdog/formatter heredocs (until ported to pure PS).
#
# NOT supported (deliberately, per Joel 2026-04-24):
#   - mingw / MSYS2 / Git Bash on Windows. Use the bash `airc` under WSL,
#     or this airc.ps1 from PowerShell. No third path.
#
# Reference: every command stub below carries (bash:LINE) pointing at the
# corresponding implementation in the bash original. Use that for parity
# checks when porting each command.

#Requires -Version 7.0

$ErrorActionPreference = 'Stop'

# ── Constants & scope detection (bash:1-100) ───────────────────────────────

$AIRC_VERSION = '0.0.1-windows-port'

function Get-AircScope {
    # Parallel to bash detect_scope(). If we're inside a git repo,
    # identity lives at <repo-root>/.airc/; otherwise $env:USERPROFILE/.airc/.
    # Honors $env:AIRC_HOME override (used by tests + isolated scopes).
    if ($env:AIRC_HOME) { return $env:AIRC_HOME }
    try {
        $gitRoot = git rev-parse --show-toplevel 2>$null
        if ($LASTEXITCODE -eq 0 -and $gitRoot) {
            return (Join-Path $gitRoot '.airc')
        }
    } catch { }
    return (Join-Path $env:USERPROFILE '.airc')
}

$AIRC_WRITE_DIR = Get-AircScope
$CONFIG       = Join-Path $AIRC_WRITE_DIR 'config.json'
$IDENTITY_DIR = Join-Path $AIRC_WRITE_DIR 'identity'
$PEERS_DIR    = Join-Path $AIRC_WRITE_DIR 'peers'
$MESSAGES     = Join-Path $AIRC_WRITE_DIR 'messages.jsonl'

# ── Config helpers (bash:get_config_val / set_config_val) ──────────────────

function Get-ConfigVal {
    param([string]$Key, [string]$Default = '')
    if (-not (Test-Path $CONFIG)) { return $Default }
    try {
        $cfg = Get-Content $CONFIG -Raw | ConvertFrom-Json -AsHashtable
        if ($cfg.ContainsKey($Key)) { return $cfg[$Key] }
    } catch { }
    return $Default
}

function Set-ConfigVal {
    param([string]$Key, [string]$Value)
    $cfg = @{}
    if (Test-Path $CONFIG) {
        try { $cfg = Get-Content $CONFIG -Raw | ConvertFrom-Json -AsHashtable } catch { $cfg = @{} }
    }
    $cfg[$Key] = $Value
    $cfg | ConvertTo-Json -Depth 10 | Set-Content -Path $CONFIG -NoNewline
}

# ── Stub: cmd_version (bash:2942 cmd_version) ──────────────────────────────

function Invoke-Version {
    Write-Host "  airc.ps1 $AIRC_VERSION on PowerShell $($PSVersionTable.PSVersion)"
    Write-Host "  install: $PSScriptRoot"
}

# ── Stub: cmd_help (bash:2993) ─────────────────────────────────────────────

function Invoke-Help {
    @"
AIRC — Agentic Internet Relay Chat for AI peers
(Windows-native PowerShell port; see also: airc bash for POSIX)

Common verbs:
  airc join                       # auto-#general (joins existing or hosts)
  airc msg @<peer> <message>      # DM a peer (or omit @peer to broadcast)
  airc peers                      # list paired peers
  airc list                       # list open rooms on your gh account
  airc nick <new-name>            # rename, broadcast to peers
  airc part                       # leave the current room
  airc quit                       # leave the mesh entirely

PORT STATUS: see WINDOWS-PORT-STATUS.md for which commands are wired
yet. This is a draft port; most commands are still stubs.
"@ | Write-Host
}

# ── Command dispatch (bash:2967 case "${1:-help}" in) ──────────────────────

$cmd = if ($args.Count -gt 0) { $args[0] } else { 'help' }
$rest = if ($args.Count -gt 1) { $args[1..($args.Count-1)] } else { @() }

switch ($cmd) {
    # ── Info / help ──
    'version' { Invoke-Version; break }
    '--version' { Invoke-Version; break }
    '-v' { Invoke-Version; break }
    'help' { Invoke-Help; break }
    '--help' { Invoke-Help; break }
    '-h' { Invoke-Help; break }

    # ── Connection lifecycle (TODO) ──
    'connect' { Write-Error 'TODO: cmd_connect (bash:1100..1850) — host vs joiner branching, gh discovery, pair handshake, monitor formatter loop'; exit 99 }
    'join'    { Write-Error 'TODO: alias of connect'; exit 99 }
    'resume'  { Write-Error 'TODO: alias of connect (bash:resume)'; exit 99 }

    # ── Messaging (TODO) ──
    'msg'     { Write-Error 'TODO: cmd_send (bash:1800..1900) — local-mirror-first, ssh append to host messages.jsonl, queue on network fail'; exit 99 }
    'send'    { Write-Error 'TODO: alias of msg'; exit 99 }

    # ── Identity (TODO) ──
    'nick'    { Write-Error 'TODO: cmd_rename — sanitize name, update config.json, broadcast [rename] marker'; exit 99 }
    'rename'  { Write-Error 'TODO: alias of nick'; exit 99 }
    'peers'   { Write-Error 'TODO: cmd_peers — list peer JSON files'; exit 99 }

    # ── Room / discovery (TODO) ──
    'list'    { Write-Error 'TODO: cmd_rooms (bash:cmd_rooms) — gh gist list filter by description'; exit 99 }
    'rooms'   { Write-Error 'TODO: alias of list'; exit 99 }
    'invite'  { Write-Error 'TODO: cmd_invite — print join string'; exit 99 }
    'part'    { Write-Error 'TODO: cmd_part (bash:2037) — host: gh gist delete; joiner: local teardown only'; exit 99 }

    # ── Lifecycle / disconnect (TODO) ──
    'quit'    { Write-Error 'TODO: cmd_disconnect — teardown + strip host_target from config'; exit 99 }
    'disconnect' { Write-Error 'TODO: alias of quit'; exit 99 }
    'teardown' { Write-Error 'TODO: cmd_teardown — read airc.pid, kill PIDs, cleanup'; exit 99 }
    'stop'    { Write-Error 'TODO: alias of teardown'; exit 99 }

    # ── Diagnostic / utility (TODO) ──
    'logs'    { Write-Error 'TODO: cmd_logs — tail messages.jsonl'; exit 99 }
    'status'  { Write-Error 'TODO: cmd_status — identity + monitor PID + queue size'; exit 99 }
    'doctor'  { Write-Error 'TODO: cmd_doctor — environment health + integration suite'; exit 99 }
    'tests'   { Write-Error 'TODO: alias of doctor (test path only)'; exit 99 }
    'ping'    { Write-Error 'TODO: cmd_ping (bash:cmd_ping) — round-trip liveness probe'; exit 99 }
    'reminder' { Write-Error 'TODO: cmd_reminder — silence-nudge interval'; exit 99 }
    'send-file' { Write-Error 'TODO: cmd_send_file — scp + airc msg notification'; exit 99 }
    'repair'  { Write-Error 'TODO: cmd_repair — teardown --flush + reconnect'; exit 99 }

    # ── Updates / channels (TODO) ──
    'update'  { Write-Error 'TODO: cmd_update — git pull + re-run install.ps1'; exit 99 }
    'upgrade' { Write-Error 'TODO: alias of update'; exit 99 }
    'pull'    { Write-Error 'TODO: alias of update'; exit 99 }
    'channel' { Write-Error 'TODO: cmd_channel — show/set release channel'; exit 99 }
    'canary'  { Write-Error 'TODO: cmd_update --channel canary'; exit 99 }

    # ── Daemon (TODO — Windows-specific: Task Scheduler not launchd/systemd) ──
    'daemon'  { Write-Error 'TODO: cmd_daemon Windows port — register Task Scheduler task at logon (Action: Start pwsh.exe with -File airc.ps1 connect; Settings: RestartOnFailure, RunOnlyIfNetworkAvailable)'; exit 99 }

    # ── Debug ──
    'debug-scope' { Write-Host $AIRC_WRITE_DIR; break }

    default {
        Write-Error "Unknown command: $cmd. Try: airc help"
        exit 2
    }
}
