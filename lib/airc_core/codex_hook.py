"""Codex lifecycle hook adapter for airc.

Codex hooks run outside the model turn and can inject extra developer
context. This adapter converts the local airc inbox cursor into the
UserPromptSubmit JSON shape Codex documents, without touching GitHub.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from contextlib import redirect_stdout

from airc_core import inbox


def _read_stdin_json() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _poll_context(args: argparse.Namespace) -> str:
    out = io.StringIO()
    argv = [
        "read",
        "--home",
        args.home,
        "--cursor-file",
        args.cursor_file,
        "--count",
        str(args.count),
        "--quiet-empty",
        "--exclude-self",
        "--my-name",
        args.my_name,
        "--client-id",
        args.client_id,
    ]
    with redirect_stdout(out):
        inbox.main(argv)
    return out.getvalue().strip()


def cmd_user_prompt_submit(args: argparse.Namespace) -> int:
    _read_stdin_json()
    context = _poll_context(args)
    if not context:
        return 0
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                "Unread AIRC messages received before this user turn. "
                "Account for them before continuing:\n\n"
                f"{context}"
            ),
        }
    }
    print(json.dumps(payload, separators=(",", ":")))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="airc_core.codex_hook")
    sub = parser.add_subparsers(dest="cmd", required=True)
    user_prompt = sub.add_parser("user-prompt-submit")
    user_prompt.add_argument("--home", required=True)
    user_prompt.add_argument("--cursor-file", required=True)
    user_prompt.add_argument("--my-name", default="")
    user_prompt.add_argument("--client-id", default="")
    user_prompt.add_argument("--count", type=int, default=50)
    args = parser.parse_args(argv)
    if args.cmd == "user-prompt-submit":
        return cmd_user_prompt_submit(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
