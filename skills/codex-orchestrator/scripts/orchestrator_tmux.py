from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Callable

from orchestrator_constants import (
    COMPACT_COMMAND,
    COMPACT_FORWARDED_CONTEXT_PREFIX,
    COMPACT_FORWARDED_CONTEXT_SUFFIX,
    COMPACT_INTERRUPT_KEY,
    TMUX_SEND_SPACING_SECONDS,
)


@dataclass
class TmuxSender:
    send_spacing_seconds: float = TMUX_SEND_SPACING_SECONDS
    sleep_fn: Callable[[float], None] = time.sleep

    def send_prompt(self, target: str, prompt: str) -> None:
        self._send_keys(target, prompt)
        self.sleep_fn(self.send_spacing_seconds)
        self._send_enter(target)

    def send_compact_sequence(
        self,
        target: str,
        *,
        confirmation_prompt: str,
        post_command_delay_seconds: float,
        forwarded_context: str | None = None,
    ) -> None:
        self._send_keys(target, COMPACT_INTERRUPT_KEY)
        self.sleep_fn(self.send_spacing_seconds)
        self.send_prompt(target, COMPACT_COMMAND)
        self.sleep_fn(post_command_delay_seconds)
        final_prompt = confirmation_prompt
        if forwarded_context:
            separator = ""
            if confirmation_prompt and not confirmation_prompt[-1].isspace():
                separator = " "
            final_prompt = (
                f"{confirmation_prompt}"
                f"{separator}"
                f"{COMPACT_FORWARDED_CONTEXT_PREFIX}{forwarded_context}{COMPACT_FORWARDED_CONTEXT_SUFFIX}"
            )
        self.send_prompt(target, final_prompt)

    def capture_pane(self, target: str, *, line_count: int) -> str:
        result = self._tmux(
            ["capture-pane", "-p", "-t", target, "-S", f"-{line_count}"],
            capture_output=True,
        )
        return result.stdout

    @staticmethod
    def _tmux(args: list[str], *, capture_output: bool) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["tmux", *args], check=True, text=True, capture_output=capture_output)

    def _send_keys(self, target: str, text: str) -> None:
        self._tmux(["send-keys", "-t", target, text], capture_output=False)

    def _send_enter(self, target: str) -> None:
        self._tmux(["send-keys", "-t", target, "Enter"], capture_output=False)
