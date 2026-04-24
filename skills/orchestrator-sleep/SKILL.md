---
name: Orchestrator Sleep
description: Use when a Codex agent needs to pause for a fixed duration and resume later in the same tmux pane. Covers the process-based Codex Orchestrator CLI and its sleep, status, cancel, and compact commands.
---

# Orchestrator Sleep

This skill bundles its own local Python script to pause an agent and resume it later.

## When to use

- Agent needs to sleep for a fixed duration and continue later.
- The current Codex session is running inside tmux and should be resumed automatically.

## Workflow

1. Run the bundled sleep entrypoint from the same tmux pane as the agent:

```bash
python ~/.agents/skills/orchestrator-sleep/scripts/orchestrator.py sleep 300
```

This command uses `TMUX_PANE`, records the timer for that pane, and spawns a detached worker process.

2. After sending the sleep command, stop responding immediately. Do not keep working, add commentary, or send extra messages.

3. If needed, inspect timer status for the current pane:

```bash
python ~/.agents/skills/orchestrator-sleep/scripts/orchestrator.py status
```

4. If needed, cancel the active timer for the current pane:

```bash
python ~/.agents/skills/orchestrator-sleep/scripts/orchestrator.py cancel
```

5. If needed, compact model context for the current pane:

```bash
python ~/.agents/skills/orchestrator-sleep/scripts/orchestrator.py compact
```

6. Wait for the worker to reprompt the same tmux pane with:

```text
[Automated Message] Sleep complete.
```

7. When that automated message appears, continue the task as required.

## Notes

- Only one active timer is allowed per tmux pane.
- The commands expect to run inside tmux so `TMUX_PANE` is available.
- For testing, `~/.agents/skills/orchestrator-sleep/scripts/orchestrator.py` also accepts `--tmux-pane` to override the pane explicitly.
