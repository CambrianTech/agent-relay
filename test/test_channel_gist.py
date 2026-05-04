"""channel_gist tests — convergence on duplicate gists.

Run: cd test && python3 test_channel_gist.py
"""

from __future__ import annotations

import sys
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

from airc_core import channel_gist  # noqa: E402


class FindExistingConvergenceTests(unittest.TestCase):
    """When two+ gists describe the same channel (host-takeover races,
    accidental dup creates), all peers must converge on ONE gist.
    Pre-fix find_existing returned whichever happened to appear first
    in gh's list-response, which is recency-ordered → different peers
    saw different "first" → substrate split silently.

    Convergence rule: oldest-by-created_at wins. Deterministic across
    every peer on the gh account regardless of when they polled."""

    def _gist(self, gid, channel, created_at, desc=None):
        return {
            "id": gid,
            "description": desc or f"airc room: #{channel} (post-3c per-channel gist)",
            "created_at": created_at,
            "files": {
                f"airc-room-{channel}.json": {
                    "content": '{"airc": 1, "kind": "mesh", "channels": ["%s"]}' % channel,
                    "truncated": False,
                },
            },
        }

    def test_returns_oldest_when_two_canonical_dups(self):
        """Two gists describe #general with identical canonical shape;
        find_existing must return the OLDEST regardless of list order."""
        # gh list-response is recency-ordered: NEWER first.
        listing = [
            self._gist("newer-id", "general", "2026-04-29T15:00:00Z"),
            self._gist("older-id", "general", "2026-04-29T07:00:00Z"),
        ]
        with mock.patch.object(channel_gist, "_gh_list_user_gists", return_value=listing):
            chosen = channel_gist.find_existing("general")
        self.assertEqual(chosen, "older-id",
                         "must converge on the OLDEST duplicate, not newest")

    def test_returns_oldest_across_three_dups(self):
        listing = [
            self._gist("middle", "general", "2026-04-29T10:00:00Z"),
            self._gist("newest", "general", "2026-04-29T15:00:00Z"),
            self._gist("oldest", "general", "2026-04-29T05:00:00Z"),
        ]
        with mock.patch.object(channel_gist, "_gh_list_user_gists", return_value=listing):
            chosen = channel_gist.find_existing("general")
        self.assertEqual(chosen, "oldest")

    def test_canonical_wins_over_legacy_even_when_legacy_is_older(self):
        """#290 contract preserved: canonical single-channel gists take
        priority over legacy multi-channel mesh gists. Even if the
        legacy mesh is OLDER, the canonical wins (oldest among
        canonicals). This tiebreak avoids re-introducing the split
        between [#general] and [a, b, c, general] gists."""
        legacy_old = {
            "id": "legacy-old",
            "description": "airc mesh",
            "created_at": "2026-04-29T01:00:00Z",
            "files": {
                "airc-room-mesh.json": {
                    "content": '{"airc": 1, "kind": "mesh", "channels": ["a", "b", "general"]}',
                    "truncated": False,
                },
            },
        }
        canonical_newer = self._gist("canonical-new", "general", "2026-04-29T08:00:00Z")
        with mock.patch.object(channel_gist, "_gh_list_user_gists",
                               return_value=[legacy_old, canonical_newer]):
            chosen = channel_gist.find_existing("general")
        self.assertEqual(chosen, "canonical-new",
                         "canonical (single-channel) priority overrides legacy oldest")

    def test_returns_none_when_no_match(self):
        with mock.patch.object(channel_gist, "_gh_list_user_gists", return_value=[]), \
             mock.patch.object(channel_gist, "_find_existing_via_local_cache", return_value=None):
            self.assertIsNone(channel_gist.find_existing("nonexistent"))

    def test_require_invite_skips_seed_only_channel_gist(self):
        """Connect discovery needs a host envelope, not just a routing
        seed. Seed-only channel gists are valid for cmd_send routing but
        cannot be joined because they have no invite/host data."""
        seed_only = self._gist("seed-only", "acme", "2026-05-04T17:27:38Z")
        host = self._gist("host", "acme", "2026-05-04T17:28:38Z")
        env = json.loads(host["files"]["airc-room-acme.json"]["content"])
        env["invite"] = "host@example"
        host["files"]["airc-room-acme.json"]["content"] = json.dumps(env)
        with mock.patch.object(channel_gist, "_gh_list_user_gists",
                               return_value=[seed_only, host]):
            self.assertEqual(channel_gist.find_existing("acme"), "seed-only")
            self.assertEqual(channel_gist.find_existing("acme", require_invite=True), "host")

    def test_returns_oldest_legacy_when_no_canonical(self):
        """If only legacy mesh gists exist (none canonical), still
        converge on oldest among them."""
        m_old = {
            "id": "mesh-old",
            "description": "airc mesh",
            "created_at": "2026-04-29T05:00:00Z",
            "files": {"airc-room-mesh.json": {
                "content": '{"airc":1,"kind":"mesh","channels":["a","general","c"]}',
                "truncated": False,
            }},
        }
        m_new = {
            "id": "mesh-new",
            "description": "airc mesh",
            "created_at": "2026-04-29T15:00:00Z",
            "files": {"airc-room-mesh.json": {
                "content": '{"airc":1,"kind":"mesh","channels":["general","x"]}',
                "truncated": False,
            }},
        }
        with mock.patch.object(channel_gist, "_gh_list_user_gists",
                               return_value=[m_new, m_old]):
            chosen = channel_gist.find_existing("general")
        self.assertEqual(chosen, "mesh-old")


