# Codex Orchestrator Skill Pack

This repo is an installable skill bundle.

It currently ships three skills:

- [`codex-orchestrator`](skills/codex-orchestrator): a tmux-aware sleep/resume workflow backed by a local Python CLI.
- [`privileged-automation`](skills/privileged-automation): a scratchpad-driven privileged automation skill.
- [`unprivileged-automation`](skills/unprivileged-automation): a scratchpad-driven unprivileged automation skill.

Each `sleep` command records timer state for the current `TMUX_PANE`, then spawns a detached worker process that waits in the background and later sends:

```text
[Automated Message] Sleep complete.
```

## Install

This repo keeps bundled skills under [`skills/`](/home/nicholasoh/Workspace/Nitrous/Internal/Projects/codex-orchestrator/skills). The installer creates one symlink per skill under `~/.agents/skills/`, installs a `codex-orchestrator` wrapper under `~/.local/bin/`, and ensures `~/.local/bin` is added to `PATH` idempotently in `~/.bashrc`.

```bash
./installer.sh
```

To uninstall all symlinks created for this bundle:

```bash
./installer.sh uninstall
```

That currently creates:

```text
~/.agents/skills/codex-orchestrator -> <repo>/skills/codex-orchestrator
~/.agents/skills/privileged-automation -> <repo>/skills/privileged-automation
~/.agents/skills/unprivileged-automation -> <repo>/skills/unprivileged-automation
~/.local/bin/codex-orchestrator -> wrapper script
```

If you add more skills later, rerunning `./installer.sh` will link those too. `./installer.sh uninstall` removes only matching symlinks that point back to this repo's bundled skills. The installer also cleans up legacy renamed links from older skill names.

The installer manages its own marked `~/.bashrc` PATH block for `~/.local/bin`. Uninstall is intentionally conservative:

- if `~/.local/bin/codex-orchestrator` still exists, the PATH block is retained
- if any other entry still exists in `~/.local/bin`, the PATH block is retained
- the PATH block is removed only when `~/.local/bin` appears unused by the current account

This is a deliberate policy to avoid breaking unrelated user commands in `~/.local/bin`.

Codex detects skill changes automatically, but if an update does not appear in the current session, restart Codex.

## Skill Layout

```text
skills/
  codex-orchestrator/
    SKILL.md
    scripts/
      orchestrator.py
  privileged-automation/
    SKILL.md
    scratchpads/
      template.md
  unprivileged-automation/
    SKILL.md
    scratchpads/
      template.md
```

## Bundled Skills

### `codex-orchestrator` (Codex Orchestrator)

Use this when an agent needs to pause for a fixed duration and resume later in the same tmux pane.

### `privileged-automation` (Privileged Automation)

Use this when you want a scratchpad-first workflow for privileged or longer-running research/execution tasks. The skill requires copying the bundled scratchpad template to a task-specific path first, then using that scratchpad as the source of truth for the rest of the work.

Bundled template:

```text
skills/privileged-automation/scratchpads/template.md
```

### `unprivileged-automation` (Unprivileged Automation)

Use this when you want a scratchpad-first workflow for longer-running execution tasks without privileged access.

Bundled template:

```text
skills/unprivileged-automation/scratchpads/template.md
```

## Commands

The CLI keys timers by tmux pane. Only one active timer is allowed per pane.

```bash
codex-orchestrator sleep 600
codex-orchestrator status
codex-orchestrator cancel
codex-orchestrator compact
```

`sleep`, `cancel`, and `compact` expect to run inside tmux so `TMUX_PANE` is available. `status` behaves differently:

- In the current Codex sandbox harness, `sleep` fails early with an error telling the agent to request user escalation, because detached background workers are not reliable there.
- Inside tmux, `status` reports the pending timer for the current pane, including overdue timers that have not been processed by the worker yet.
- Outside tmux, `status` lists all pending timers in the state directory for admin use, including overdue timers that have not been processed by the worker yet, and deletes timers only after they have been overdue for more than 10 seconds.
- `compact` first sends `Esc` to interrupt current work, then submits `/compact`, then sends an automated confirmation message.
- `compact -m "..."` or `compact --message "..."` appends a reminder payload to that confirmation so the post-compaction model can recover task context.

For testing, you can override the pane manually:

```bash
codex-orchestrator sleep 600 --tmux-pane %3
codex-orchestrator status --tmux-pane %3
codex-orchestrator cancel --tmux-pane %3
codex-orchestrator compact --tmux-pane %3
codex-orchestrator compact --tmux-pane %3 --message "resume from the installer task"
```

## Behavior

1. `sleep` starts a detached worker for the current pane.
2. In the current Codex sandbox harness, `sleep` fails early and tells the agent to ask the user for escalation before retrying.
3. If that pane already has an active timer, or a timer that expired less than 10 seconds ago, `sleep` fails.
4. `status` reports the pending timer for the current pane when run inside tmux, including overdue timers awaiting worker delivery.
5. `status` lists all pending timers when run outside tmux, including overdue timers awaiting worker delivery, and cleans up timers that have been stale for more than 10 seconds.
6. `cancel` cancels the active timer for the current pane.
7. `compact` sends `/compact` and then an automated context-compacted message into the same pane, optionally followed by forwarded reminder text.
8. When the timer expires, the worker sends the wake prompt into that pane and clears its state.

State files live under `$XDG_RUNTIME_DIR/codex-orchestrator` when available, otherwise under the system temp directory.

## Example

Start a sleep timer:

```bash
codex-orchestrator sleep 300
```

Check it:

```bash
codex-orchestrator status
```

List all active timers outside tmux:

```bash
env -u TMUX_PANE codex-orchestrator status
```

Cancel it:

```bash
codex-orchestrator cancel
```

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
