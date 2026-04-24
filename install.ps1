# install.ps1 — Windows-native PowerShell installer for airc
#
# Mirrors install.sh for Windows. Both installers MUST agree on:
#   - Skill directory layout (~/.claude/skills/<name>/SKILL.md symlinks)
#   - Old-symlink cleanup list (so renames self-heal across updates)
#   - Channel persistence ($AIRC_DIR/.channel)
#
# Hard requirements (we fail loud if missing — per Joel's "loud failure
# beats silent slowness" rule):
#   - PowerShell 7+ (Core)
#   - git (for clone + update)
#   - gh CLI
#   - OpenSSH client (built into Windows 10+ as optional feature)
#   - Tailscale (Windows MSI installer)
#   - Python 3 (for the watchdog/formatter heredocs in airc.ps1, until
#     ported to pure PowerShell)
#
# NOT a requirement: WSL, mingw, Cygwin. This installer is for native
# Windows. The bash install.sh handles POSIX (incl. WSL) installs.

#Requires -Version 7.0
$ErrorActionPreference = 'Stop'

$CLONE_DIR     = if ($env:AIRC_DIR)     { $env:AIRC_DIR }     else { Join-Path $env:USERPROFILE '.airc-src' }
$BIN_TARGET    = if ($env:BIN_TARGET)   { $env:BIN_TARGET }   else { Join-Path $env:USERPROFILE 'AppData\Local\Programs\airc' }
$SKILLS_TARGET = if ($env:SKILLS_TARGET) { $env:SKILLS_TARGET } else { Join-Path $env:USERPROFILE '.claude\skills' }

function Test-Required {
    param([string]$Cmd, [string]$Hint)
    if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) {
        Write-Error "REQUIRED: $Cmd not found on PATH. $Hint"
        exit 1
    }
}

# ── Prereq audit ───────────────────────────────────────────────────────────

Test-Required 'git' 'Install Git for Windows: https://git-scm.com/download/win'
Test-Required 'gh'  'Install gh CLI: https://cli.github.com/ — then gh auth login'
Test-Required 'ssh' 'Install OpenSSH client: Settings → Apps → Optional Features → Add → OpenSSH Client'
Test-Required 'python' 'Install Python 3.10+: https://www.python.org/downloads/windows/ (or Microsoft Store)'

if (-not (Get-Command 'tailscale' -ErrorAction SilentlyContinue)) {
    Write-Warning 'Tailscale CLI not on PATH. Install from https://tailscale.com/download/windows. Continuing — airc will fail on connect if Tailscale is not running.'
}

# ── Clone or update ────────────────────────────────────────────────────────

if (Test-Path (Join-Path $CLONE_DIR '.git')) {
    Write-Host '  -> Updating existing install'
    # TODO: parallel to install.sh:27..90 — channel-aware fetch + ff-pull,
    # auto-recover from non-channel branches, surface ff failures with the
    # actionable recovery block.
    git -C $CLONE_DIR pull --ff-only --quiet
} else {
    Write-Host '  -> Installing AIRC'
    New-Item -ItemType Directory -Force -Path (Split-Path $CLONE_DIR) | Out-Null
    git clone --quiet https://github.com/CambrianTech/airc.git $CLONE_DIR
}

# ── Binary symlink: airc → airc.ps1 ────────────────────────────────────────
# Windows symlinks need either Developer Mode or admin. Fall back to a
# wrapper .cmd if symlink fails (TODO).

New-Item -ItemType Directory -Force -Path $BIN_TARGET | Out-Null
$aircLink = Join-Path $BIN_TARGET 'airc.ps1'
if (Test-Path $aircLink) { Remove-Item $aircLink -Force }
try {
    New-Item -ItemType SymbolicLink -Path $aircLink -Target (Join-Path $CLONE_DIR 'airc.ps1') | Out-Null
    Write-Host "  -> Linked airc.ps1 -> $CLONE_DIR\airc.ps1"
} catch {
    # Fall back to copy if symlink is denied
    Copy-Item (Join-Path $CLONE_DIR 'airc.ps1') $aircLink -Force
    Write-Warning "Symlink denied — fell back to copy. Re-run installer after each `git pull` to refresh."
}

# Add BIN_TARGET to PATH for current user if not already present
$userPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
if ($userPath -notlike "*$BIN_TARGET*") {
    [Environment]::SetEnvironmentVariable('PATH', "$userPath;$BIN_TARGET", 'User')
    Write-Host "  -> Added $BIN_TARGET to user PATH (open a new shell to pick up)"
}

# ── Skills ──────────────────────────────────────────────────────────────────
# Mirror install.sh:114..142. The cleanup list MUST stay in sync with the
# bash version — old skill names (connect/send/rename/disconnect from the
# IRC rename, etc.) get nuked here so renames self-heal across updates.

$skillsDir = Join-Path $CLONE_DIR 'skills'
if (Test-Path $skillsDir) {
    New-Item -ItemType Directory -Force -Path $SKILLS_TARGET | Out-Null

    $oldSkillNames = @('connect', 'send', 'rename', 'disconnect', 'monitor', 'setup', 'uninstall')
    foreach ($old in $oldSkillNames) {
        $oldPath = Join-Path $SKILLS_TARGET $old
        if (Test-Path $oldPath) { Remove-Item $oldPath -Force -Recurse -ErrorAction SilentlyContinue }
    }

    Get-ChildItem -Directory $skillsDir | ForEach-Object {
        $target = Join-Path $SKILLS_TARGET $_.Name
        if (Test-Path $target) { Remove-Item $target -Force -Recurse -ErrorAction SilentlyContinue }
        try {
            New-Item -ItemType SymbolicLink -Path $target -Target $_.FullName | Out-Null
        } catch {
            # Fall back to copy on systems without symlink permission
            Copy-Item -Recurse $_.FullName $target -Force
        }
        Write-Host "  -> Skill: /$($_.Name)"
    }
}

Write-Host ''
Write-Host '  -> Installed. Requires Tailscale: https://tailscale.com'
Write-Host ''
Write-Host '  airc join                       # auto-#general (joins existing or hosts)'
Write-Host '  airc msg @<peer> <message>      # DM a peer (or omit @peer to broadcast)'
