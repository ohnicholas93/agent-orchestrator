from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from orchestrator import (
    CONTINUE_INSTRUCTIONS,
    OrchestratorError,
    SleepCoordinator,
    StatusSnapshot,
    TmuxCodexController,
    parse_session_id,
    parse_status_snapshot,
)


STATUS_SAMPLE = """
╭─────────────────────────────────────────────────────────────────────────────────╮
│  >_ OpenAI Codex (v0.116.0)                                                     │
│                                                                                 │
│  Model:                gpt-5.4 (reasoning medium, summaries auto)               │
│  Directory:            /data/kcl/zxl/noh/orchestrator                           │
│  Permissions:          Custom (workspace-write, on-request)                     │
│  Agents.md:            <none>                                                   │
│  Account:              ludvigschumacher@gmail.com (Plus)                        │
│  Collaboration mode:   Default                                                  │
│  Session:              019d1b2c-3fc4-7740-abc6-d58891e2ea59                     │
│                                                                                 │
│  Context window:       52% left (130K used / 258K)                              │
╰─────────────────────────────────────────────────────────────────────────────────╯
"""


class ParseSessionIdTests(unittest.TestCase):
    def test_parse_status_snapshot_from_boxed_status_output(self) -> None:
        snapshot = parse_status_snapshot(STATUS_SAMPLE)
        self.assertEqual(snapshot.session_id, "019d1b2c-3fc4-7740-abc6-d58891e2ea59")
        self.assertEqual(snapshot.directory, "/data/kcl/zxl/noh/orchestrator")

    def test_parse_session_id_from_boxed_status_output(self) -> None:
        self.assertEqual(
            parse_session_id(STATUS_SAMPLE),
            "019d1b2c-3fc4-7740-abc6-d58891e2ea59",
        )

    def test_parse_session_id_uses_latest_match(self) -> None:
        text = STATUS_SAMPLE + "\nSession: 11111111-2222-3333-4444-555555555555\n"
        self.assertEqual(parse_session_id(text), "11111111-2222-3333-4444-555555555555")

    def test_parse_session_id_requires_match(self) -> None:
        with self.assertRaises(OrchestratorError):
            parse_session_id("no session here")


class FakeController:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def request_status_snapshot(self) -> StatusSnapshot:
        self.calls.append(("status", None))
        return StatusSnapshot(session_id="session-123", directory="/tmp/demo")

    def interrupt(self) -> None:
        self.calls.append(("interrupt", None))

    def resume(self, session_id: str, *, directory: str | None = None) -> None:
        self.calls.append(("resume", (session_id, directory)))


class SleepCoordinatorTests(unittest.TestCase):
    def test_sleep_coordinator_runs_status_interrupt_sleep_resume(self) -> None:
        controller = FakeController()
        slept: list[float] = []
        coordinator = SleepCoordinator(controller, sleep_fn=lambda seconds: slept.append(seconds))

        response = coordinator.request_sleep(12)
        self.assertEqual(response, {"accepted": True, "seconds": 12})

        worker = coordinator._worker
        self.assertIsNotNone(worker)
        worker.join(timeout=1)

        self.assertEqual(
            controller.calls,
            [("status", None), ("interrupt", None), ("resume", ("session-123", "/tmp/demo"))],
        )
        self.assertEqual(slept, [5, 12])

    def test_sleep_coordinator_rejects_second_active_request(self) -> None:
        controller = FakeController()
        blocker = []

        def fake_sleep(_seconds: float) -> None:
            blocker.append(True)
            while blocker:
                pass

        coordinator = SleepCoordinator(controller, sleep_fn=fake_sleep)
        coordinator.request_sleep(1)
        with self.assertRaises(OrchestratorError):
            coordinator.request_sleep(1)
        blocker.clear()


class TmuxControllerTests(unittest.TestCase):
    @patch("orchestrator.subprocess.run")
    def test_capture_pane_and_parse_session(self, mock_run) -> None:
        mock_run.side_effect = [
            unittest.mock.Mock(stdout=""),
            unittest.mock.Mock(stdout=""),
            unittest.mock.Mock(stdout=""),
            unittest.mock.Mock(stdout=STATUS_SAMPLE),
        ]

        controller = TmuxCodexController(
            tmux_session="tmux-codex",
            status_poll_interval_seconds=0,
            status_timeout_seconds=1,
        )
        snapshot = controller.request_status_snapshot()
        self.assertEqual(snapshot.session_id, "019d1b2c-3fc4-7740-abc6-d58891e2ea59")
        self.assertEqual(snapshot.directory, "/data/kcl/zxl/noh/orchestrator")

    @patch("orchestrator.subprocess.run")
    def test_resume_prepends_cd_when_requested(self, mock_run) -> None:
        controller = TmuxCodexController(tmux_session="tmux-codex")
        controller.resume("session-123", directory="/tmp/demo")
        sent = mock_run.call_args_list[0].args[0]
        self.assertEqual(
            sent,
            [
                "tmux",
                "send-keys",
                "-t",
                "tmux-codex",
                f"codex --cd /tmp/demo --yolo resume session-123 {CONTINUE_INSTRUCTIONS}",
            ],
        )

    @patch("orchestrator.subprocess.run")
    def test_resume_omits_cd_when_disabled(self, mock_run) -> None:
        controller = TmuxCodexController(tmux_session="tmux-codex", cd_before_resume=False)
        controller.resume("session-123", directory="/tmp/demo")
        sent = mock_run.call_args_list[0].args[0]
        self.assertEqual(
            sent,
            [
                "tmux",
                "send-keys",
                "-t",
                "tmux-codex",
                f"codex --yolo resume session-123 {CONTINUE_INSTRUCTIONS}",
            ],
        )


if __name__ == "__main__":
    unittest.main()
