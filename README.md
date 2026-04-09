# Codex Orchestrator Skill Pack

This repo is an installable skill bundle.

It currently ships two skills:

- [`orchestrator-sleep`](skills/orchestrator-sleep): a tmux-aware sleep/resume workflow backed by a local Python CLI.
- [`privileged-researcher`](skills/privileged-researcher): a scratchpad-driven orchestration skill for privileged research and execution workflows.

Each `sleep` command records timer state for the current `TMUX_PANE`, then spawns a detached worker process that waits in the background and later sends:

```text
[Automated Message] Sleep complete.
```

## Install

This repo keeps bundled skills under [`skills/`](/home/nicholasoh/Workspace/Nitrous/Internal/Projects/codex-orchestrator/skills). The installer creates one symlink per skill under `~/.agents/skills/`.

```bash
bash install.sh
```

To uninstall all symlinks created for this bundle:

```bash
bash install.sh uninstall
```

That currently creates:

```text
~/.agents/skills/orchestrator-sleep -> <repo>/skills/orchestrator-sleep
~/.agents/skills/privileged-researcher -> <repo>/skills/privileged-researcher
```

If you add more skills later, rerunning `bash install.sh` will link those too. `bash install.sh uninstall` removes only matching symlinks that point back to this repo's bundled skills.

Codex detects skill changes automatically, but if an update does not appear in the current session, restart Codex.

## Skill Layout

```text
skills/
  orchestrator-sleep/
    SKILL.md
    scripts/
      orchestrator.py
  privileged-researcher/
    SKILL.md
    scratchpads/
      template.md
```

## Bundled Skills

### `orchestrator-sleep`

Use this when an agent needs to pause for a fixed duration and resume later in the same tmux pane.

### `privileged-researcher`

Use this when you want a scratchpad-first workflow for privileged or longer-running research/execution tasks. The skill requires copying the bundled scratchpad template to a task-specific path first, then using that scratchpad as the source of truth for the rest of the work.

Bundled template:

```text
skills/privileged-researcher/scratchpads/template.md
```

## Commands

The CLI keys timers by tmux pane. Only one active timer is allowed per pane.

```bash
python skills/orchestrator-sleep/scripts/orchestrator.py sleep 600
python skills/orchestrator-sleep/scripts/orchestrator.py get
python skills/orchestrator-sleep/scripts/orchestrator.py cancel
```

`sleep` and `cancel` expect to run inside tmux so `TMUX_PANE` is available. `get` behaves differently:

- In the current Codex sandbox harness, `sleep` fails early with an error telling the agent to request user escalation, because detached background workers are not reliable there.
- Inside tmux, `get` reports the pending timer for the current pane, including overdue timers that have not been processed by the worker yet.
- Outside tmux, `get` lists all pending timers in the state directory for admin use, including overdue timers that have not been processed by the worker yet, and deletes timers only after they have been overdue for more than 10 seconds.

For testing, you can override the pane manually:

```bash
python skills/orchestrator-sleep/scripts/orchestrator.py sleep 600 --tmux-pane %3
python skills/orchestrator-sleep/scripts/orchestrator.py get --tmux-pane %3
python skills/orchestrator-sleep/scripts/orchestrator.py cancel --tmux-pane %3
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
python skills/orchestrator-sleep/scripts/orchestrator.py sleep 300
```

Check it:

```bash
python skills/orchestrator-sleep/scripts/orchestrator.py get
```

List all active timers outside tmux:

```bash
env -u TMUX_PANE python skills/orchestrator-sleep/scripts/orchestrator.py get
```

Cancel it:

```bash
python skills/orchestrator-sleep/scripts/orchestrator.py cancel
```

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
