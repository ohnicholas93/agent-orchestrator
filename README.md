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
