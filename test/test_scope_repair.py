"""Scope repair tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib"))

from airc_core import scope_repair  # noqa: E402


class ScopeRepairTests(unittest.TestCase):
    def test_repairs_missing_config_from_durable_scope_state(self):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            home = Path(tmp.name)
            (home / "identity").mkdir()
            (home / "identity" / "ssh_key.pub").write_text(
                "ssh-ed25519 AAAATEST airc-fallback\n",
                encoding="utf-8",
            )
            (home / "room_name").write_text("general\n", encoding="utf-8")
            (home / "room_gist_id").write_text("c68640ec0144b422c16b2d8c83ad5ee5\n", encoding="utf-8")
            (home / "host_gist_id").write_text("df40c8ae6c90f8e14009426fd6e16e22\n", encoding="utf-8")
            (home / "bearer_state.cambriantech.json").write_text("{}\n", encoding="utf-8")
            (home / "bearer_state.general.json").write_text("{}\n", encoding="utf-8")
            (home / "bearer_recv.cambriantech.log").write_text(
                "[airc:bearer_gh] _gh_api_get(df40c8ae6c90f8e14009426fd6e16e22): ok\n",
                encoding="utf-8",
            )
            (home / "bearer_recv.general.log").write_text(
                "[airc:bearer_gh] _gh_api_get(c68640ec0144b422c16b2d8c83ad5ee5): ok\n",
                encoding="utf-8",
            )
            (home / "messages.jsonl").write_text(
                json.dumps({"from": "airc-8a5e", "msg": "local"}) + "\n"
                + json.dumps({"from": "airc", "msg": "system"}) + "\n",
                encoding="utf-8",
            )

            config = home / "config.json"
            rc = scope_repair.main(
                [
                    "repair-config",
                    "--home",
                    str(home),
                    "--config",
                    str(config),
                    "--default-name",
                    "default-name",
                    "--host",
                    "127.0.0.1",
                ]
            )

            self.assertEqual(rc, 0)
            data = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(data["name"], "airc-8a5e")
            self.assertEqual(data["host"], "127.0.0.1")
            self.assertEqual(data["subscribed_channels"], ["cambriantech", "general"])
            self.assertEqual(
                data["channel_gists"],
                {
                    "cambriantech": "df40c8ae6c90f8e14009426fd6e16e22",
                    "general": "c68640ec0144b422c16b2d8c83ad5ee5",
                },
            )

    def test_empty_scope_is_not_marked_initialized(self):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            home = Path(tmp.name)
            config = home / "config.json"
            rc = scope_repair.main(["repair-config", "--home", str(home), "--config", str(config)])
            self.assertEqual(rc, 1)
            self.assertFalse(config.exists())

    def test_repairs_incomplete_existing_config(self):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            home = Path(tmp.name)
            config = home / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "name": "airc-8a5e",
                        "host": "127.0.0.1",
                        "created": "2026-05-05T00:00:00Z",
                        "subscribed_channels": ["general"],
                        "channel_gists": {"general": "91dfbe70f2358c7085e303e90016874c"},
                    }
                ),
                encoding="utf-8",
            )
            (home / "bearer_state.cambriantech.json").write_text("{}\n", encoding="utf-8")
            (home / "bearer_recv.cambriantech.log").write_text(
                "[airc:bearer_gh] _gh_api_get(df40c8ae6c90f8e14009426fd6e16e22): ok\n",
                encoding="utf-8",
            )
            rc = scope_repair.main(["repair-config", "--home", str(home), "--config", str(config)])
            self.assertEqual(rc, 0)
            data = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(data["subscribed_channels"], ["cambriantech", "general"])
            self.assertEqual(data["channel_gists"]["cambriantech"], "df40c8ae6c90f8e14009426fd6e16e22")


if __name__ == "__main__":
    unittest.main()
