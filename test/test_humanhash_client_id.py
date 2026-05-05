"""Mnemonic and runtime client id tests."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from airc_core.humanhash import humanhash  # noqa: E402
from airc_core import client_id  # noqa: E402


class HumanhashTests(unittest.TestCase):
    def test_known_mnemonic(self) -> None:
        self.assertEqual(
            humanhash("d7e247c0000000000000000000000000"),
            "potato-ack-ack-ack",
        )

    def test_odd_hex_is_accepted(self) -> None:
        self.assertEqual(humanhash("abc", 2), humanhash("0abc", 2))


class ClientIdTests(unittest.TestCase):
    def test_explicit_env_wins(self) -> None:
        with mock.patch.dict(os.environ, {"AIRC_CLIENT_ID": "explicit"}, clear=True):
            self.assertEqual(client_id.current_client_id(), "explicit")

    def test_agent_process_uses_humanhash_label_not_raw_pid(self) -> None:
        responses = {
            100: "200 python -m airc_core.client_id",
            200: "300 /bin/bash /path/to/airc msg hi",
            300: "1 /Users/example/.local/bin/claude --resume",
        }

        def fake_check_output(argv: list[str], **_: object) -> str:
            return responses[int(argv[2])]

        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("os.getpid", return_value=100),
            mock.patch("subprocess.check_output", side_effect=fake_check_output),
        ):
            value = client_id.current_client_id()

        self.assertRegex(value, r"^agent:[a-z]+-[a-z]+-[a-z]+-[a-z]+$")
        self.assertNotIn("300", value)


if __name__ == "__main__":
    unittest.main()
