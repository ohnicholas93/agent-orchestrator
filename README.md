# Codex Orchestrator

This is a tmux-aware CLI for pausing a Codex agent and resuming it later in the same pane.

Each `sleep` command records timer state for the current `TMUX_PANE`, then spawns a detached worker process that waits in the background and later sends:

```text
[Automated Message] Sleep complete.
```

## Install

Codex plugins are discovered through a marketplace registry file. For a home-local install, the documented marketplace path is `~/.agents/plugins/marketplace.json`.

Recommended layout:

1. Copy this repo to `~/codex-plugins/codex-orchestrator`
2. Create `~/.agents/plugins/marketplace.json`
3. Register the plugin as a local source
4. Start a new Codex session so plugin discovery reloads

Example marketplace file:

```json
{
  "name": "local-plugins",
  "interface": {
    "displayName": "Local Plugins"
  },
  "plugins": [
    {
      "name": "codex-orchestrator",
      "source": {
        "source": "local",
        "path": "./codex-plugins/codex-orchestrator"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Utilities"
    }
  ]
}
```

Notes:

- The plugin manifest lives at [`.codex-plugin/plugin.json`](/home/nicholasoh/Workspace/Nitrous/Internal/Projects/codex-orchestrator/.codex-plugin/plugin.json)
- The bundled skill lives at [`skills/codex-orchestrator/SKILL.md`](/home/nicholasoh/Workspace/Nitrous/Internal/Projects/codex-orchestrator/skills/codex-orchestrator/SKILL.md)

## Commands

The CLI keys timers by tmux pane. Only one active timer is allowed per pane.

```bash
python orchestrator.py sleep 600
python orchestrator.py get
python orchestrator.py cancel
```

`sleep` and `cancel` expect to run inside tmux so `TMUX_PANE` is available. `get` behaves differently:

- In the current Codex sandbox harness, `sleep` fails early with an error telling the agent to request user escalation, because detached background workers are not reliable there.
- Inside tmux, `get` reports the pending timer for the current pane, including overdue timers that have not been processed by the worker yet.
- Outside tmux, `get` lists all pending timers in the state directory for admin use, including overdue timers that have not been processed by the worker yet, and deletes timers only after they have been overdue for more than 10 seconds.

For testing, you can override the pane manually:

```bash
python orchestrator.py sleep 600 --tmux-pane %3
python orchestrator.py get --tmux-pane %3
python orchestrator.py cancel --tmux-pane %3
```

## Behavior

1. `sleep` starts a detached worker for the current pane.
2. In the current Codex sandbox harness, `sleep` fails early and tells the agent to ask the user for escalation before retrying.
3. If that pane already has an active timer, or a timer that expired less than 10 seconds ago, `sleep` fails.
4. `get` reports the pending timer for the current pane when run inside tmux, including overdue timers awaiting worker delivery.
5. `get` lists all pending timers when run outside tmux, including overdue timers awaiting worker delivery, and cleans up timers that have been stale for more than 10 seconds.
6. `cancel` cancels the active timer for the current pane.
7. When the timer expires, the worker sends the wake prompt into that pane and clears its state.

State files live under `$XDG_RUNTIME_DIR/codex-orchestrator` when available, otherwise under the system temp directory.

## Example

Start a sleep timer:

```bash
python orchestrator.py sleep 300
```

Check it:

```bash
python orchestrator.py get
```

List all active timers outside tmux:

```bash
env -u TMUX_PANE python orchestrator.py get
```

Cancel it:

```bash
python orchestrator.py cancel
```

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
