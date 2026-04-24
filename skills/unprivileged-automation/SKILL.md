---
name: Unprivileged Automation
description: Use when a Codex agent needs a scratchpad-driven workflow for execution tasks in a live workspace without privileged access, especially when the user wants explicit scope tracking, durable notes, planned check-ins, and a final approval gate before autonomous execution.
---

# Unprivileged Automation

Use this skill for orchestrating tasks where the agent should work from a durable scratchpad and proceed autonomously, cautiously, under normal sandboxed or limited-access conditions.

## When to use

- The task is long-running, research-related, or operationally sensitive.
- The user wants a scratchpad to track scope, commands, session names, status, and notes.
- The task may involve restricted commands or sandbox limits. Prefer non-escalated approaches first, but go ahead and request user-approved escalation when the task genuinely requires it.

## Workflow

1. Copy `~/.agents/skills/unprivileged-automation/scratchpads/template.md` to the scratchpad path provided by the user.
2. If the user did not provide a scratchpad path, ask for one before proceeding.
3. Immediately edit the copied scratchpad so it reflects the current task, scope, paths, sessions, commands, status, and notes.
4. Read the scratchpad's `Operating Rules` section and adopt it as the canonical local operations manual for the task.
5. Treat the user's request as free-form context. Extract the real task, constraints, goals, risks, any access limits, and current status, then normalize them into the scratchpad.
6. Before proceeding autonomously, confirm your understanding and ask the user for one final approval before execution.
7. Use the scratchpad as the source of truth for the rest of the task.

## Operating Notes

- Stay within the user-approved scope.
- Assume limited permissions by default; prefer sandbox-safe and non-destructive actions first.
- Prefer non-escalated approaches first. When escalation is genuinely required to complete the task, go ahead and request user approval.
- Ask before dangerous, irreversible, high-impact, or privilege-requiring actions.
- Prefer durable logs and checkpoint-aware relaunches. You MUST use tmux for long-running work, and should request escalation to launch tmux if the environment prevents it.
- Keep context lean by updating the scratchpad instead of restating operational state in chat.
- For long waits, use the local `Orchestrator Sleep` skill instead of harness sleep timers.

## Bundled Resource

Scratchpad template:

```text
~/.agents/skills/unprivileged-automation/scratchpads/template.md
```
