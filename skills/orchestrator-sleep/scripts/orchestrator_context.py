from __future__ import annotations

import re

from orchestrator_constants import CONTEXT_CAPTURE_LINE_COUNT
from orchestrator_tmux import TmuxSender


_CONTEXT_REMAINING_PATTERN = re.compile(r"Context\s+(\d{1,3})%\s+left", re.IGNORECASE)


def parse_context_remaining_percent(captured_output: str) -> int | None:
    if not isinstance(captured_output, str):
        return None
    matches = list(_CONTEXT_REMAINING_PATTERN.finditer(captured_output))
    if not matches:
        return None
    try:
        remaining = int(matches[-1].group(1))
    except (TypeError, ValueError):
        return None
    if remaining < 0 or remaining > 100:
        return None
    return remaining


def read_context_remaining_percent(sender: TmuxSender, pane_id: str) -> int | None:
    try:
        captured_output = sender.capture_pane(pane_id, line_count=CONTEXT_CAPTURE_LINE_COUNT)
    except Exception:
        return None
    return parse_context_remaining_percent(captured_output)
