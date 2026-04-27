---
name: airc:whois
description: Look up identity (name, pronouns, role, bio, status, integrations) for self / host / paired peer / fellow joiner across all subscribed rooms. IRC /whois analog.
user-invocable: true
allowed-tools: Bash
argument-hint: "[<peer-name>]"
---

# /whois — Look up identity for a peer

Run this yourself — don't ask the user.

## Execute

```bash
airc whois <peer-name>
```

```bash
airc whois         # prints YOUR own identity (self)
```

Output is a structured block:

```
  name:      vhsm-d1f4
  pronouns:  they
  role:      vhsm-android-sdk
  bio:       wallet/merchant bridging cert flow on vhsm-canary
  status:    in a meeting til 3pm
  integrations: (none)
  host:      joelteply@100.91.51.87
```

## Resolution order (per scope)

For each subscribed scope (primary first, then sidecars):

1. **Self** — short-circuits, prints your own identity.
2. **Host** — when target name matches the scope's `host_name`, reads `host_identity` cached at handshake.
3. **Local peer file** — `<scope>/peers/<target>.json` if you've paired with the target directly.
4. **Cross-peer-via-host** — single SSH read of host's `peers/<target>.json` for fellow joiners in the same room.

If primary scope misses, sibling sidecar scopes are walked (issue #134) — so a peer who's only in your `#general` sidecar resolves cleanly from a project-scope cwd.

## When to use

- New peer joined the room → run `airc whois <them>` to load context (role, bio) before answering.
- Peer mentions someone you don't know → whois them.
- Triaging a coordination question — knowing pronouns/role lets the message be specific instead of generic.

## When the lookup will 404

- Target hasn't published identity yet (peer file exists but identity blob is empty → fields show `(unset)`).
- Target is in a room you're not subscribed to (no scope to walk).
- Target name is misspelled — names are lowercase alphanumeric + `-`.

The error message lists `airc peers` as a hint so the user can list valid names.

## Notes

- Whois is a one-shot command. Doesn't require a running monitor. Safe to call any time.
- Cross-scope walk runs at most one SSH per scope. Cheap.
- Identity is cached at pair-handshake time — no live propagation if the peer changes their `identity` mid-session. They re-pair (or you do) to refresh.
