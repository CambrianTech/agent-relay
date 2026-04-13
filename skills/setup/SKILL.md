---
name: relay:setup
description: Set up Agent Relay — initialize this machine and pair with another.
user-invocable: true
allowed-tools: Bash, Monitor
argument-hint: "<peer@user@host#key>"
---

# Set Up Agent Relay

Do everything yourself — don't ask the user to run commands.

## Step 1 (HOST ONLY): SSH is required for hosting

SSH is only needed if you're the host (no `@` in arguments). Skip this step if joining.

`relay connect` checks SSH automatically. If it fails, it prints exactly what command to run. You can't run sudo yourself — tell the user:

"SSH isn't working on this machine. Please type this in your terminal:" then show them the command from the error output. In Claude Code they can prefix with `!` to run it in the session, e.g.: `! sudo launchctl kickstart -k system/com.openssh.sshd`

After they run it, retry `relay connect`.

## Step 2: Install relay if needed

If `relay` is not on PATH:
```bash
curl -fsSL https://raw.githubusercontent.com/CambrianTech/agent-relay/main/install.sh | bash
```

## Step 3: Join or Start

**If `$ARGUMENTS` contains `@`** — you are joining a host:

Run the join. Pass the ENTIRE argument including the `#key` portion — that's the host's SSH public key:
```bash
relay join $ARGUMENTS
```

**IMMEDIATELY after join (even if there are warnings), start the monitor and send a test message. Do NOT skip this.**
```
Monitor(persistent=true, command="relay monitor")
```
```bash
relay send <peer> "connected"
```

If join failed with SSH errors, diagnose and fix:
- Is sshd running? `pgrep -x sshd`
- Is the host reachable? `nc -z <host-ip> 22`
- Are keys authorized? Check `~/.ssh/authorized_keys`
- Fix the issue and retry `relay join`.

**If no `@` in arguments** — you are the host:

```bash
relay start <name>
```

**IMMEDIATELY start the monitor:**
```
Monitor(persistent=true, command="relay monitor")
```

Show the join string from `relay start` output. Tell the user: "Give this to the other Claude:" followed by `/relay:setup <the join string>`
