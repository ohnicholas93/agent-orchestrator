#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable


CONTINUE_PROMPT = "Sleep complete, this is orchestrator resuming your execution. Please continue."
LOG = logging.getLogger("orchestrator")


class OrchestratorError(RuntimeError):
    pass


@dataclass
class TmuxCodexController:
    tmux_session: str
    send_spacing_seconds: float = 0.5
    sleep_fn: Callable[[float], None] = time.sleep

    def send_prompt(self, prompt: str) -> None:
        self._tmux(["send-keys", "-t", self.tmux_session, prompt])
        self.sleep_fn(self.send_spacing_seconds)
        self._tmux(["send-keys", "-t", self.tmux_session, "Enter"])

    def _tmux(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["tmux", *args], check=True, text=True, capture_output=False)


class SleepCoordinator:
    def __init__(
        self,
        controller: TmuxCodexController,
        *,
        continue_prompt: str = CONTINUE_PROMPT,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._controller = controller
        self._continue_prompt = continue_prompt
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
                target=self._sleep_and_continue,
                args=(seconds,),
                name="sleep-and-continue",
                daemon=True,
            )
            self._worker.start()
        return {"accepted": True, "seconds": seconds}

    def _sleep_and_continue(self, seconds: float) -> None:
        try:
            LOG.info("Sleeping for %s seconds before continuing tmux session", seconds)
            self._sleep_fn(seconds)
            self._controller.send_prompt(self._continue_prompt)
            LOG.info("Sent continuation prompt to tmux session")
        except Exception:
            LOG.exception("Sleep/continue cycle failed")
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
    parser = argparse.ArgumentParser(description="Minimal tmux-backed Codex sleep/continue orchestrator.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--tmux-session", default="tmux-codex")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    controller = TmuxCodexController(tmux_session=args.tmux_session)
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
