#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


CONTINUE_PROMPT = "[Automated Message] Sleep complete."
LOG = logging.getLogger("orchestrator")


class OrchestratorError(RuntimeError):
    pass


def default_state_dir() -> Path:
    candidate = Path(tempfile.gettempdir()) / "codex-orchestrator" / f"user-{os.getuid()}"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OrchestratorError("Could not create a writable state directory for Codex Orchestrator.") from exc
    return candidate


DEFAULT_STATE_DIR = default_state_dir()


@dataclass
class TimerState:
    pane_id: str
    token: str
    wake_at: float
    prompt: str


@dataclass
class TmuxSender:
    send_spacing_seconds: float = 0.5
    sleep_fn: Callable[[float], None] = time.sleep

    def send_prompt(self, target: str, prompt: str) -> None:
        self._tmux(["send-keys", "-t", target, prompt])
        self.sleep_fn(self.send_spacing_seconds)
        self._tmux(["send-keys", "-t", target, "Enter"])

    def _tmux(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["tmux", *args], check=True, text=True, capture_output=False)


class TimerManager:
    _lock_timeout_seconds = 5.0
    _stale_lock_seconds = 30.0

    def __init__(
        self,
        sender: TmuxSender,
        *,
        state_dir: Path = DEFAULT_STATE_DIR,
        time_fn: Callable[[], float] = time.time,
        sleep_fn: Callable[[float], None] = time.sleep,
        spawn_fn: Callable[[list[str]], object] | None = None,
        script_path: Path | None = None,
        python_executable: str | None = None,
        continue_prompt: str = CONTINUE_PROMPT,
    ) -> None:
        self._sender = sender
        self._state_dir = state_dir
        self._time_fn = time_fn
        self._sleep_fn = sleep_fn
        self._spawn_fn = spawn_fn or self._spawn_worker
        self._script_path = script_path or Path(__file__).resolve()
        self._python_executable = python_executable or sys.executable
        self._continue_prompt = continue_prompt

    def sleep_timer(self, seconds: float, pane_id: str, *, prompt: str | None = None) -> dict[str, object]:
        if seconds <= 0:
            raise OrchestratorError("Sleep duration must be positive.")

        state_path = self._state_path(pane_id)
        with self._locked_state_path(state_path):
            existing = self._load_state(state_path)
            if existing is not None and existing.wake_at > self._time_fn():
                raise OrchestratorError(f"A sleep request is already active for tmux target {pane_id}.")
            if existing is not None:
                self._clear_state(state_path)

            state = TimerState(
                pane_id=pane_id,
                token=uuid.uuid4().hex,
                wake_at=self._time_fn() + seconds,
                prompt=prompt or self._continue_prompt,
            )
            self._write_state(state_path, state)

            try:
                self._spawn_fn(
                    [
                        self._python_executable,
                        str(self._script_path),
                        "_worker",
                        "--tmux-pane",
                        pane_id,
                        "--wake-at",
                        str(state.wake_at),
                        "--token",
                        state.token,
                        "--state-file",
                        str(state_path),
                        "--prompt",
                        state.prompt,
                    ]
                )
            except Exception:
                self._clear_state(state_path)
                raise
        return {
            "accepted": True,
            "seconds": seconds,
            "target": pane_id,
            "wake_at": state.wake_at,
        }

    def get_timer(self, pane_id: str) -> dict[str, object]:
        state_path = self._state_path(pane_id)
        with self._locked_state_path(state_path):
            state = self._load_state(state_path)
            if state is None:
                return {"active": False, "target": pane_id}
            if state.wake_at <= self._time_fn():
                self._clear_state(state_path)
                return {"active": False, "target": pane_id}

            seconds_remaining = max(0.0, state.wake_at - self._time_fn())
        return {
            "active": True,
            "target": pane_id,
            "wake_at": state.wake_at,
            "seconds_remaining": seconds_remaining,
        }

    def cancel_timer(self, pane_id: str) -> dict[str, object]:
        state_path = self._state_path(pane_id)
        with self._locked_state_path(state_path):
            state = self._load_state(state_path)
            if state is None:
                return {"cancelled": False, "target": pane_id}

            self._clear_state(state_path)
            return {"cancelled": True, "target": pane_id}

    def run_worker(self, pane_id: str, wake_at: float, token: str, state_file: Path, prompt: str) -> int:
        remaining = max(0.0, wake_at - self._time_fn())
        LOG.info("Sleeping for %s seconds before continuing tmux target %s", remaining, pane_id)
        self._sleep_fn(remaining)

        with self._locked_state_path(state_file):
            state = self._load_state(state_file)
            if state is None or state.token != token:
                LOG.info("Timer for tmux target %s was cancelled or replaced before wake", pane_id)
                return 0

            self._sender.send_prompt(pane_id, prompt)
            LOG.info("Sent continuation prompt to tmux target %s", pane_id)
            self._clear_state(state_file)
        return 0

    def _state_path(self, pane_id: str) -> Path:
        pane_key = pane_id.replace("%", "pane-").replace("/", "_")
        namespace = self._state_namespace()
        return self._state_dir / f"{namespace}__{pane_key}.json"

    @staticmethod
    def _lock_path(path: Path) -> Path:
        return path.with_suffix(".lock")

    def _state_namespace(self) -> str:
        tmux_socket = os.environ.get("TMUX", "").split(",", 1)[0] or "no-tmux"
        digest = hashlib.sha256(tmux_socket.encode("utf-8")).hexdigest()[:16]
        return f"tmux-{digest}"

    @contextmanager
    def _locked_state_path(self, state_path: Path):
        lock_path = self._lock_path(state_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self._lock_timeout_seconds
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                self._write_lock_metadata(fd)
                break
            except FileExistsError:
                if self._is_stale_lock(lock_path):
                    self._clear_state(lock_path)
                    continue
                if time.monotonic() >= deadline:
                    raise OrchestratorError(f"Timed out waiting for timer lock for tmux target {state_path.stem}.")
                self._sleep_fn(0.01)

        try:
            yield
        finally:
            os.close(fd)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def _write_lock_metadata(self, fd: int) -> None:
        payload = json.dumps({"pid": os.getpid(), "created_at": time.time()}).encode("utf-8")
        os.write(fd, payload)

    def _is_stale_lock(self, lock_path: Path) -> bool:
        try:
            raw = lock_path.read_text(encoding="utf-8")
        except OSError:
            return self._lock_age_exceeds_threshold(lock_path)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return self._lock_age_exceeds_threshold(lock_path)

        pid = data.get("pid")
        created_at = data.get("created_at")
        if not isinstance(pid, int) or not isinstance(created_at, (int, float)):
            return self._lock_age_exceeds_threshold(lock_path)
        if time.time() - float(created_at) > self._stale_lock_seconds:
            return True
        return not self._pid_exists(pid)

    def _lock_age_exceeds_threshold(self, lock_path: Path) -> bool:
        try:
            return time.time() - lock_path.stat().st_mtime > self._stale_lock_seconds
        except FileNotFoundError:
            return False

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _load_state(self, path: Path) -> TimerState | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return TimerState(**data)
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def _write_state(self, path: Path, state: TimerState) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(asdict(state)), encoding="utf-8")
        temp_path.replace(path)

    @staticmethod
    def _clear_state(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def _spawn_worker(args: list[str]) -> None:
        with open(os.devnull, "w", encoding="utf-8") as devnull:
            subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=devnull,
                stderr=devnull,
                start_new_session=True,
                close_fds=True,
            )


