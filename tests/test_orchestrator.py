from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from orchestrator import (
    CONTINUE_PROMPT,
    AutoTmuxTargetResolver,
    FixedTmuxTargetResolver,
    OrchestratorError,
    SleepCoordinator,
    TmuxPane,
    TmuxSender,
)


class FakeSender:
    def __init__(self) -> None:
        self.prompts: list[tuple[str, str]] = []

    def send_prompt(self, target: str, prompt: str) -> None:
        self.prompts.append((target, prompt))


class SleepCoordinatorTests(unittest.TestCase):
    def test_sleep_coordinator_sleeps_then_sends_continue_prompt(self) -> None:
        sender = FakeSender()
        slept: list[float] = []
        coordinator = SleepCoordinator(
            sender,
            FixedTmuxTargetResolver("%7"),
            sleep_fn=lambda seconds: slept.append(seconds),
        )

        response = coordinator.request_sleep(12)
        self.assertEqual(response, {"accepted": True, "seconds": 12, "target": "%7"})

        worker = coordinator._workers["%7"]
        worker.join(timeout=1)

        self.assertEqual(slept, [12])
        self.assertEqual(sender.prompts, [("%7", CONTINUE_PROMPT)])

    def test_sleep_coordinator_rejects_second_active_request_for_same_target(self) -> None:
        sender = FakeSender()
        blocker = []

        def fake_sleep(_seconds: float) -> None:
            blocker.append(True)
            while blocker:
                pass

        coordinator = SleepCoordinator(sender, FixedTmuxTargetResolver("%1"), sleep_fn=fake_sleep)
        coordinator.request_sleep(1)
        with self.assertRaises(OrchestratorError):
            coordinator.request_sleep(1)
        blocker.clear()

    def test_sleep_coordinator_allows_concurrent_requests_for_different_targets(self) -> None:
        sender = FakeSender()
        slept: list[tuple[str, float]] = []
        targets = iter(["%1", "%2"])

        class SequencedResolver:
            def resolve_target(self) -> str:
                return next(targets)

        def fake_sleep(seconds: float) -> None:
            thread_name = threading.current_thread().name
            slept.append((thread_name, seconds))

        coordinator = SleepCoordinator(sender, SequencedResolver(), sleep_fn=fake_sleep)

        first = coordinator.request_sleep(3)
        second = coordinator.request_sleep(7)

        self.assertEqual(first["target"], "%1")
        self.assertEqual(second["target"], "%2")

        for worker in list(coordinator._workers.values()):
            worker.join(timeout=1)

        self.assertEqual(sender.prompts, [("%1", CONTINUE_PROMPT), ("%2", CONTINUE_PROMPT)])
        self.assertEqual(sorted(seconds for _thread_name, seconds in slept), [3, 7])


class AutoTmuxTargetResolverTests(unittest.TestCase):
    def test_resolver_picks_most_recent_sleep_caller(self) -> None:
        panes = [
            TmuxPane("%1", "bash", False, False, 100),
            TmuxPane("%2", "bash", True, False, 250),
        ]
        transcripts = {
            "%1": "curl -X POST http://127.0.0.1:8766/sleep -d '30'\nolder output\n",
            "%2": "noise\ncurl -X POST http://127.0.0.1:8766/sleep -d '5'\n",
        }
        resolver = AutoTmuxTargetResolver(
            list_panes_fn=lambda: panes,
            capture_pane_fn=lambda pane_id, _capture_lines: transcripts[pane_id],
        )

        self.assertEqual(resolver.resolve_target(), "%2")

    def test_resolver_does_not_let_later_general_activity_steal_resume(self) -> None:
        panes = [
            TmuxPane("%1", "bash", True, False, 5_000),
            TmuxPane("%2", "bash", False, False, 100),
        ]
        transcripts = {
            "%1": (
                "curl -X POST http://127.0.0.1:8766/sleep -d '30'\n"
                "build output\n"
                "more output\n"
                "shell prompt\n"
            ),
            "%2": "noise\ncurl -X POST http://127.0.0.1:8766/sleep -d '5'\n",
        }
        resolver = AutoTmuxTargetResolver(
            list_panes_fn=lambda: panes,
            capture_pane_fn=lambda pane_id, _capture_lines: transcripts[pane_id],
        )

        self.assertEqual(resolver.resolve_target(), "%2")

    def test_resolver_raises_when_no_sleep_call_is_visible(self) -> None:
        resolver = AutoTmuxTargetResolver(
            list_panes_fn=lambda: [TmuxPane("%1", "bash", True, False, 100)],
            capture_pane_fn=lambda _pane_id, _capture_lines: "echo hello\nls -la\n",
        )

        with self.assertRaises(OrchestratorError):
            resolver.resolve_target()


class TmuxSenderTests(unittest.TestCase):
    @patch("orchestrator.subprocess.run")
    def test_send_prompt_sends_text_then_enter(self, mock_run) -> None:
        sender = TmuxSender(sleep_fn=lambda _seconds: None)
        sender.send_prompt("%9", "continue please")
        self.assertEqual(
            [call.args[0] for call in mock_run.call_args_list],
            [
                ["tmux", "send-keys", "-t", "%9", "continue please"],
                ["tmux", "send-keys", "-t", "%9", "Enter"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
