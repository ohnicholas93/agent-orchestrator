---
name: Privileged Automation
description: Use when a Codex agent needs a scratchpad-driven workflow for privileged execution tasks in a live workspace, especially when the user wants explicit scope tracking, durable notes, planned check-ins, and a final approval gate before autonomous execution.
---

# Privileged Automation

Use this skill for orchestrating tasks where the agent should work from a durable scratchpad and proceed autonomously, cautiously, with elevated or high-impact operations.

## When to use

- The task is long-running, research-related, or operationally sensitive.
- The user wants a scratchpad to track scope, commands, session names, status, and notes.
- The task may involve privileged execution or supervision of ongoing runs.

## Workflow

1. Copy `~/.agents/skills/privileged-automation/scratchpads/template.md` to the scratchpad path provided by the user.
2. If the user did not provide a scratchpad path, ask for one before proceeding.
3. Immediately edit the copied scratchpad so it reflects the current task, scope, paths, sessions, commands, status, and notes.
4. Read the scratchpad's `Operating Rules` section and adopt it as the canonical local operations manual for the task.
5. Treat the user's request as free-form context. Extract the real task, constraints, goals, risks, and current status, then normalize them into the scratchpad.
6. Before proceeding autonomously, confirm your understanding and ask the user for one final approval before execution.
7. Use the scratchpad as the source of truth for the rest of the task.

## Operating Notes

- Stay within the user-approved scope.
- Ask before dangerous, irreversible, or high-impact actions.
- Prefer durable logs, checkpoint-aware relaunches, and detached tmux sessions for long work.
- Keep context lean by updating the scratchpad instead of restating operational state in chat.
- For long waits, use the local `Codex Orchestrator` skill instead of harness sleep timers.

## Bundled Resource

Scratchpad template:

```text
~/.agents/skills/privileged-automation/scratchpads/template.md
```
