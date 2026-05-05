"""Codex lifecycle hook adapter for airc.

Codex hooks run outside the model turn and can inject extra developer
context. This adapter converts the local airc inbox cursor into the
UserPromptSubmit JSON shape Codex documents, without touching GitHub.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass

from airc_core import inbox


INBOX_LINE_RE = re.compile(r"^\[(?P<ts>[^\]]+)\] (?P<sender>[^:]+): (?P<msg>.*)$")


@dataclass
class InboxMessage:
    ts: str
    sender: str
    msg: str


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


def _parse_inbox(text: str) -> list[InboxMessage]:
    messages = []
    for line in text.splitlines():
        match = INBOX_LINE_RE.match(line)
        if not match:
            continue
        messages.append(InboxMessage(ts=match.group("ts"), sender=match.group("sender"), msg=match.group("msg")))
    return messages


def _summarize_text(value: str, max_len: int = 120) -> str:
    one_line = " ".join(value.split())
    if len(one_line) <= max_len:
        return one_line
    return f"{one_line[: max_len - 3].rstrip()}..."


def _dedupe_messages(messages: list[InboxMessage]) -> list[InboxMessage]:
    seen = set()
    deduped: list[InboxMessage] = []
    for msg in messages:
        key = (msg.sender, msg.msg)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(msg)
    return deduped


def _digest(context: str, max_items: int = 8) -> str:
    messages = _dedupe_messages(_parse_inbox(context))
    if not messages:
        return context

    hidden = max(0, len(messages) - max_items)
    shown = messages[-max_items:]
    senders = []
    for msg in messages:
        if msg.sender not in senders:
            senders.append(msg.sender)

    lines = [
        f"AIRC: {len(messages)} unread"
        + (f" from {', '.join(senders[:3])}" if senders else "")
        + (f" +{len(senders) - 3}" if len(senders) > 3 else "")
    ]
    if hidden:
        lines.append(f"latest {len(shown)} shown; {hidden} older omitted")
    for msg in shown:
        lines.append(f"- {msg.sender}: {_summarize_text(msg.msg)}")
    if hidden:
        lines.append("more: airc inbox --peek --count 50")
    return "\n".join(lines)


def cmd_user_prompt_submit(args: argparse.Namespace) -> int:
    _read_stdin_json()
    context = _poll_context(args)
    if not context:
        return 0
    if not args.raw:
        context = _digest(context, max_items=args.max_items)
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
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
    user_prompt.add_argument("--max-items", type=int, default=8)
    user_prompt.add_argument("--raw", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "user-prompt-submit":
        return cmd_user_prompt_submit(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
