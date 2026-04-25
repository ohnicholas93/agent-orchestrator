---
name: Codex Orchestrator
description: Use when a Codex agent needs to manage tmux-pane orchestration tasks through the Codex Orchestrator CLI. Covers three core concepts -> sleep/cancel, status, and compact.
---

# Codex Orchestrator

This skill bundles its own local Python script for tmux-pane orchestration tasks. The supported commands fall into three related but distinct modes:

- `sleep` / `cancel`: manage a delayed resume flow for the current tmux pane.
- `status`: inspect timer state for the current pane or list active timers.
- `compact`: ask Codex to compact model context in the current pane.

## When to use

- Agent needs to sleep for a fixed duration and continue later.
- Agent needs to inspect orchestrator timer state.
- Agent needs to compact model context in the current tmux pane.
- The current Codex session is running inside tmux.

## Sleep / Cancel

Use this path when the agent should pause and resume later in the same tmux pane.

1. Run the bundled sleep entrypoint from the same tmux pane as the agent:

```bash
codex-orchestrator sleep 300
```

This command uses `TMUX_PANE`, records the timer for that pane, and spawns a detached worker process.

2. After sending the sleep command, stop responding immediately. Do not keep working, add commentary, or send extra messages.

3. Wait for the worker to reprompt the same tmux pane with:

```text
[Automated Message] Sleep complete.
```

4. When that automated message appears, continue the task as required.

Note: If needed, cancel the active timer for the current pane:

```bash
codex-orchestrator cancel
```

## Status

Use this path when the agent only needs timer state. This is separate from both sleeping and compacting.

1. Inspect timer status for the current pane:

```bash
codex-orchestrator status
```

## Compact

Use this path when the agent needs to compact Codex model context in the current tmux pane. This is not dependent on sleep or status.

1. Trigger compaction for the current pane:

```bash
codex-orchestrator compact
```

Note: You are encouraged to hand a reminder to your post-compaction model context by using the `--forwarded-context` CLI argument:

```bash
codex-orchestrator compact --forwarded-context "current situation, remaining things to do, scratchpad path, etc"
```

## Notes

- Only one active timer is allowed per tmux pane.
- The commands expect to run inside tmux so `TMUX_PANE` is available.
