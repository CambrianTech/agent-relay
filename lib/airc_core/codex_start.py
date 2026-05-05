"""Codex process adapter for starting AIRC outside the tool process group.

Codex shell tool calls may clean up background children when the command
returns. A plain `nohup airc join &` can therefore look healthy for a few
seconds and then vanish. This module owns the runtime-specific detach detail
so the public skill can stay simple: `airc join`.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="airc_core.codex_start")
    parser.add_argument("--airc", required=True, help="Path to the airc executable")
    parser.add_argument("--home", required=True, help="AIRC_HOME/scope directory")
    parser.add_argument("--log", required=True, help="Log file for detached output")
    parser.add_argument("join_args", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    join_args = list(args.join_args)
    if join_args and join_args[0] == "--":
        join_args = join_args[1:]

    home = Path(args.home).expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)
    log_path = Path(args.log).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["AIRC_HOME"] = str(home)
    env["AIRC_CODEX_START_CHILD"] = "1"

    with open(os.devnull, "rb") as stdin, open(log_path, "ab", buffering=0) as out:
        proc = subprocess.Popen(
            [args.airc, "join", *join_args],
            stdin=stdin,
            stdout=out,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=os.getcwd(),
            close_fds=True,
            start_new_session=True,
        )

    print(f"airc join: launched Codex-detached transport for {home} (PID {proc.pid}, log {log_path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
