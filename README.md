# Codex Orchestrator

This is a tmux-aware CLI for pausing a Codex agent and resuming it later in the same pane.

There is no long-lived server anymore. Each `sleep` command records timer state for the current `TMUX_PANE`, then spawns a detached worker process that waits in the background and later sends:

```text
[Automated Message] Sleep complete.
```

## Install

Codex plugins are discovered through a marketplace registry file. For a home-local install, the documented marketplace path is `~/.agents/plugins/marketplace.json`.

Recommended layout:

1. Copy this repo to `~/plugins/codex-orchestrator`
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
        "path": "./plugins/codex-orchestrator"
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

All commands expect to run inside tmux so `TMUX_PANE` is available. For testing, you can override the pane manually:

```bash
python orchestrator.py sleep 600 --tmux-pane %3
python orchestrator.py get --tmux-pane %3
python orchestrator.py cancel --tmux-pane %3
```

## Behavior

1. `sleep` starts a detached worker for the current pane.
2. If that pane already has an active timer, `sleep` fails.
3. `get` reports the next wake time for the current pane, if any.
4. `cancel` cancels the active timer for the current pane.
5. When the timer expires, the worker sends the wake prompt into that pane and clears its state.

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

Cancel it:

```bash
python orchestrator.py cancel
```

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
