#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


CONTINUE_PROMPT = "Sleep complete, this is orchestrator resuming your execution. Please continue."
LOG = logging.getLogger("orchestrator")
SLEEP_CALL_PATTERN = re.compile(r"(curl|httpie|http)\b.*?/sleep\b|/sleep\b.*?(curl|httpie|http)", re.IGNORECASE)


class OrchestratorError(RuntimeError):
    pass


@dataclass
class TmuxPane:
    pane_id: str
    current_command: str
    is_active: bool
    is_dead: bool
    activity_epoch: int


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


@dataclass
class FixedTmuxTargetResolver:
    target: str

    def resolve_target(self) -> str:
        return self.target


@dataclass
class AutoTmuxTargetResolver:
    capture_lines: int = 120
    min_score: int = 1
    list_panes_fn: Callable[[], list[TmuxPane]] | None = None
    capture_pane_fn: Callable[[str, int], str] | None = None

    def resolve_target(self) -> str:
        panes = self._list_panes()
        best_pane: TmuxPane | None = None
        best_rank: tuple[int, int, int, int] | None = None

        for pane in panes:
            rank = self._rank_pane(pane)
            if rank is None:
                continue
            if best_rank is None or rank > best_rank:
                best_rank = rank
                best_pane = pane

        if best_pane is None or best_rank is None:
            raise OrchestratorError("Could not detect a tmux pane that recently called /sleep.")

        LOG.info("Auto-detected tmux caller pane %s with rank %s", best_pane.pane_id, best_rank)
        return best_pane.pane_id

    def _rank_pane(self, pane: TmuxPane) -> tuple[int, int, int, int] | None:
        if pane.is_dead:
            return None

        transcript = self._capture_pane(pane.pane_id)
        lines = [line.strip() for line in transcript.splitlines() if line.strip()]
        match_offsets = [offset for offset, line in enumerate(reversed(lines)) if SLEEP_CALL_PATTERN.search(line)]
        if not match_offsets:
            return None

        latest_offset = match_offsets[0]
        preferred_command = int(pane.current_command.lower() in {"codex", "python", "bash", "zsh", "fish"})

        # Prefer the pane whose /sleep call is closest to the live bottom of scrollback.
        # General pane activity is only a tie-breaker when the visible /sleep recency is the same.
        return (-latest_offset, int(pane.is_active), pane.activity_epoch, preferred_command)

    def _list_panes(self) -> list[TmuxPane]:
        if self.list_panes_fn is not None:
            return self.list_panes_fn()

        result = subprocess.run(
            [
                "tmux",
                "list-panes",
                "-a",
                "-F",
                "#{pane_id}\t#{pane_current_command}\t#{pane_active}\t#{pane_dead}\t#{pane_activity}",
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        panes: list[TmuxPane] = []
        for raw_line in result.stdout.splitlines():
            pane_id, command, is_active, is_dead, activity_epoch = raw_line.split("\t", 4)
            panes.append(
                TmuxPane(
                    pane_id=pane_id,
                    current_command=command,
                    is_active=is_active == "1",
                    is_dead=is_dead == "1",
                    activity_epoch=int(activity_epoch or 0),
                )
            )
        return panes

    def _capture_pane(self, pane_id: str) -> str:
        if self.capture_pane_fn is not None:
            return self.capture_pane_fn(pane_id, self.capture_lines)

        result = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", pane_id, "-S", f"-{self.capture_lines}"],
            check=True,
            text=True,
            capture_output=True,
        )
        return result.stdout


class SleepCoordinator:
    def __init__(
        self,
        sender: TmuxSender,
        target_resolver: FixedTmuxTargetResolver | AutoTmuxTargetResolver,
        *,
        continue_prompt: str = CONTINUE_PROMPT,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sender = sender
        self._target_resolver = target_resolver
        self._continue_prompt = continue_prompt
        self._sleep_fn = sleep_fn
        self._lock = threading.Lock()
        self._workers: dict[str, threading.Thread] = {}

    def request_sleep(self, seconds: float) -> dict[str, object]:
        if seconds <= 0:
            raise OrchestratorError("Sleep duration must be positive.")
        with self._lock:
            target = self._target_resolver.resolve_target()
            if target in self._workers:
                raise OrchestratorError(f"A sleep request is already active for tmux target {target}.")
            worker = threading.Thread(
                target=self._sleep_and_continue,
                args=(seconds, target),
                name="sleep-and-continue",
                daemon=True,
            )
            self._workers[target] = worker
            worker.start()
        return {"accepted": True, "seconds": seconds, "target": target}

    def _sleep_and_continue(self, seconds: float, target: str) -> None:
        try:
            LOG.info("Sleeping for %s seconds before continuing tmux target %s", seconds, target)
            self._sleep_fn(seconds)
            self._sender.send_prompt(target, self._continue_prompt)
            LOG.info("Sent continuation prompt to tmux target %s", target)
        except Exception:
            LOG.exception("Sleep/continue cycle failed")
        finally:
            with self._lock:
                self._workers.pop(target, None)


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
    parser.add_argument("--tmux-target", help="Explicit tmux pane/session/window target. If omitted, auto-detect the caller pane.")
    parser.add_argument("--capture-lines", type=int, default=120, help="Number of lines to inspect from each tmux pane during auto-detection.")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    sender = TmuxSender()
    if args.tmux_target:
        target_resolver: FixedTmuxTargetResolver | AutoTmuxTargetResolver = FixedTmuxTargetResolver(args.tmux_target)
    else:
        target_resolver = AutoTmuxTargetResolver(capture_lines=args.capture_lines)
    coordinator = SleepCoordinator(sender, target_resolver)
    server = ThreadingHTTPServer((args.host, args.port), build_handler(coordinator))
    LOG.info(
        "Listening on http://%s:%s/sleep using %s",
        args.host,
        args.port,
        f"fixed tmux target {args.tmux_target}" if args.tmux_target else "auto tmux pane detection",
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
