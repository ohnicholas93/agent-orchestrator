---
name: Orchestrator Sleep
description: Use when a Codex agent needs to suspend work for a period and resume later through the local tmux-backed Codex Orchestrator server. Covers starting the server in tmux, issuing POST /sleep requests, and understanding tmux auto-detection.
---

# Orchestrator Sleep

This skill uses the local `codex-orchestrator` plugin to pause an agent and resume it later.

## When to use

- Agent needs to sleep for a fixed duration and continue later.
- The current Codex session is running inside tmux and should be resumed automatically.

## Workflow

1. Confirm whether the local orchestrator server is already running. The server should remain alive while the agent is sleeping, so run it inside its own tmux session.
2. If it is not running, start it with a single command from the plugin root:

```bash
tmux new-session -d -s codex-orchestrator 'cd /path/to/codex-orchestrator && python orchestrator.py --host 127.0.0.1 --port 8765'
```

Adjust the path to plugin root as needed. If tmux access is blocked by sandboxing, request escalation so the user can approve the tmux command or run it themselves.

3. From the tmux pane where the Codex agent is running, ask the server to sleep:

```bash
curl -X POST http://127.0.0.1:8765/sleep \
  -H 'Content-Type: application/json' \
  -d '{"seconds": 300}'
```

4. After sending the REST request, stop responding immediately. Do not keep working, add commentary, or send extra messages. Wait for the server to reprompt the your harness with:

```text
[Automated Message] Sleep complete.
```

5. When that automated message appears, continue the task as required.

6. By default the server inspects all tmux panes, finds the pane that most recently issued a `/sleep` request, and sends the wake message back to that pane.

## Notes

- Use `--tmux-target` only when auto-detection is not appropriate.
- Auto-detection inspects recent tmux pane history, so the `/sleep` REST API call should still be visible in scrollback.