class LocalCacheFallbackTests(unittest.TestCase):
    """REST listing failures must not force a new solo room.

    The fallback starts from locally remembered channel_gists, validates
    those ids through the gist git endpoint, then chooses the best
    recoverable room from wire evidence.
    """

    def _write_cfg(self, root: str, name: str, channel: str, gid: str) -> None:
        airc = Path(root) / name / ".airc"
        airc.mkdir(parents=True)
        (airc / "config.json").write_text(
            json.dumps({"channel_gists": {channel: gid}}),
            encoding="utf-8",
        )

    def _snapshot(self, gid: str, channel: str, channels: list[str], ts: str, desc: str | None = None) -> dict:
        return {
            "id": gid,
            "description": desc or f"airc room: #{channel} (git fallback)",
            "files": {
                f"airc-room-{channel}.json": {
                    "content": json.dumps({
                        "airc": 1,
                        "kind": "mesh",
                        "channels": channels,
                        "last_heartbeat": ts,
                    }),
                    "truncated": False,
                },
                "messages.jsonl": {
                    "content": json.dumps({"ts": ts, "from": "test", "msg": "marker"}) + "\n",
                    "truncated": False,
                },
            },
        }

    def test_rest_miss_uses_local_git_cache_and_rejects_newer_multi_channel_island(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = "aaaaaaaa"
            current = "bbbbbbbb"
            island = "cccccccc"
            self._write_cfg(tmp, "old-worktree", "general", stale)
            self._write_cfg(tmp, "current-worktree", "general", current)
            self._write_cfg(tmp, "solo-island", "general", island)
            snapshots = {
                stale: self._snapshot(stale, "general", ["general"], "2026-04-30T12:00:00Z"),
                current: self._snapshot(current, "general", ["general"], "2026-05-04T18:11:00Z"),
                island: self._snapshot(island, "general", ["general", "acme"], "2026-05-04T18:27:00Z"),
            }
            roots = os.pathsep.join([
                str(Path(tmp) / "old-worktree" / ".airc"),
                str(Path(tmp) / "current-worktree" / ".airc"),
                str(Path(tmp) / "solo-island" / ".airc"),
            ])
            with mock.patch.dict(os.environ, {"AIRC_GIST_CACHE_ROOTS": roots, "AIRC_DISABLE_LOCAL_GIST_FALLBACK": ""}), \
                 mock.patch.object(channel_gist, "_gh_list_user_gists", return_value=[]), \
                 mock.patch.object(channel_gist, "_git_gist_snapshot", side_effect=lambda gid: snapshots.get(gid)):
                self.assertEqual(channel_gist.find_existing("general"), current)

    def test_local_fallback_picks_recent_matching_multi_channel_when_no_strict_room_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = "dddddddd"
            current = "eeeeeeee"
            self._write_cfg(tmp, "old", "acme", old)
            self._write_cfg(tmp, "current", "acme", current)
            snapshots = {
                old: self._snapshot(old, "acme", ["acme", "general"], "2026-05-04T17:40:00Z"),
                current: self._snapshot(current, "acme", ["acme", "general"], "2026-05-04T18:22:49Z"),
            }
            roots = os.pathsep.join([
                str(Path(tmp) / "old" / ".airc"),
                str(Path(tmp) / "current" / ".airc"),
            ])
            with mock.patch.dict(os.environ, {"AIRC_GIST_CACHE_ROOTS": roots, "AIRC_DISABLE_LOCAL_GIST_FALLBACK": ""}), \
                 mock.patch.object(channel_gist, "_gh_list_user_gists", return_value=[]), \
                 mock.patch.object(channel_gist, "_git_gist_snapshot", side_effect=lambda gid: snapshots.get(gid)):
                self.assertEqual(channel_gist.find_existing("acme"), current)

    def test_default_local_fallback_only_reads_current_airc_home_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            broad = home / "Development" / "project" / ".airc"
            current = home / "current" / ".airc"
            broad.mkdir(parents=True)
            current.mkdir(parents=True)
            (broad / "config.json").write_text(
                json.dumps({"channel_gists": {"general": "broadscan"}}),
                encoding="utf-8",
            )
            current_gid = "cccccccc"
            (current / "config.json").write_text(
                json.dumps({"channel_gists": {"general": current_gid}}),
                encoding="utf-8",
            )
            old_home = os.environ.get("HOME")
            env = {"AIRC_HOME": str(current), "AIRC_DISABLE_LOCAL_GIST_FALLBACK": ""}
            with mock.patch.dict(os.environ, env, clear=False), \
                 mock.patch("os.path.expanduser", side_effect=lambda p: str(home) if p == "~" else p), \
                 mock.patch("os.walk", side_effect=AssertionError("local fallback must not crawl directories")), \
                 mock.patch.object(channel_gist, "_git_gist_snapshot", return_value=None) as snapshot:
                candidates = channel_gist._local_config_gist_candidates("general")
            if old_home is not None:
                os.environ["HOME"] = old_home
            self.assertEqual(candidates, [(current_gid, os.path.getmtime(current / "config.json"))])
            snapshot.assert_not_called()

    def test_explicit_local_fallback_roots_are_config_files_or_airc_dirs_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.airc"
            second = Path(tmp) / "second-config.json"
            first.mkdir()
            (first / "config.json").write_text(
                json.dumps({"channel_gists": {"general": "11111111"}}),
                encoding="utf-8",
            )
            second.write_text(
                json.dumps({"channel_gists": {"general": "22222222"}}),
                encoding="utf-8",
            )
            roots = os.pathsep.join([str(first), str(second)])
            with mock.patch.dict(os.environ, {"AIRC_GIST_CACHE_ROOTS": roots, "AIRC_HOME": ""}), \
                 mock.patch("os.walk", side_effect=AssertionError("local fallback must not crawl directories")):
                self.assertEqual(
                    sorted(channel_gist._local_config_gist_candidates("general")),
                    sorted([
                        ("11111111", os.path.getmtime(first / "config.json")),
                        ("22222222", os.path.getmtime(second)),
                    ]),
                )

    def test_resolve_does_not_create_new_gist_during_gh_backoff(self):
        with mock.patch.object(channel_gist, "find_existing", return_value=None), \
             mock.patch.object(channel_gist.gh_backoff, "backoff_active", return_value=True), \
             mock.patch.object(channel_gist, "create_new") as create_new:
            self.assertIsNone(channel_gist.resolve("general", create_if_missing=True))
            create_new.assert_not_called()

    def test_resolve_does_not_create_new_gist_after_untrusted_discovery(self):
        with mock.patch.object(channel_gist, "find_existing", return_value=None), \
             mock.patch.object(channel_gist.gh_backoff, "backoff_active", return_value=False), \
             mock.patch.object(channel_gist, "create_new") as create_new:
            channel_gist._LAST_GIST_LIST_UNAVAILABLE = True
            try:
                self.assertIsNone(channel_gist.resolve("general", create_if_missing=True))
                create_new.assert_not_called()
            finally:
                channel_gist._LAST_GIST_LIST_UNAVAILABLE = False

    def test_host_preflight_blocks_when_discovery_untrusted(self):
        with mock.patch.object(channel_gist, "find_existing", return_value=None), \
             mock.patch.object(channel_gist.gh_backoff, "backoff_active", return_value=False):
            channel_gist._LAST_GIST_LIST_UNAVAILABLE = True
            try:
                self.assertEqual(channel_gist.host_preflight("general"), ("blocked", None))
            finally:
                channel_gist._LAST_GIST_LIST_UNAVAILABLE = False

    def test_host_preflight_uses_current_config_before_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.json"
            cfg.write_text(
                json.dumps({"channel_gists": {"general": "abcdef1234567890"}}),
                encoding="utf-8",
            )
            with mock.patch.object(channel_gist, "find_existing") as find_existing:
                self.assertEqual(
                    channel_gist.host_preflight("general", config_path=str(cfg)),
                    ("existing", "abcdef1234567890"),
                )
                find_existing.assert_not_called()

    def test_host_preflight_allows_create_only_after_trusted_empty_discovery(self):
        with mock.patch.object(channel_gist, "find_existing", return_value=None), \
             mock.patch.object(channel_gist.gh_backoff, "backoff_active", return_value=False):
            channel_gist._LAST_GIST_LIST_UNAVAILABLE = False
            self.assertEqual(channel_gist.host_preflight("general"), ("create", None))

    def test_host_preflight_first_user_missing_config_can_create_after_trusted_empty_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_config = str(Path(tmp) / "new-user" / ".airc" / "config.json")
            with mock.patch.object(channel_gist, "find_existing", return_value=None), \
                 mock.patch.object(channel_gist.gh_backoff, "backoff_active", return_value=False):
                channel_gist._LAST_GIST_LIST_UNAVAILABLE = False
                self.assertEqual(
                    channel_gist.host_preflight("general", config_path=missing_config),
                    ("create", None),
                )


class GistListCacheTests(unittest.TestCase):
    """Gist discovery should not spam GitHub during monitor/status churn."""

    def _cache_path(self, tmp: str) -> Path:
        uid = str(os.getuid()) if hasattr(os, "getuid") else os.environ.get("USERNAME", "user")
        return Path(tmp) / f"airc-gh-gist-list-{uid}.json"

    def test_fresh_cache_avoids_gh_api_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            listing = [{"id": "cached", "description": "airc mesh", "files": {}}]
            cache = self._cache_path(tmp)
            cache.write_text(json.dumps(listing), encoding="utf-8")
            with mock.patch.object(tempfile, "gettempdir", return_value=tmp), \
                 mock.patch.dict(os.environ, {"AIRC_GIST_LIST_CACHE_SEC": "300"}), \
                 mock.patch.object(channel_gist, "_resolve_gh_bin", return_value="/bin/gh"), \
                 mock.patch.object(subprocess, "run") as run:
                self.assertEqual(channel_gist._gh_list_user_gists(), listing)
                run.assert_not_called()

    def test_live_success_refreshes_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            listing = [{"id": "live", "description": "airc room: #general", "files": {}}]
            completed = subprocess.CompletedProcess(
                args=["gh"], returncode=0, stdout=json.dumps(listing), stderr=""
            )
            with mock.patch.object(tempfile, "gettempdir", return_value=tmp), \
                 mock.patch.dict(os.environ, {"AIRC_GIST_LIST_CACHE_SEC": "0"}), \
                 mock.patch.object(channel_gist, "_resolve_gh_bin", return_value="/bin/gh"), \
                 mock.patch.object(subprocess, "run", return_value=completed):
                self.assertEqual(channel_gist._gh_list_user_gists(), listing)
            cache = self._cache_path(tmp)
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8")), listing)

    def test_rate_limited_live_probe_uses_stale_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            listing = [{"id": "stale-but-useful", "description": "airc mesh", "files": {}}]
            cache = self._cache_path(tmp)
            cache.write_text(json.dumps(listing), encoding="utf-8")
            old = 120
            os.utime(cache, (os.path.getatime(cache) - old, os.path.getmtime(cache) - old))
            completed = subprocess.CompletedProcess(
                args=["gh"], returncode=1, stdout="", stderr="secondary rate limit"
            )
            with mock.patch.object(tempfile, "gettempdir", return_value=tmp), \
                 mock.patch.dict(os.environ, {
                     "AIRC_GIST_LIST_CACHE_SEC": "0",
                     "AIRC_GIST_LIST_STALE_SEC": "900",
                 }), \
                 mock.patch.object(channel_gist, "_resolve_gh_bin", return_value="/bin/gh"), \
                 mock.patch.object(subprocess, "run", return_value=completed):
                self.assertEqual(channel_gist._gh_list_user_gists(), listing)


if __name__ == "__main__":
    unittest.main()
