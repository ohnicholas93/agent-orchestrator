---
name: codex-orchestrator
description: Use when a Codex agent needs to suspend work for a period and resume later through the local tmux-backed Codex Orchestrator server. Covers starting the server, issuing POST /sleep requests, and understanding tmux auto-detection.
---

# Codex Orchestrator

This skill uses the local `codex-orchestrator` plugin to pause an agent and resume it later.

## When to use

- The user wants an agent to sleep for a fixed duration and continue later.
- The current Codex session is running inside tmux and should be resumed automatically.
- You need to inspect or explain how the orchestrator chooses which tmux pane to resume.

## Workflow

1. Confirm whether the local orchestrator server is already running.
2. If needed, start the orchestrator **in tmux for persistence** (name it `codex-orchestrator`) from the plugin root:

```bash
python orchestrator.py --host 127.0.0.1 --port 8765
```

3. Ask the server to sleep:

```bash
curl -X POST http://127.0.0.1:8765/sleep \
  -H 'Content-Type: application/json' \
  -d '{"seconds": 300}'
```

4. By default the server inspects all tmux panes, finds the pane that most recently issued a `/sleep` request, and sends the continuation prompt back to that pane.

## Notes

- Use `--tmux-target` only when auto-detection is not appropriate.
- Auto-detection inspects recent tmux pane history, so the `/sleep` command should still be visible in scrollback.
- The continuation prompt text is defined in `../../orchestrator.py`.
