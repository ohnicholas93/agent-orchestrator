from __future__ import annotations


CONTINUE_PROMPT = "[Automated Message] Sleep complete. "
COMPACT_COMMAND = "/compact"
COMPACT_CONFIRMATION_PROMPT = "[Automated Message] Context compacted. "
COMPACT_FORWARDED_CONTEXT_PREFIX = (
    'The message below was forwarded by you, prior to compaction, to remind you of your current context.\n\n"'
)
COMPACT_FORWARDED_CONTEXT_SUFFIX = '"'
COMPACT_INTERRUPT_KEY = "Escape"
STALE_TIMER_GRACE_SECONDS = 10.0
CONTEXT_WARNING_THRESHOLD_PERCENT = 30
CONTEXT_CAPTURE_LINE_COUNT = 200
TMUX_SEND_SPACING_SECONDS = 0.5
COMPACT_POST_COMMAND_DELAY_SECONDS = 0.5
