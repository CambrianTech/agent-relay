"""Runtime client identity helpers.

An airc identity/nick belongs to a scope, not necessarily to one UI
session. Multiple Claude or Codex tabs can share one `.airc` directory
and one nick, so local self-filtering needs a per-agent runtime key.
"""

from __future__ import annotations

import os
import hashlib
import subprocess
import sys

from airc_core.humanhash import humanhash


def agent_process_client_id() -> str:
    """Return a stable-ish id for the owning Claude/Codex process."""

    pid = os.getpid()
    for _ in range(16):
        try:
            out = subprocess.check_output(
                ["ps", "-p", str(pid), "-o", "ppid=,command="],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            return ""
        if not out:
            return ""
        parts = out.split(None, 1)
        parent = parts[0] if parts else ""
        cmd = parts[1] if len(parts) > 1 else ""
        argv0 = cmd.split()[0] if cmd.split() else ""
        base = os.path.basename(argv0)
        if base in {"claude", "codex"} or "/codex/codex" in cmd:
            digest = hashlib.sha256(f"{pid}:{cmd}".encode("utf-8")).hexdigest()
            return f"agent:{humanhash(digest, 4)}"
        if not parent or parent == "1":
            return ""
        pid = int(parent)
    return ""


def current_client_id() -> str:
    if os.environ.get("AIRC_CLIENT_ID"):
        return os.environ["AIRC_CLIENT_ID"]
    if os.environ.get("CODEX_THREAD_ID"):
        return f"codex:{os.environ['CODEX_THREAD_ID']}"
    if os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return f"claude:{os.environ['CLAUDE_CODE_SESSION_ID']}"
    if os.environ.get("CLAUDE_SESSION_ID"):
        return f"claude:{os.environ['CLAUDE_SESSION_ID']}"
    return agent_process_client_id()


def main(argv: list[str] | None = None) -> int:
    del argv
    client_id = current_client_id()
    if not client_id:
        return 1
    print(client_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
