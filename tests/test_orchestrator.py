from __future__ import annotations

import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

from orchestrator import CONTINUE_PROMPT, OrchestratorError, TimerManager, TimerState, TmuxSender, main, resolve_tmux_pane


class FakeSender:
    def __init__(self) -> None:
        self.prompts: list[tuple[str, str]] = []

    def send_prompt(self, target: str, prompt: str) -> None:
        self.prompts.append((target, prompt))


class TimerManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.state_dir = Path(self.tempdir.name)
        self.sender = FakeSender()
        self.spawned: list[list[str]] = []
        self.now = 1_000.0

        def spawn_fn(args: list[str]) -> None:
            self.spawned.append(args)

        self.manager = TimerManager(
            self.sender,
            state_dir=self.state_dir,
            time_fn=lambda: self.now,
            sleep_fn=lambda _seconds: None,
            spawn_fn=spawn_fn,
            script_path=Path("/tmp/orchestrator.py"),
            python_executable="python",
        )

    def test_sleep_timer_creates_state_and_spawns_worker(self) -> None:
        response = self.manager.sleep_timer(12, "%7")
        state_path = self.manager._state_path("%7")

        self.assertTrue(response["accepted"])
        self.assertEqual(response["target"], "%7")
        self.assertEqual(response["seconds"], 12)
        self.assertEqual(response["wake_at"], 1_012.0)
        self.assertEqual(self.spawned[0][:4], ["python", "/tmp/orchestrator.py", "_worker", "--tmux-pane"])
        self.assertTrue(state_path.exists())

    def test_sleep_timer_rejects_second_active_request_for_same_pane(self) -> None:
        self.manager.sleep_timer(5, "%1")

        with self.assertRaises(OrchestratorError):
            self.manager.sleep_timer(7, "%1")

    def test_sleep_timer_allows_different_panes(self) -> None:
        first = self.manager.sleep_timer(5, "%1")
        second = self.manager.sleep_timer(7, "%2")

        self.assertEqual(first["target"], "%1")
        self.assertEqual(second["target"], "%2")

    def test_get_timer_returns_active_timer(self) -> None:
        self.manager.sleep_timer(10, "%1")
        self.now = 1_004.0

        status = self.manager.get_timer("%1")

        self.assertEqual(status["target"], "%1")
        self.assertTrue(status["active"])
        self.assertEqual(status["seconds_remaining"], 6.0)

    def test_cancel_timer_clears_state(self) -> None:
        self.manager.sleep_timer(10, "%1")
        state_path = self.manager._state_path("%1")

        result = self.manager.cancel_timer("%1")

        self.assertEqual(result, {"cancelled": True, "target": "%1"})
        self.assertFalse(state_path.exists())

    def test_run_worker_sends_prompt_and_clears_state(self) -> None:
        state_path = self.manager._state_path("%1")
        state = TimerState("%1", "abc", 1_005.0, CONTINUE_PROMPT)
        state_path.write_text(
            '{"pane_id":"%1","token":"abc","wake_at":1005.0,"prompt":"[Automated Message] Sleep complete."}',
            encoding="utf-8",
        )
        slept: list[float] = []
        manager = TimerManager(
            self.sender,
            state_dir=self.state_dir,
            time_fn=lambda: 1_000.0,
            sleep_fn=lambda seconds: slept.append(seconds),
            spawn_fn=lambda _args: None,
        )

        code = manager.run_worker("%1", state.wake_at, state.token, state_path, CONTINUE_PROMPT)

        self.assertEqual(code, 0)
        self.assertEqual(slept, [5.0])
        self.assertEqual(self.sender.prompts, [("%1", CONTINUE_PROMPT)])
        self.assertFalse(state_path.exists())

    def test_run_worker_exits_without_prompt_when_state_is_missing(self) -> None:
        state_path = self.manager._state_path("%1")

        code = self.manager.run_worker("%1", 1_001.0, "missing", state_path, CONTINUE_PROMPT)

        self.assertEqual(code, 0)
        self.assertEqual(self.sender.prompts, [])

    def test_cancel_timer_before_worker_wake_prevents_prompt(self) -> None:
        self.manager.sleep_timer(10, "%1")
        state_path = self.manager._state_path("%1")
        state = self.manager._load_state(state_path)
        assert state is not None
        worker_ready = threading.Event()
        allow_worker = threading.Event()
        slept: list[float] = []

        manager = TimerManager(
            self.sender,
            state_dir=self.state_dir,
            time_fn=lambda: 1_000.0,
            sleep_fn=lambda seconds: (slept.append(seconds), worker_ready.set(), allow_worker.wait(timeout=1)),
            spawn_fn=lambda _args: None,
        )

        worker = threading.Thread(
            target=manager.run_worker,
            args=("%1", state.wake_at, state.token, state_path, CONTINUE_PROMPT),
        )
        worker.start()
        self.assertTrue(worker_ready.wait(timeout=1))

        result = self.manager.cancel_timer("%1")
        allow_worker.set()
        worker.join(timeout=1)

        self.assertEqual(result, {"cancelled": True, "target": "%1"})
        self.assertEqual(slept, [10.0])
        self.assertEqual(self.sender.prompts, [])

    def test_sleep_timer_uses_tmux_namespace_in_state_path(self) -> None:
        with mock.patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,123,0"}, clear=True):
            first = self.manager._state_path("%1")
        with mock.patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/other,456,0"}, clear=True):
            second = self.manager._state_path("%1")

        self.assertNotEqual(first, second)

    def test_sleep_timer_serializes_concurrent_creation_for_same_pane(self) -> None:
        release_spawn = threading.Event()
        spawn_started = threading.Event()
        spawned: list[list[str]] = []

        def spawn_fn(args: list[str]) -> None:
            spawn_started.set()
            release_spawn.wait(timeout=1)
            spawned.append(args)

        manager = TimerManager(
            self.sender,
            state_dir=self.state_dir,
            time_fn=lambda: self.now,
            sleep_fn=lambda _seconds: None,
            spawn_fn=spawn_fn,
            script_path=Path("/tmp/orchestrator.py"),
            python_executable="python",
        )

        results: list[dict[str, object]] = []
        errors: list[Exception] = []

        def request_sleep() -> None:
            try:
                results.append(manager.sleep_timer(5, "%race"))
            except Exception as exc:  # pragma: no cover - assertion below inspects the exact type
                errors.append(exc)

        first = threading.Thread(target=request_sleep)
        second = threading.Thread(target=request_sleep)
        first.start()
        self.assertTrue(spawn_started.wait(timeout=1))
        second.start()
        release_spawn.set()
        first.join(timeout=1)
        second.join(timeout=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(len(spawned), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], OrchestratorError)
        self.assertIn("already active", str(errors[0]))

    def test_cancel_timer_waits_for_inflight_worker_and_reports_not_cancelled(self) -> None:
        state_path = self.manager._state_path("%1")
        state = TimerState("%1", "abc", 1_000.0, CONTINUE_PROMPT)
        self.manager._write_state(state_path, state)
        send_started = threading.Event()
        release_send = threading.Event()
        cancel_result: dict[str, object] = {}

        class BlockingSender:
            def send_prompt(self, target: str, prompt: str) -> None:
                send_started.set()
                release_send.wait(timeout=1)
                self.prompts.append((target, prompt))

            def __init__(self) -> None:
                self.prompts: list[tuple[str, str]] = []

        sender = BlockingSender()
        manager = TimerManager(
            sender,
            state_dir=self.state_dir,
            time_fn=lambda: 1_000.0,
            sleep_fn=lambda _seconds: None,
            spawn_fn=lambda _args: None,
        )

        worker = threading.Thread(
            target=manager.run_worker,
            args=("%1", state.wake_at, state.token, state_path, CONTINUE_PROMPT),
        )
        worker.start()
        self.assertTrue(send_started.wait(timeout=1))

        cancel_thread = threading.Thread(target=lambda: cancel_result.update(self.manager.cancel_timer("%1")))
        cancel_thread.start()
        self.assertTrue(cancel_thread.is_alive())
        release_send.set()
        worker.join(timeout=1)
        cancel_thread.join(timeout=1)

        self.assertEqual(cancel_result, {"cancelled": False, "target": "%1"})
        self.assertEqual(sender.prompts, [("%1", CONTINUE_PROMPT)])

    def test_stale_lock_is_recovered(self) -> None:
        state_path = self.manager._state_path("%1")
        lock_path = self.manager._lock_path(state_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text('{"pid":999999,"created_at":1000.0}', encoding="utf-8")

        with mock.patch.object(TimerManager, "_pid_exists", return_value=False):
            response = self.manager.sleep_timer(5, "%1")

        self.assertTrue(response["accepted"])
        self.assertFalse(lock_path.exists())


class WorkerSpawnTests(unittest.TestCase):
    @mock.patch("orchestrator.subprocess.Popen")
    def test_spawn_worker_uses_direct_subprocess_without_shell_expansion(self, mock_popen) -> None:
        args = [
            "python",
            "/tmp/orchestrator.py",
            "_worker",
            "--prompt",
            '$(touch /tmp/pwned)',
        ]

        TimerManager._spawn_worker(args)

        mock_popen.assert_called_once()
        self.assertEqual(mock_popen.call_args.args[0], args)
        self.assertTrue(mock_popen.call_args.kwargs["start_new_session"])
        self.assertNotIn("shell", mock_popen.call_args.kwargs)


class TmuxResolutionTests(unittest.TestCase):
    def test_resolve_tmux_pane_prefers_explicit_value(self) -> None:
        self.assertEqual(resolve_tmux_pane("%9"), "%9")

    def test_resolve_tmux_pane_raises_without_env_or_explicit_value(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(OrchestratorError):
                resolve_tmux_pane(None)


class CliTests(unittest.TestCase):
    @mock.patch("orchestrator.print")
    @mock.patch("orchestrator.TimerManager")
    def test_main_sleep_subcommand_uses_timer_manager(self, mock_manager_cls, mock_print) -> None:
        mock_manager = mock_manager_cls.return_value
        mock_manager.sleep_timer.return_value = {"accepted": True, "target": "%9"}

        code = main(["sleep", "30", "--tmux-pane", "%9"])

        self.assertEqual(code, 0)
        mock_manager.sleep_timer.assert_called_once_with(30.0, "%9", prompt=CONTINUE_PROMPT)
        mock_print.assert_called_once_with('{"accepted": true, "target": "%9"}')


class TmuxSenderTests(unittest.TestCase):
    @mock.patch("orchestrator.subprocess.run")
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
