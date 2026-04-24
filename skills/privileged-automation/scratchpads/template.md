# Agentic Codex Scratchpad

Date: [ADJUST ACCORDINGLY]
Scope: [ADJUST ACCORDINGLY]

## Operating Rules

- Stay within scope and protect state: do not do anything outside the explicitly provided scope, and do not delete, overwrite, reset, reclaim, or otherwise disturb anything meaningful unless explicitly approved by the user. Ask before any dangerous, irreversible, or high-impact action. Do not access the internet without user permission.
- Keep execution durable and context lean: prefer resumable commands, checkpoint-aware relaunches, durable logs, and detached tmux sessions. Use the scratchpad as the source of truth. Inspect logs in narrow windows with targeted commands so context stays small.
- Use hardware pragmatically: schedule available GPUs efficiently and prefer better utilization when the gain is obvious, but do not thrash. If improving utilization would require stopping and rerunning, weigh the expected gain against restart/setup cost, preserve scientific consistency when settings should stay comparable across runs or experts, and avoid repeated retries when better utilization is clearly not practical.
- Supervise runs like a senior operator: at early and planned check-ins, judge the full setup and observed behavior together. This includes hyperparameters, total steps, save/log/eval cadence, batch sizing, accumulation, learning-rate schedule, checkpoint policy, resource utilization, numerical stability, loss progression, and whether the training dynamics look scientifically sensible and observable enough to support trust in the result. If the setup or behavior is obviously wrong, poorly instrumented, or unlikely to yield a trustworthy outcome, stop and fix it early rather than letting a bad run continue.
- Wait intelligently: for long jobs, prefer a small number of planned supervisory checks, roughly quarter-interval milestones unless earlier signals justify checking sooner.
- Sleep via the local `Codex Orchestrator` ONLY, not harness timers. Treat this as the durable wakeup path for long waits instead of spawning shell `sleep` processes from the harness. NEVER use harness timers (exec_command with sleep) for sleeps; they are not reliable.
- Initialize from the scratchpad first: after copying this template locally, fill it in before substantial work and then treat its rules as the durable local operations manual for the rest of the task.

## Paths

[ADJUST ACCORDINGLY]

## Session Names

[ADJUST ACCORDINGLY]

## Commands

[ADJUST ACCORDINGLY]

## Status

[ADJUST ACCORDINGLY]

## Notes

[ADJUST ACCORDINGLY]
