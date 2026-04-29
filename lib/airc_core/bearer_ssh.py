"""SshBearer — message transport over SSH.

ALL SSH-specific knowledge lives in this module: ssh binary location, key
selection, host/port resolution, MSYS path handling on Windows, the
`__APPENDED__` confirmation protocol, error classification (auth vs
network), Tailscale-CGNAT offline-detection fast-path. Code outside this
file does not mention SSH or Tailscale.

If a future contributor needs to find "how does airc do SSH," the answer
is "open this file." If they need to add a new transport (gh, Reticulum,
LoRa, websocket, anything), they write a sibling file in the same shape
and register it in bearer_resolver.py. They never touch this one.

Phase 1 (current state): send() is functional. The cmd_send.sh SSH
delivery primitive — including the relay_ssh subprocess invocation, the
__APPENDED__ confirmation, the Tailscale-offline fast-path, and the
auth/network error classification — has been relocated here. cmd_send.sh
calls this module via bearer_cli.

Phase 2 (next): recv_stream() relocates the monitor's SSH-tail logic.
liveness() relocates the heartbeat read.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Iterator, Optional

from .bearer import (
    Bearer,
    BearerError,
    LivenessResult,
    SendOutcome,
    PeerUnreachable,
    ReceivedMessage,
)


class SshBearerError(BearerError):
    """SSH-transport-class errors. Distinct subclass for diagnostic clarity;
    callers branching on outcome kinds (SendOutcome.kind) should not
    isinstance-check this — the outcome contract is the API."""


# Tailscale CGNAT range (100.64.0.0/10): hosts whose IPs fall here come
# via Tailscale and the local `tailscale status` can tell us if they're
# offline before we waste a 10s SSH ConnectTimeout. Ranges 100.64–100.127.
_CGNAT_RE = re.compile(
    r"^100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\."
)

# Default SSH options — match the prior relay_ssh defaults exactly so
# behavior is preserved across the bash→Python relocation.
#   StrictHostKeyChecking=accept-new — TOFU on first contact, refuse on key change
#   ConnectTimeout=10                — fail fast on unreachable hosts
#   ServerAliveInterval=30           — keep long-lived monitor tails alive
_SSH_OPTS = [
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ConnectTimeout=10",
    "-o", "ServerAliveInterval=30",
]


def _resolve_ssh_bin() -> str:
    """Locate ssh on PATH. Inherits the user's environment so platform
    quirks (Git Bash on Windows, /usr/bin/ssh on macOS, etc.) resolve
    naturally. Raises SshBearerError if no ssh is found."""
    bin_path = shutil.which("ssh")
    if not bin_path:
        raise SshBearerError(
            "ssh binary not found on PATH; install OpenSSH or Git for Windows"
        )
    return bin_path


def _resolve_tailscale_bin() -> Optional[str]:
    """Locate tailscale CLI if installed. Returns None when absent —
    the offline fast-path simply doesn't engage. Tailscale is the ONE
    transport we still know about by name in this module; it's the SSH
    bearer's optimization for CGNAT hosts. After Phase 3 (Tailscale
    dropped), this function and the fast-path it gates can be deleted
    in a single edit."""
    return shutil.which("tailscale")


def _is_peer_offline_in_tailnet(host_target: str) -> bool:
    """Confirm the peer is reported offline by local tailscale status.

    Returns True ONLY when we have positive confirmation of offline
    state. Returns False for: online, unknown, non-CGNAT targets, or
    any error reading tailscale state. Never raises — uncertainty is
    "False" so the caller falls through to the normal SSH attempt.

    Mirrors the prior bash function (airc:510). Strips a leading
    `user@` from host_target before the CGNAT check (issue #78 root
    cause: resume paths fed in `user@host` and silently bypassed the
    gate)."""
    if not host_target:
        return False
    # Strip user@ prefix if present.
    host = host_target.split("@", 1)[-1]
    if not _CGNAT_RE.match(host):
        return False
    ts_bin = _resolve_tailscale_bin()
    if not ts_bin:
        return False
    try:
        result = subprocess.run(
            [ts_bin, "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    if result.returncode != 0:
        return False
    # tailscale status format: "<IP>  <hostname>  <owner>  <os>  <state...>"
    # Match target IP at column 1 + the literal word "offline" anywhere on
    # the same line.
    for line in result.stdout.splitlines():
        cols = line.split()
        if not cols:
            continue
        if cols[0] == host and "offline" in line:
            return True
    return False


def _classify_ssh_failure(stderr: str) -> tuple[str, str]:
    """Categorize an ssh failure based on its stderr.

    Returns (kind, detail) where kind is one of "auth_failure",
    "transient_failure". Auth failures are fatal-until-repair (user
    must re-pair); transient failures are retryable.

    The pre-existing bash code distinguished these via grep on stderr
    — this is the same distinction in Python. Keeping the strings
    literal so behavior is preserved.
    """
    auth_markers = [
        "Permission denied",
        "Authentication failed",
        "publickey",
    ]
    if any(m in stderr for m in auth_markers):
        return ("auth_failure", "host refused our SSH identity; re-pair required")
    return ("transient_failure", stderr.strip().splitlines()[-1] if stderr.strip() else "ssh failed")


def _build_ssh_argv(host_target: str, identity_key: Optional[str], remote_cmd: str) -> list[str]:
    """Construct the argv for a single ssh invocation. host_target is
    `user@host` or `user@host:port`. Identity key is optional — if
    provided we pass `-i`; otherwise ssh uses its default key search.

    Splits user@host:port into user@host plus a separate -p port
    argument (ssh's CLI doesn't accept :port in the host arg)."""
    ssh_bin = _resolve_ssh_bin()
    argv = [ssh_bin]
    if identity_key:
        argv += ["-i", identity_key]
    argv += list(_SSH_OPTS)
    # Split off port if present.
    target = host_target
    if ":" in target:
        target, port = target.rsplit(":", 1)
        argv += ["-p", port]
    argv.append(target)
    argv.append(remote_cmd)
    return argv


class SshBearer(Bearer):
    KIND = "ssh"

    @classmethod
    def can_serve(cls, peer_meta: dict) -> bool:
        """Return True if peer_meta describes an SSH-reachable peer.

        SSH reachability requires a `host_target` field (user@host[:port])
        populated by the pair-handshake. peer_meta is supplied by the
        caller; the disk-side identity-key check is lazy in send().
        """
        return bool(peer_meta.get("host_target"))

    def __init__(self, peer_meta: Optional[dict] = None) -> None:
        # No IO — concrete bearers MUST be cheap to instantiate.
        # peer_meta supplied by the resolver. Optional for unit-test
        # ergonomics (tests construct directly without a resolver).
        self._opened_peer_id: Optional[str] = None
        self._peer_meta: dict = peer_meta or {}
        self._closed = False
        self._proc = None  # active recv_stream Popen, if any
        self._last_recv_ts: Optional[float] = None

    def _check_alive(self) -> None:
        if self._closed:
            raise SshBearerError("bearer already closed")

    def open(self, peer_id: str) -> None:
        """Cache peer_id for subsequent send() calls. No actual SSH
        connection is established at open() — SSH is connectionless from
        the bearer's POV (each send is one ssh invocation). Per the ABC,
        open() may legitimately be a near-no-op for transports that don't
        need a persistent connection."""
        self._check_alive()
        self._opened_peer_id = peer_id

    def send(self, peer_id: str, channel: str, payload: bytes) -> SendOutcome:
        """Deliver `payload` to `peer_id` over SSH, append to the host's
        messages.jsonl, confirm via __APPENDED__ marker.

        Mirrors the cmd_send.sh:194-228 primitive precisely; behavior is
        preserved across the relocation. The Tailscale-offline fast-path
        engages first to skip predictable misses; on attempt, stderr is
        inspected to classify auth vs transient failures."""
        self._check_alive()

        host_target = self._peer_meta.get("host_target")
        if not host_target:
            raise SshBearerError(
                f"SshBearer.send called for peer_id={peer_id!r} with no "
                f"host_target in peer_meta — open() called with stale meta?"
            )
        remote_home = self._peer_meta.get("remote_home", "$HOME/.airc")
        identity_key = self._peer_meta.get("identity_key")

        # Fast-path: known-offline tailnet peer. Queue immediately; the
        # caller's monitor flush_pending_loop drains when the peer wakes.
        if _is_peer_offline_in_tailnet(host_target):
            return SendOutcome(
                kind="queued_unreachable",
                detail=f"peer offline in tailnet, auto-delivers on wake",
            )

        # Normal SSH attempt: append to remote messages.jsonl, confirm via
        # the __APPENDED__ marker. Trust the marker over ssh's exit code —
        # some shells bubble benign stderr warnings up as nonzero exit
        # even when the append succeeded.
        remote_cmd = f"cat >> {remote_home}/messages.jsonl && echo __APPENDED__"
        argv = _build_ssh_argv(host_target, identity_key, remote_cmd)

        # Payload is opaque bytes; the prior bash path used a trailing newline
        # via `printf '%s\n'`. Preserve that to keep messages.jsonl a strict
        # newline-delimited JSON file regardless of caller payload framing.
        stdin_bytes = payload if payload.endswith(b"\n") else payload + b"\n"

        try:
            result = subprocess.run(
                argv,
                input=stdin_bytes,
                capture_output=True,
                timeout=15,  # 10s connect + buffer for the cat append
            )
        except subprocess.TimeoutExpired:
            return SendOutcome(
                kind="transient_failure",
                detail="ssh timed out after 15s",
            )
        except OSError as e:
            return SendOutcome(
                kind="transient_failure",
                detail=f"ssh exec failed: {e}",
            )

        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")

        if "__APPENDED__" in stdout:
            return SendOutcome(kind="delivered", detail="")

        # Failure path: classify by stderr.
        kind, detail = _classify_ssh_failure(stderr)
        return SendOutcome(kind=kind, detail=detail)

    def recv_stream(self) -> Iterator[ReceivedMessage]:
        """Stream events from the host's messages.jsonl via SSH-tail.

        Internally manages: ssh subprocess lifecycle, line-buffered stdout
        parsing, JSON decoding, and reconnection on SSH death. Yields one
        ReceivedMessage per valid envelope on the wire. Malformed lines
        are dropped silently (the formatter has caught these for years
        — preserving that behavior). close() makes the generator return.

        Reconnection: SSH dies → wait briefly → reopen with the persisted
        line offset → resume yielding. The offset is updated as events
        flow so a reconnect mid-stream doesn't replay or skip. Watchdog,
        escalation counter, and any UX response to extended silence are
        CALLER concerns — the bearer's job is to keep producing events
        and update its own liveness signal so liveness() answers honestly.

        ABC contract reminder: callers must use line-buffered IO. SSH's
        stdout is unbuffered when tail is the underlying command, so this
        is naturally line-paced.
        """
        self._check_alive()

        host_target = self._peer_meta.get("host_target")
        if not host_target:
            raise SshBearerError(
                "SshBearer.recv_stream called with no host_target in peer_meta"
            )
        remote_home = self._peer_meta.get("remote_home", "$HOME/.airc")
        identity_key = self._peer_meta.get("identity_key")
        offset_file = self._peer_meta.get("offset_file")

        while not self._closed:
            tail_pos = self._compute_tail_position(offset_file)
            remote_cmd = f"tail {tail_pos} -F {remote_home}/messages.jsonl 2>/dev/null"
            argv = _build_ssh_argv(host_target, identity_key, remote_cmd)

            try:
                # Use BufferedReader (default bufsize) + explicit readline()
                # rather than iter(proc.stdout). bufsize=0 with text=False
                # gives a raw FileIO that doesn't yield lines on iteration;
                # bufsize=1 (line-buffered) is text-mode only and falls back
                # to 8KB buffering for bytes, delaying delivery by seconds.
                # readline() blocks until \n arrives — which is immediately
                # since ssh+tail flushes line-paced. Surfaced by
                # scenario_bearer_ssh_recv (Phase 2b prep).
                proc = subprocess.Popen(
                    argv,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=False,
                )
            except OSError:
                # Brief backoff so we don't hot-loop on a missing ssh binary
                # or similar permanent error. Caller's watchdog will notice
                # extended silence via liveness() and escalate.
                self._sleep_or_break(3.0)
                continue

            self._proc = proc
            try:
                assert proc.stdout is not None  # Popen kw guarantees this
                while not self._closed:
                    raw_line = proc.stdout.readline()
                    if not raw_line:  # EOF (ssh died)
                        break
                    self._on_line_received(raw_line, offset_file)
                    msg = self._parse_envelope(raw_line)
                    if msg is None:
                        continue
                    yield msg
            finally:
                self._reap_proc(proc)
                self._proc = None
            # SSH died — backoff briefly, then reconnect (unless closed).
            if not self._closed:
                self._sleep_or_break(3.0)

    @staticmethod
    def _compute_tail_position(offset_file: Optional[str]) -> str:
        """Decide tail's `-n` flag based on the persisted offset.

        Mirrors the bash monitor's logic verbatim:
          - empty / 0 / non-numeric → `-n 0` (start at EOF, no replay)
          - positive integer N → `-n +N+1` (resume past line N)

        Stale-offset detection (offset > host's current line count) is
        deliberately NOT done here — that's a one-shot probe the caller
        can run on first connect. Repeating it on every reconnect would
        burn an SSH round-trip we don't need; the steady-state offset is
        always sane because the formatter writes it monotonically.
        """
        if not offset_file:
            return "-n 0"
        try:
            with open(offset_file, "r") as f:
                raw = f.read().strip()
        except OSError:
            return "-n 0"
        if not raw or not raw.isdigit():
            return "-n 0"
        try:
            n = int(raw)
        except ValueError:
            return "-n 0"
        if n <= 0:
            return "-n 0"
        return f"-n +{n + 1}"

    def _on_line_received(self, raw_line: bytes, offset_file: Optional[str]) -> None:
        """Update bearer-internal state on each received line.

        - Bumps last_recv_ts so liveness() returns a fresh timestamp.
        - Persists the new offset (line count) so reconnect resumes
          past this line.
        Persistence failures are swallowed — the bearer continues
        streaming; a stale offset just means the next reconnect may
        replay a few lines, which the caller can dedupe."""
        import time as _time
        self._last_recv_ts = _time.time()
        if offset_file is None:
            return
        # Read-modify-write of the line count. Cheap because we're already
        # the only writer (the formatter's old-path writer is replaced by
        # this when monitor flips to recv_stream in Phase 2b).
        try:
            with open(offset_file, "r") as f:
                cur = f.read().strip()
            n = int(cur) if cur.isdigit() else 0
        except (OSError, ValueError):
            n = 0
        try:
            with open(offset_file, "w") as f:
                f.write(str(n + 1))
        except OSError:
            pass

    @staticmethod
    def _parse_envelope(raw_line: bytes) -> Optional[ReceivedMessage]:
        """Parse a single tail-stream line as a message envelope.

        Returns None on malformed input — silent drop matches the prior
        formatter behavior. Valid envelope = JSON object with at least
        `from` and `channel` fields. The full envelope (including sig)
        is preserved as the payload bytes so callers retain everything
        they had before this seam existed.
        """
        line = raw_line.rstrip(b"\n").rstrip(b"\r")
        if not line:
            return None
        import json as _json
        try:
            env = _json.loads(line)
        except (ValueError, TypeError):
            return None
        if not isinstance(env, dict):
            return None
        sender = env.get("from")
        channel = env.get("channel", "")
        if not sender:
            return None
        return ReceivedMessage(
            sender_peer_id=str(sender),
            channel=str(channel),
            payload=line,
            bearer_metadata={"envelope": env},
        )

    def _reap_proc(self, proc) -> None:
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1)
        except OSError:
            pass

    def _sleep_or_break(self, seconds: float) -> None:
        """Sleep `seconds` in small ticks so close() takes effect promptly.
        Returns immediately if the bearer was closed during the wait."""
        import time as _time
        deadline = _time.time() + seconds
        while not self._closed and _time.time() < deadline:
            _time.sleep(0.1)

    def liveness(self, peer_id: str) -> LivenessResult:
        """Report when this bearer last received an event from the peer.

        SshBearer's natural liveness signal is "stream activity" — we
        bump self._last_recv_ts on every line that comes through tail.
        None means "no signal yet" (recv_stream hasn't yielded), not
        "definitely dead." Caller's watchdog interprets staleness.

        This is the bearer-side of the airc-status / airc-peers
        observability fix from #270: instead of reading some external
        heartbeat file, the SSH-bearer attests directly to "the SSH
        stream produced an event N seconds ago."
        """
        self._check_alive()
        if self._last_recv_ts is None:
            return LivenessResult(
                peer_id=peer_id,
                last_seen_ts=None,
                bearer_diag="no events received via ssh tail yet",
            )
        return LivenessResult(
            peer_id=peer_id,
            last_seen_ts=self._last_recv_ts,
            bearer_diag="last event from ssh tail",
        )

    def close(self) -> None:
        # Idempotent per ABC contract. Tear down the recv_stream
        # subprocess if running so the generator returns promptly.
        self._closed = True
        proc = self._proc
        if proc is not None:
            self._reap_proc(proc)
            self._proc = None
        self._opened_peer_id = None
        self._peer_meta = {}