def resolve_tmux_pane(explicit_pane: str | None) -> str:
    pane_id = explicit_pane or os.environ.get("TMUX_PANE")
    if not pane_id:
        raise OrchestratorError("Could not determine tmux pane. Set TMUX_PANE or pass --tmux-pane.")
    return pane_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tmux-backed Codex sleep orchestrator.")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--log-level", default="INFO")

    subparsers = parser.add_subparsers(dest="command", required=True)

    sleep_parser = subparsers.add_parser("sleep", help="Start a background timer for the current tmux pane.")
    sleep_parser.add_argument("seconds", type=float)
    sleep_parser.add_argument("--tmux-pane")
    sleep_parser.add_argument("--prompt", default=CONTINUE_PROMPT)

    get_parser = subparsers.add_parser("get", help="Show the active timer for the current tmux pane.")
    get_parser.add_argument("--tmux-pane")

    cancel_parser = subparsers.add_parser("cancel", help="Cancel the active timer for the current tmux pane.")
    cancel_parser.add_argument("--tmux-pane")

    worker_parser = subparsers.add_parser("_worker", help=argparse.SUPPRESS)
    worker_parser.add_argument("--tmux-pane", required=True)
    worker_parser.add_argument("--wake-at", type=float, required=True)
    worker_parser.add_argument("--token", required=True)
    worker_parser.add_argument("--state-file", type=Path, required=True)
    worker_parser.add_argument("--prompt", default=CONTINUE_PROMPT)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    manager = TimerManager(TmuxSender(), state_dir=args.state_dir)

    try:
        if args.command == "sleep":
            payload = manager.sleep_timer(args.seconds, resolve_tmux_pane(args.tmux_pane), prompt=args.prompt)
        elif args.command == "get":
            payload = manager.get_timer(resolve_tmux_pane(args.tmux_pane))
        elif args.command == "cancel":
            payload = manager.cancel_timer(resolve_tmux_pane(args.tmux_pane))
        elif args.command == "_worker":
            return manager.run_worker(args.tmux_pane, args.wake_at, args.token, args.state_file, args.prompt)
        else:
            raise OrchestratorError(f"Unsupported command: {args.command}")
    except OrchestratorError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
