#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import json
import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

CONTINUE_INSTRUCTIONS = "Sleep complete, this is orchestrator resuming your execution. Please continue."
LOG = logging.getLogger("orchestrator")
SESSION_RE = re.compile(r"Session:\s*([0-9a-fA-F-]{8,})")
DIRECTORY_RE = re.compile(r"Directory:\s*(.+?)(?:\s*│)?\s*$", re.MULTILINE)


class OrchestratorError(RuntimeError):
    pass


@dataclass(frozen=True)
class StatusSnapshot:
    session_id: str
    directory: str


def parse_status_snapshot(status_text: str) -> StatusSnapshot:
    matches = SESSION_RE.findall(status_text)
    if not matches:
        raise OrchestratorError("Could not find Codex session id in /status output.")
    directory_match = DIRECTORY_RE.search(status_text)
    if not directory_match:
        raise OrchestratorError("Could not find Codex directory in /status output.")
    return StatusSnapshot(session_id=matches[-1], directory=directory_match.group(1).strip())


def parse_session_id(status_text: str) -> str:
    return parse_status_snapshot(status_text).session_id


@dataclass
class TmuxCodexController:
    tmux_session: str
    status_command: str = "/status"
    cd_before_resume: bool = True
    status_timeout_seconds: float = 20.0
    status_poll_interval_seconds: float = 3
    sleep_fn: Callable[[float], None] = time.sleep

    def request_status_snapshot(self) -> StatusSnapshot:
        self.send_keys(self.status_command, enter=True)
        deadline = time.monotonic() + self.status_timeout_seconds
        last_capture = ""
        while time.monotonic() < deadline:
            self.sleep_fn(self.status_poll_interval_seconds)
            last_capture = self.capture_pane()
            try:
                return parse_status_snapshot(last_capture)
            except OrchestratorError:
                continue
        raise OrchestratorError(
            "Timed out waiting for /status output with session metadata.\n"
            f"Last pane capture:\n{last_capture}"
        )

    def interrupt(self, repeats: int = 3, spacing_seconds: float = 0.2) -> None:
        for index in range(repeats):
            self._tmux(["send-keys", "-t", self.tmux_session, "C-c"])
            if index + 1 < repeats:
                self.sleep_fn(spacing_seconds)

    def resume(self, session_id: str, *, directory: str | None = None) -> None:
        if self.cd_before_resume:
            if not directory:
                raise OrchestratorError("Directory restore is enabled but no parsed directory is available.")
            command = f"codex --cd {shlex.quote(directory)} --yolo resume {shlex.quote(session_id)} \"{CONTINUE_INSTRUCTIONS}\""
        else:
            command = f"codex --yolo resume {shlex.quote(session_id)} \"{CONTINUE_INSTRUCTIONS}\""
        self.send_keys(command, enter=True)

    def send_keys(self, text: str, *, enter: bool) -> None:
        self._tmux(["send-keys", "-t", self.tmux_session, text])
        if enter:
            self.sleep_fn(0.5)
            self._tmux(["send-keys", "-t", self.tmux_session, "Enter"])

    def capture_pane(self, start_line: str = "-50") -> str:
        result = self._tmux(
            ["capture-pane", "-p", "-t", self.tmux_session, "-S", start_line],
            capture_output=True,
        )
        return result.stdout

    def _tmux(self, args: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["tmux", *args],
            check=True,
            text=True,
            capture_output=capture_output,
        )
        return completed


class SleepCoordinator:
    def __init__(self, controller: TmuxCodexController, sleep_fn: Callable[[float], None] = time.sleep) -> None:
        self._controller = controller
        self._sleep_fn = sleep_fn
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._active = False

    def request_sleep(self, seconds: float) -> dict[str, object]:
        if seconds <= 0:
            raise OrchestratorError("Sleep duration must be positive.")
        with self._lock:
            if self._active:
                raise OrchestratorError("A sleep request is already active.")
            self._active = True
            self._worker = threading.Thread(
                target=self._sleep_and_resume,
                args=(seconds,),
                name="sleep-and-resume",
                daemon=True,
            )
            self._worker.start()
        return {"accepted": True, "seconds": seconds}

    def _sleep_and_resume(self, seconds: float) -> None:
        try:
            self._sleep_fn(5)
            snapshot = self._controller.request_status_snapshot()
            LOG.info("Captured Codex session id %s in %s", snapshot.session_id, snapshot.directory)
            self._controller.interrupt()
            LOG.info("Interrupted Codex session %s; sleeping for %s seconds", snapshot.session_id, seconds)
            self._sleep_fn(seconds)
            self._controller.resume(snapshot.session_id, directory=snapshot.directory)
            LOG.info("Resumed Codex session %s", snapshot.session_id)
        except Exception:
            LOG.exception("Sleep/resume cycle failed")
        finally:
            with self._lock:
                self._active = False
                self._worker = None


class OrchestratorHandler(BaseHTTPRequestHandler):
    coordinator: SleepCoordinator

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/sleep":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        try:
            seconds = self._parse_sleep_seconds()
            payload = self.coordinator.request_sleep(seconds)
        except OrchestratorError as exc:
            status = HTTPStatus.CONFLICT if "already active" in str(exc) else HTTPStatus.BAD_REQUEST
            self._send_json(status, {"error": str(exc)})
            return
        except json.JSONDecodeError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Invalid JSON body: {exc}"})
            return

        self._send_json(HTTPStatus.ACCEPTED, payload)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        LOG.info("%s - %s", self.address_string(), format % args)

    def _parse_sleep_seconds(self) -> float:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8").strip()
        if not raw_body:
            raise OrchestratorError("Request body must contain sleep seconds.")
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()

        if content_type == "application/json":
            body = json.loads(raw_body)
            if not isinstance(body, dict) or "seconds" not in body:
                raise OrchestratorError("JSON body must be an object with a `seconds` field.")
            seconds = body["seconds"]
        else:
            seconds = raw_body

        try:
            return float(seconds)
        except (TypeError, ValueError) as exc:
            raise OrchestratorError("Sleep seconds must be numeric.") from exc

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_handler(coordinator: SleepCoordinator) -> type[OrchestratorHandler]:
    class Handler(OrchestratorHandler):
        pass

    Handler.coordinator = coordinator
    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal tmux-backed Codex sleep/resume orchestrator.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--tmux-session", default="tmux-codex")
    parser.add_argument(
        "--no-cd",
        action="store_true",
        help="Do not restore the parsed Codex status directory when running the resume command.",
    )
    parser.add_argument("--status-timeout", type=float, default=20.0)
    parser.add_argument("--status-poll-interval", type=float, default=3)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    controller = TmuxCodexController(
        tmux_session=args.tmux_session,
        cd_before_resume=not args.no_cd,
        status_timeout_seconds=args.status_timeout,
        status_poll_interval_seconds=args.status_poll_interval,
    )
    coordinator = SleepCoordinator(controller)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(coordinator))
    LOG.info("Listening on http://%s:%s/sleep for tmux session %s", args.host, args.port, args.tmux_session)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
