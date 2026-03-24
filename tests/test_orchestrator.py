from __future__ import annotations

import unittest
from unittest.mock import patch

from orchestrator import CONTINUE_PROMPT, OrchestratorError, SleepCoordinator, TmuxCodexController


class FakeController:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def send_prompt(self, prompt: str) -> None:
        self.prompts.append(prompt)


class SleepCoordinatorTests(unittest.TestCase):
    def test_sleep_coordinator_sleeps_then_sends_continue_prompt(self) -> None:
        controller = FakeController()
        slept: list[float] = []
        coordinator = SleepCoordinator(controller, sleep_fn=lambda seconds: slept.append(seconds))

        response = coordinator.request_sleep(12)
        self.assertEqual(response, {"accepted": True, "seconds": 12})

        worker = coordinator._worker
        self.assertIsNotNone(worker)
        worker.join(timeout=1)

        self.assertEqual(slept, [12])
        self.assertEqual(controller.prompts, [CONTINUE_PROMPT])

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
    def test_send_prompt_sends_text_then_enter(self, mock_run) -> None:
        controller = TmuxCodexController(tmux_session="tmux-codex", sleep_fn=lambda _seconds: None)
        controller.send_prompt("continue please")
        self.assertEqual(
            [call.args[0] for call in mock_run.call_args_list],
            [
                ["tmux", "send-keys", "-t", "tmux-codex", "continue please"],
                ["tmux", "send-keys", "-t", "tmux-codex", "Enter"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
