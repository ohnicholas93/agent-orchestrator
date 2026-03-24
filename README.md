# Minimal Codex Orchestrator

This is a tiny local HTTP wrapper around a live Codex CLI session running inside a tmux session.

It exposes one endpoint:

- `POST /sleep`

The endpoint accepts either:

- raw numeric body, for example `3600`
- JSON body, for example `{"seconds": 3600}`

Behavior:

1. sleep for the requested number of seconds
2. send a continuation prompt into the target tmux session
3. press `Enter`

## Run

```bash
python orchestrator.py --tmux-session tmux-codex --host 127.0.0.1 --port 8765
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
