# Codex Orchestrator

A scratchpad-driven orchestration setup for running long-lived, stateful tasks inside the [Codex CLI](https://github.com/openai/codex).

## Overview

This repo provides two files that work together:

| File | Purpose |
|---|---|
| `scratchpad_template.md` | A durable operations manual template that the agent copies into your workspace and keeps up to date throughout the task. |
| `codex_prompt.md` | A two-part system prompt that bootstraps the agent and tells it to initialize from the scratchpad before doing anything else. |

The scratchpad acts as the agent's source of truth — it records paths, session names, commands, status, and notes so the agent can resume context after interruptions without losing state.

## How to Use

### 1. Copy the scratchpad template into your project

Place a copy of `scratchpad_template.md` somewhere accessible in your workspace (e.g., `~/my-project/scratchpad.md`). You don't need to fill it in — the agent will do that.

### 2. Edit `codex_prompt.md`

Open `codex_prompt.md` and make two edits:

**Part 1 — set the template path.** Replace the placeholder on line 6 with the actual path to the scratchpad template you just saved:

```
# Before
Copy `[EDIT TO PATH OF SAVED SCRATCHPAD TEMPLATE]` to the scratchpad path …

# After
Copy `~/my-project/scratchpad.md` to the scratchpad path …
```

**Part 2 — describe your task.** Append your free-form instructions after the `Part 2:` heading on line 14. Include the scratchpad path the agent should use at runtime, your task details, constraints, goals, and any relevant context. For example:

```
Part 2:

Scratchpad path: /workspace/experiments/scratchpad.md

Run a fine-tuning job on the dataset at /workspace/data/train.jsonl using the config in
/workspace/configs/base.yaml. Use tmux session "ft-run". Check loss at 500-step intervals
and stop early if it diverges. Save checkpoints to /workspace/checkpoints/.
```

### 3. Launch in Codex CLI

Feed the prompt into Codex. For example:

```bash
codex "$(cat codex_prompt.md)"
```

Or paste the contents of `codex_prompt.md` directly into the Codex CLI prompt.

### 4. Approve the agent's plan

The agent will:
1. Copy the scratchpad template to the path you specified.
2. Fill in all sections based on your task description.
3. Present its understanding and ask for **one final approval** before executing.

Review the scratchpad and confirm. The agent then operates autonomously, using the scratchpad as its durable state file.

## Scratchpad Sections

| Section | What the agent records here |
|---|---|
| **Operating Rules** | Canonical rules the agent follows (pre-filled from the template). |
| **Paths** | Key directories and files for the task. |
| **Session Names** | tmux / screen sessions the agent manages. |
| **Commands** | Exact commands used or planned, for reproducibility. |
| **Status** | Current task state — updated at every check-in. |
| **Notes** | Observations, decisions, and anything worth preserving. |

## Tips

- **Resumability.** If the session is interrupted, relaunch the same prompt. The agent reads the existing scratchpad and picks up where it left off.
- **Check-ins.** The agent supervises long jobs at quarter-interval milestones by default. Mention any custom cadence in your Part 2 instructions.
- **Safety.** The agent asks before any destructive or irreversible action. You can tighten this further by adding constraints to your Part 2 instructions.
