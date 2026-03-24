# Minimal Codex Orchestrator

This is a tiny local HTTP wrapper around a Codex CLI session running inside a tmux session.

It exposes one endpoint:

- `POST /sleep`

The endpoint accepts either:

- raw numeric body, for example `3600`
- JSON body, for example `{"seconds": 3600}`

Behavior:

1. send `/status` into the target tmux session
2. robustly parse the `Session:` line from the boxed Codex status output
3. send `Ctrl-C` into the tmux session
4. sleep for the requested number of seconds
5. send `codex resume <session-id>` back into the tmux session

## Run

```bash
python orchestrator.py --tmux-session tmux-codex --host 127.0.0.1 --port 8765
```

By default, the resume command restores the parsed Codex status directory using `codex --cd <dir> --yolo resume <session-id>`.

If you want to disable that behavior, add `--no-cd`:

```bash
python orchestrator.py --tmux-session tmux-codex --host 127.0.0.1 --port 8765 --no-cd
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
