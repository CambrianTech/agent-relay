---
name: relay:setup
description: Set up Agent Relay — initialize this machine and pair with another.
user-invocable: true
allowed-tools: Bash, Monitor
argument-hint: "<peer@user@host#key>"
---

# Set Up Agent Relay

Do everything yourself — don't ask the user to run commands.

## Step 1: Ensure SSH is working on THIS machine

```bash
nc -z localhost 22 && echo "SSH OK" || echo "SSH NOT RUNNING"
```
If not running:
- macOS: try `sudo systemsetup -setremotelogin on`. If that fails, open settings for the user: `open "x-apple.systempreferences:com.apple.Sharing-Settings.extension"` and tell them to enable **Remote Login**. Wait until `nc -z localhost 22` succeeds.
- Linux: `sudo systemctl start sshd` or `sudo service ssh start`

**Ghost listener bug (macOS):** if port 22 is open but `ssh localhost "echo ok"` fails with "connection reset," sshd is dead. Try these in order until one works:
```bash
sudo launchctl kickstart -k system/com.openssh.sshd
sudo launchctl bootout system/com.openssh.sshd && sudo launchctl bootstrap system /System/Library/LaunchDaemons/ssh.plist
sudo launchctl unload /System/Library/LaunchDaemons/ssh.plist && sudo launchctl load -w /System/Library/LaunchDaemons/ssh.plist
sudo /usr/sbin/sshd
```
After each, test with `ssh localhost "echo ok"`. If none work and you don't have sudo, open settings: `open "x-apple.systempreferences:com.apple.Sharing-Settings.extension"` and tell the user to toggle Remote Login OFF, wait 3 seconds, then ON.

Do NOT proceed until `ssh localhost "echo ok"` actually succeeds.

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
