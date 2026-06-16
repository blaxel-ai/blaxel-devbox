# Security model

Why a security team can trust running agents in here. The devbox is built so an autonomous agent can do real work without becoming a liability.

## Isolation

Every run is a fresh, disposable Blaxel sandbox (a microVM). The sandbox's filesystem and processes are discarded when you delete the box, so nothing bleeds across targets or tasks. (Logs and process records are kept for audit, any external side effects are separate, and `--keep` intentionally leaves the box running.) Run one box per target or task.

## Secrets: injected, used, wiped — never baked

No secret lives in this repo or in the image. The kit's `run(..., env={...})` writes credentials to a file *inside the box*, sources it, and deletes it (a shell `trap`) when the command finishes. Secrets never appear in the image, the command string, or process args.

In production, those values come from **1Password**: inject `OP_SERVICE_ACCOUNT_TOKEN` at runtime (for example with `run(..., env=...)` / `run_agent(..., extra_env=...)`) and let the agent pull what it needs with `op read` / `op run`. The injection-and-wipe path is identical; only the source changes. The stock demo does not need a 1Password token because it generates a one-off target login per run.

## Auditability

Every run is inspectable: process records and logs for each command, a preview URL to see what the target served, and the agent's findings report as a concrete artifact. You can see *where* the work ran — not just that the agent said it ran.

Audit artifacts can include target behavior and findings. Treat preview URLs, logs, and `/workspace/report.md` as sensitive when you point the devbox at real systems, and avoid putting raw secrets into prompts, reports, filenames, or public follow-up notes.

## Lifecycle and control

Explicit create → run → inspect → delete. `bl connect` drops you into the exact box the agent used; `bl delete` tears it down. Nothing keeps running unless you ask it to (`--keep`).

## Blast radius

The agent runs with `claude --print --dangerously-skip-permissions` (no prompts) and the image sets `IS_SANDBOX=1`. That's acceptable **only** because the box is isolated and disposable. Keep it that way: scope credentials to least privilege, keep them short-lived, point the agent at authorized targets, and tear the box down when done.

The image proves a toolkit, not unlimited runtime privileges: Docker's CLI is installed, but a Docker daemon must be explicitly configured if a task needs nested/containerized execution; `op` is installed, but it cannot read real secrets until a service-account token is injected at runtime.
