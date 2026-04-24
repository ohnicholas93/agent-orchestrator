#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from orchestrator_constants import (
    COMPACT_CONFIRMATION_PROMPT,
    COMPACT_POST_COMMAND_DELAY_SECONDS,
    CONTEXT_WARNING_THRESHOLD_PERCENT,
    CONTINUE_PROMPT,
    STALE_TIMER_GRACE_SECONDS,
)
from orchestrator_context import read_context_remaining_percent
from orchestrator_errors import OrchestratorError
from orchestrator_timers import TimerManager, TimerState, default_state_dir, resolve_tmux_pane
from orchestrator_tmux import TmuxSender


LOG = logging.getLogger("orchestrator")
DEFAULT_STATE_DIR = default_state_dir()


def _build_context_warning_message(*, remaining_percent: int, orchestrator_path: Path) -> str:
    return (
        f"Your current model context window is {remaining_percent}% remaining. "
        f"The orchestrator suggests you run `{orchestrator_path} compact` at a convenient time."
    )


def _maybe_attach_response_message(
    payload: dict[str, object],
    *,
    sender: TmuxSender,
    pane_id: str | None,
    orchestrator_path: Path,
) -> dict[str, object]:
    if pane_id is None:
        return payload
    remaining_percent = read_context_remaining_percent(sender, pane_id)
    if remaining_percent is None:
        return payload
    output = dict(payload)
    if remaining_percent < CONTEXT_WARNING_THRESHOLD_PERCENT:
        output["message"] = _build_context_warning_message(
            remaining_percent=remaining_percent,
            orchestrator_path=orchestrator_path,
        )
        return output
    output["message"] = None
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tmux-backed Codex sleep orchestrator.")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--log-level", default="INFO")

    subparsers = parser.add_subparsers(dest="command", required=True)

    sleep_parser = subparsers.add_parser("sleep", help="Start a background timer for the current tmux pane.")
    sleep_parser.add_argument("seconds", type=float)
    sleep_parser.add_argument("--tmux-pane")
    sleep_parser.add_argument("--prompt", default=CONTINUE_PROMPT)

    status_parser = subparsers.add_parser("status", help="Show timer status for a pane or list all timers.")
    status_parser.add_argument("--tmux-pane")

    cancel_parser = subparsers.add_parser("cancel", help="Cancel the active timer for the current tmux pane.")
    cancel_parser.add_argument("--tmux-pane")

    compact_parser = subparsers.add_parser("compact", help="Ask Codex to compact context in the target pane.")
    compact_parser.add_argument("--tmux-pane")
    compact_parser.add_argument("--confirmation-prompt", default=COMPACT_CONFIRMATION_PROMPT)
    compact_parser.add_argument("--post-command-delay-seconds", type=float, default=COMPACT_POST_COMMAND_DELAY_SECONDS)

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

    sender = TmuxSender()
    manager = TimerManager(sender, state_dir=args.state_dir, script_path=Path(__file__).resolve())
    pane_for_message: str | None = None
    orchestrator_path = Path(__file__).resolve()

    try:
        if args.command == "sleep":
            pane_for_message = resolve_tmux_pane(args.tmux_pane)
            payload = manager.sleep_timer(args.seconds, pane_for_message, prompt=args.prompt)
        elif args.command == "status":
            pane_for_message = args.tmux_pane or os.environ.get("TMUX_PANE")
            if pane_for_message:
                payload = manager.get_timer(pane_for_message)
            else:
                payload = manager.list_active_timers(stale_grace_seconds=STALE_TIMER_GRACE_SECONDS)
        elif args.command == "cancel":
            pane_for_message = resolve_tmux_pane(args.tmux_pane)
            payload = manager.cancel_timer(pane_for_message)
        elif args.command == "compact":
            pane_for_message = resolve_tmux_pane(args.tmux_pane)
            sender.send_compact_sequence(
                pane_for_message,
                confirmation_prompt=args.confirmation_prompt,
                post_command_delay_seconds=args.post_command_delay_seconds,
            )
            payload = {"accepted": True, "target": pane_for_message}
        elif args.command == "_worker":
            return manager.run_worker(args.tmux_pane, args.wake_at, args.token, args.state_file, args.prompt)
        else:
            raise OrchestratorError(f"Unsupported command: {args.command}")
    except OrchestratorError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    payload = _maybe_attach_response_message(
        payload,
        sender=sender,
        pane_id=pane_for_message,
        orchestrator_path=orchestrator_path,
    )
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

