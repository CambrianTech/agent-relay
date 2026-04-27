"""Pair-handshake response parsing for airc.

When a joiner connects to a host, the host returns a JSON envelope
with fields the joiner caches in its config (host's name, ssh_pub,
airc_home, reminder interval, identity blob). Pre-migration each
field-extract was an inline `python -c "import json; print(...)"`
heredoc; bash variable substitution into the python source was a
silent-fail vector (continuum-b69f's PR #164/#165 retest 2026-04-27
caught the host_airc_home write-side; this is the read-side).

Post-migration: response JSON comes via stdin, field name + default
via argv. Python source is fixed bytes; bash never touches it.

CLI:

    echo "$response" | python -m airc_core.handshake get_field <name> [default]

Empty stdout on parse failure (matches the bash `|| true` fallback
pattern). Exit always 0 — caller checks the value.
"""

from __future__ import annotations

import json
import sys


def parse_response(response_json: str) -> dict:
    """Parse a handshake-response JSON string. Returns {} on failure."""
    if not response_json:
        return {}
    try:
        obj = json.loads(response_json)
        return obj if isinstance(obj, dict) else {}
    except (ValueError, TypeError):
        return {}


def accept_one() -> int:
    """Host-side: bind a TCP listener, accept ONE incoming joiner,
    process its handshake payload, send response, log peer-joined
    event. Exits 0 on success, 0 on parent-death-timeout.

    Reads from env:
        HOST_PORT, PEERS_DIR, IDENTITY_DIR, CONFIG, HOST_NAME,
        REMINDER_INTERVAL, AIRC_WRITE_DIR, MESSAGES

    The outer bash `while true; do ... done &` loop calls this once
    per iteration; one accept per call. Parent-death detection
    (os.getppid() == 1) lets us self-exit cleanly when the airc
    bash dies between pairings — no orphan port-holder.

    Pre-migration this was a 125-line heredoc with EIGHT bash
    variable substitutions INTO the python source ($host_port,
    $PEERS_DIR, $(timestamp), $IDENTITY_DIR, $CONFIG, $name,
    $reminder_interval, $AIRC_WRITE_DIR, $MESSAGES). Each was a
    silent-fail class continuum traced today.
    """
    import datetime
    import os
    import socket as sock_mod

    host_port = int(os.environ.get("HOST_PORT", "7547"))
    peers_dir = os.path.expanduser(os.environ.get("PEERS_DIR", ""))
    identity_dir = os.path.expanduser(os.environ.get("IDENTITY_DIR", ""))
    config_path = os.environ.get("CONFIG", "")
    host_name = os.environ.get("HOST_NAME", "")
    reminder_interval = int(os.environ.get("REMINDER_INTERVAL", "300"))
    airc_write_dir = os.environ.get("AIRC_WRITE_DIR", "")
    messages_path = os.environ.get("MESSAGES", "")

    sock = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)
    sock.setsockopt(sock_mod.SOL_SOCKET, sock_mod.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", host_port))
    sock.listen(1)
    # Short accept timeout + parent-death check means if the outer bash
    # dies between pairings, this python exits cleanly on the next
    # timeout instead of orphaning and holding the port forever.
    sock.settimeout(10)
    while True:
        try:
            conn, _addr = sock.accept()
            break
        except sock_mod.timeout:
            if os.getppid() == 1:
                sock.close()
                return 0

    data = b""
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk
        if b"\n" in data:
            break

    joiner = json.loads(data.decode().strip())

    # Authorize joiner's SSH key.
    ssh_dir = os.path.expanduser("~/.ssh")
    os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
    ak = os.path.join(ssh_dir, "authorized_keys")
    ssh_key = joiner.get("ssh_pub", "")
    if ssh_key:
        existing = open(ak).read() if os.path.exists(ak) else ""
        if ssh_key not in existing:
            with open(ak, "a") as f:
                f.write(ssh_key.strip() + "\n")
            os.chmod(ak, 0o600)

    # Save joiner as peer — but first drop any existing records that share
    # this joiner's host (stable identity across renames). Otherwise a
    # rename chain leaves stale '<old-name>.json' alongside the new one.
    os.makedirs(peers_dir, exist_ok=True)
    jname = joiner["name"]
    jhost = joiner.get("host", "")
    if jhost and os.path.isdir(peers_dir):
        for entry in os.listdir(peers_dir):
            if not entry.endswith(".json"):
                continue
            if entry == jname + ".json":
                continue
            try:
                d = json.load(open(os.path.join(peers_dir, entry)))
            except Exception:
                continue
            if d.get("host") == jhost:
                # Same machine+user pairing under a different name — stale.
                for ext in (".json", ".pub"):
                    p = os.path.join(peers_dir, entry[:-5] + ext)
                    if os.path.isfile(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass

    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(peers_dir, jname + ".json"), "w") as f:
        json.dump({
            "name": jname,
            "host": joiner.get("host", ""),
            "airc_home": joiner.get("airc_home", ""),
            "paired": timestamp,
            # Cache joiner's SSH pubkey so airc kick can remove it from
            # authorized_keys later. Without this, kick has no way to find
            # the right line in authorized_keys and the kicked peer keeps
            # SSH access — Copilot caught this on PR #73 review.
            "ssh_pub": joiner.get("ssh_pub", ""),
            # Cache joiner's identity blob (issue #34 v2). Empty on legacy
            # peers that don't send the field — airc whois prints the
            # 'not exchanged yet' fallback gracefully.
            "identity": joiner.get("identity", {}),
        }, f, indent=2)
    if joiner.get("sign_pub"):
        with open(os.path.join(peers_dir, jname + ".pub"), "w") as f:
            f.write(joiner["sign_pub"])

    # Send back host's SSH pubkey + airc_home + own identity blob (issue
    # #34 v2). Joiner caches under host_identity so 'airc whois
    # <host-name>' works locally without a round-trip.
    host_pub = open(os.path.join(identity_dir, "ssh_key.pub")).read().strip()
    host_identity = {}
    try:
        host_config = json.load(open(config_path))
        host_identity = host_config.get("identity", {}) or {}
    except Exception:
        pass
    response = json.dumps({
        "ssh_pub": host_pub,
        "name": host_name,
        "reminder": reminder_interval,
        "airc_home": airc_write_dir,
        "identity": host_identity,
    })
    conn.sendall((response + "\n").encode())
    conn.close()
    sock.close()

    print(f"  Peer joined: {jname}")
    # Surface the join as a system event in messages.jsonl so the monitor
    # formatter (and downstream Monitor task summaries on every paired peer)
    # render a one-liner like '[#general] airc: <peer> joined' instead of
    # silence. Without this, peer-joined is invisible to anyone reading
    # notifications — they only learn about the new peer when chat traffic
    # starts flowing.
    try:
        room_name_path = os.path.join(airc_write_dir, "room_name")
        room_name = open(room_name_path).read().strip() if os.path.isfile(room_name_path) else "general"
        event = {
            "ts": timestamp,
            "from": "airc",
            "to": "all",
            "msg": f"{jname} joined #{room_name}",
        }
        with open(messages_path, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        # Don't fail the pair on event-emit error — pairing already
        # succeeded; missing event line is cosmetic.
        pass
    return 0


def send(host: str, port: int) -> str:
    """Joiner-side: build payload from env vars, connect to host:port,
    send, read response, return as string. Caller checks for empty
    string on failure.

    Env vars:
        MY_NAME, MY_HOST, MY_SSH_PUB, MY_SIGN_PUB, MY_AIRC_HOME,
        MY_IDENTITY (JSON string of identity dict)

    Pre-migration this was an inline `python -c "..."` heredoc with
    five bash-variable substitutions INTO the python source. Any
    special character in any field (apostrophe in bio, embedded
    newline in ssh_pub) silently broke parsing. Now: env vars + argv.
    """
    import os
    import socket as sock_mod

    payload = json.dumps({
        "name": os.environ.get("MY_NAME", ""),
        "host": os.environ.get("MY_HOST", ""),
        "ssh_pub": os.environ.get("MY_SSH_PUB", ""),
        "sign_pub": os.environ.get("MY_SIGN_PUB", ""),
        "airc_home": os.environ.get("MY_AIRC_HOME", ""),
        "identity": json.loads(os.environ.get("MY_IDENTITY", "{}") or "{}"),
    })

    s = sock_mod.socket(sock_mod.AF_INET, sock_mod.SOCK_STREAM)
    s.settimeout(30)
    s.connect((host, int(port)))
    s.sendall((payload + "\n").encode())
    s.shutdown(sock_mod.SHUT_WR)
    data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        data += chunk
    s.close()
    return data.decode().strip()


def _cli() -> int:
    if len(sys.argv) < 2:
        return 2
    cmd = sys.argv[1]
    if cmd == "get_field":
        if len(sys.argv) < 3:
            return 2
        field = sys.argv[2]
        default = sys.argv[3] if len(sys.argv) > 3 else ""
        try:
            response = sys.stdin.read()
        except Exception:
            print(default)
            return 0
        obj = parse_response(response)
        v = obj.get(field, default)
        # Numbers (e.g. reminder=300) round-trip cleanly through str();
        # nested objects (e.g. identity={}) need json.dumps so callers
        # get a parseable string back rather than Python repr.
        if isinstance(v, (dict, list)):
            print(json.dumps(v))
        else:
            print(v if v != "" else default)
        return 0
    if cmd == "send":
        if len(sys.argv) < 4:
            return 2
        host = sys.argv[2]
        port = sys.argv[3]
        try:
            print(send(host, port))
            return 0
        except Exception as e:
            # Stderr surfaces; bash's `2>&1` capture lets cmd_connect's
            # die() print the actual error per the never-swallow-errors
            # rule.
            print(f"airc-handshake-send-error: {e}", file=sys.stderr)
            return 1
    if cmd == "accept_one":
        try:
            return accept_one()
        except Exception as e:
            print(f"airc-handshake-accept-error: {e}", file=sys.stderr)
            return 1
    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
