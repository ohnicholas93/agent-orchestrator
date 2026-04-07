# Codex Orchestrator

This is a tiny local HTTP wrapper around live Codex CLI sessions running inside tmux.

The repo now also includes Codex packaging metadata:

- a distributable plugin manifest at [`.codex-plugin/plugin.json`](/home/nicholasoh/Workspace/Nitrous/Internal/Projects/agent-orchestrator/.codex-plugin/plugin.json)
- a skill at [`skills/codex-orchestrator/SKILL.md`](/home/nicholasoh/Workspace/Nitrous/Internal/Projects/agent-orchestrator/skills/codex-orchestrator/SKILL.md)

It exposes one endpoint:

- `POST /sleep`

The endpoint accepts either:

- raw numeric body, for example `3600`
- JSON body, for example `{"seconds": 3600}`

Behavior:

1. sleep for the requested number of seconds
2. auto-detect the tmux pane that most recently called `/sleep` unless an explicit target is configured
3. send a continuation prompt into that tmux pane
4. press `Enter`

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

- The plugin manifest lives at [`.codex-plugin/plugin.json`](/home/nicholasoh/Workspace/Nitrous/Internal/Projects/agent-orchestrator/.codex-plugin/plugin.json)
- The bundled skill lives at [`skills/codex-orchestrator/SKILL.md`](/home/nicholasoh/Workspace/Nitrous/Internal/Projects/agent-orchestrator/skills/codex-orchestrator/SKILL.md)
- The plugin becomes discoverable through `marketplace.json`, but the Python server does not auto-start

## Run

```bash
python orchestrator.py --host 127.0.0.1 --port 8765
```

To force a specific tmux target instead of auto-detecting:

```bash
python orchestrator.py --host 127.0.0.1 --port 8765 --tmux-target tmux-codex
```

## Example Request

```bash
curl -X POST http://127.0.0.1:8765/sleep -d '3600'
```

or

```bash
curl -X POST http://127.0.0.1:8765/sleep \
  -H 'Content-Type: application/json' \
  -d '{"seconds": 3600}'
```

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

## Activation And Testing

1. Start the server from the plugin root:

```bash
python orchestrator.py --host 127.0.0.1 --port 8765
```

2. In a tmux pane running Codex, call the sleep endpoint:

```bash
curl -X POST http://127.0.0.1:8765/sleep \
  -H 'Content-Type: application/json' \
  -d '{"seconds": 5}'
```

3. Wait for the requested duration and verify that the continuation prompt is sent back into the pane that made the request.

If you want deterministic routing while testing, bypass auto-detection and pin the target:

```bash
python orchestrator.py --host 127.0.0.1 --port 8765 --tmux-target <pane-or-session>
```
