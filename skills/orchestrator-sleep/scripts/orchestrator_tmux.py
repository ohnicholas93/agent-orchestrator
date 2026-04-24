from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Callable

from orchestrator_constants import COMPACT_COMMAND, TMUX_SEND_SPACING_SECONDS


@dataclass
class TmuxSender:
    send_spacing_seconds: float = TMUX_SEND_SPACING_SECONDS
    sleep_fn: Callable[[float], None] = time.sleep

    def send_prompt(self, target: str, prompt: str) -> None:
        self._tmux(["send-keys", "-t", target, prompt], capture_output=False)
        self.sleep_fn(self.send_spacing_seconds)
        self._tmux(["send-keys", "-t", target, "Enter"], capture_output=False)

    def send_compact_sequence(
        self,
        target: str,
        *,
        confirmation_prompt: str,
        post_command_delay_seconds: float,
    ) -> None:
        self.send_prompt(target, COMPACT_COMMAND)
        self.sleep_fn(post_command_delay_seconds)
        self.send_prompt(target, confirmation_prompt)

    def capture_pane(self, target: str, *, line_count: int) -> str:
        result = self._tmux(
            ["capture-pane", "-p", "-t", target, "-S", f"-{line_count}"],
            capture_output=True,
        )
        return result.stdout

    @staticmethod
    def _tmux(args: list[str], *, capture_output: bool) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["tmux", *args], check=True, text=True, capture_output=capture_output)
