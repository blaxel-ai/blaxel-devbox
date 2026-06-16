# Blaxel devbox

A disposable cloud sandbox that runs *your* stack, with an AI agent working inside it — your tools, your CLIs, your browser. Credentials injected at runtime (never baked), a live preview URL, full logs, and a clean teardown. Re-skin it for whatever you build.

## Plug it into your own agent

The best way to use this is plug-and-play: clone the repo and open it in your coding agent (Claude Code, Codex, Cursor, …).

**👉 Paste this into your agent, then finish the last line with what you want your devbox to do:**

```text
You're helping me build on this repo.
It's a Blaxel devbox: an AI agent runs inside an isolated, disposable sandbox.
The sandbox is loaded with my own toolkit.

Read these first:
- AGENTS.md — how it's built and the invariants
- README.md — what it is and how to run it
- devbox/Dockerfile — the toolkit (the agent's tools)
- devbox.py — the kit (small SDK helpers)
- launch.py — the recipe (the end-to-end flow)

Keep these invariants:
- Never bake secrets into the image or repo — inject them at runtime
- Pass ports explicitly and bind 0.0.0.0 (the sandbox sets PORT=80)
- Keep the image linux/amd64 and the sandbox-api COPY line

Build and verify:
- Build the image: bl deploy
- Run it end-to-end: python launch.py
- Confirm it works before telling me it's done

Here's what I want this dev box to do:
```

Vanilla cloud agents (Codex's cloud, Cursor's) drop the agent on a generic box: not your tools, not your environment, nothing safe to hold a credential. This gives the agent a *real* box — your stack — inside an isolated sandbox you can audit and throw away.

This repo is a **base layer**, not a one-off demo. The image is the substrate you re-skin with your own toolkit; the orchestration is a small kit you build on.

## Keys you need

Set these up once before running:

| What | Why | Where |
| --- | --- | --- |
| **Blaxel workspace + `bl` CLI** | runs the sandbox (no local Docker — images build remotely) | [blaxel.ai](https://blaxel.ai) — install `bl`, then `bl login` |
| **`ANTHROPIC_API_KEY`** | powers Claude Code, the agent inside the box | [console.anthropic.com](https://console.anthropic.com) |
| **`OP_SERVICE_ACCOUNT_TOKEN`** _(optional)_ | only for adapted tasks that pull real secrets via 1Password; inject it at runtime, never bake it | [1Password service accounts](https://developer.1password.com/docs/service-accounts/) |

You'll also need **Python 3** locally to run the launcher. You do **not** need local Docker to build this image; `bl deploy` builds it remotely on Blaxel. The image includes the Docker CLI for the agent, but not a Docker daemon by default (see [stack notes](./docs/stack-notes.md#docker-inside-the-box)).

## The agent's toolkit

The default [`devbox/Dockerfile`](./devbox/Dockerfile) bakes a working toolkit — these are just defaults, swap in whatever you use:

- **Claude Code CLI** — the agent that runs inside the box.
- **Vercel agent-browser** — headless Chrome built for agents, to drive real web flows.
- **Docker CLI** — build and run containerized tools when a Docker daemon is configured; the daemon is not on by default (see stack notes).
- **1Password CLI (`op`)** — pull credentials at runtime when you inject a service-account token; nothing baked into the image.
- Dev essentials — git, Python, Node, curl, jq, ripgrep, build tools.

Every line is a tool in the agent's hands. Add your own CLIs, runtimes, or scanners, swap the browser — that's the point.

## How it's laid out

| Path | What it is |
| --- | --- |
| [`devbox/`](./devbox) | **The base layer.** The agent's toolkit, baked into a Blaxel sandbox image. |
| [`devbox.py`](./devbox.py) | **The kit.** Small SDK helpers — `provision`, `run`, `serve`, `preview`, `run_agent`, `read_file`, `clone`. |
| [`launch.py`](./launch.py) | **One recipe:** provision → serve something → hand the box to the agent → surface results → tear down. |
| [`examples/assessment-task.md`](./examples/assessment-task.md) | The example agent task. Swap it for your own. |
| [`examples/target-app/`](./examples/target-app) | A tiny, intentionally-vulnerable demo target for the example. |
| [`docs/security-model.md`](./docs/security-model.md) | Isolation, runtime secret injection + wipe, auditability, lifecycle. |
| [`docs/stack-notes.md`](./docs/stack-notes.md) | Extending the agent's toolkit; Docker daemon; safe 1Password injection. |

## Quickstart

```bash
# 1. install the launcher's Python deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. add your keys, then load them into this shell
cp .env.example .env           # edit .env: set BL_WORKSPACE and ANTHROPIC_API_KEY
set -a; source .env; set +a    # export everything in .env into this shell

# 3. build the devbox image once (remote build on Blaxel — no local Docker)
cd devbox && bl deploy && cd ..
until DEVBOX_IMAGE=$(bl get sandbox blaxel-devbox -ojson | jq -r '.[0].spec.runtime.image // empty') && [ -n "$DEVBOX_IMAGE" ]; do sleep 5; done
export DEVBOX_IMAGE

# 4. launch: spin up the box, run the agent, print a preview URL
python launch.py
```

## What the demo shows

Out of the box, `python launch.py` runs one quick end-to-end example so you can *see* the devbox work. The bundled example is a **security assessment** — a clean showcase of the browser + injected-credential + report loop — but it's just one example; swap it for whatever you do (see [Make it yours](#make-it-yours)). Here's what happens:

- **A fresh, disposable sandbox** spins up from your image, with the toolkit baked in.
- **A demo target — “Northwind Console” — starts inside it.** It's a tiny, intentionally-vulnerable web app (a fake internal admin login) that ships in [`examples/target-app/`](./examples/target-app) purely as something for the agent to assess. It is *not* part of the devbox — just the subject. Don't reuse its code; it's deliberately insecure.
- **A login is injected at runtime.** `launch.py` generates a one-off username/password and hands it to the box the same way you'd inject a 1Password-sourced secret in production. So the agent logs into Northwind Console like a real user, and nothing is baked into the image. You'll see a real login screen at the preview URL — the agent has the password, you don't need it.
- **The agent (Claude Code) does the work, headless:** it authenticates with agent-browser, probes the app, and writes a findings report to `/workspace/report.md` (printed back at the end). On this target it reliably finds an unauthenticated endpoint leaking secrets, a reflected-XSS bug, and a static session token — each with evidence and a fix.
- **You can watch and step in:** a live preview URL for the target, and `bl connect sandbox blaxel-devbox-demo` to drop into the exact same box. It tears down at the end.

The point isn't the security scan — it's that an agent did real work *inside your stack*, in an isolated box you can watch, inspect, and throw away. Every part of it is swappable.

## Prove it before sharing

Use this checklist before handing the repo to another team, reviewer, or recorder:

1. **Remote image build:** after any image change, run `cd devbox && bl deploy && cd ..`; this proves the Dockerfile builds on Blaxel without local Docker.
2. **Preview smoke:** set `DEVBOX_IMAGE` with the Quickstart wait loop above, then run `python launch.py --name blaxel-devbox-smoke --no-agent --keep`; open the preview URL and confirm the Northwind login loads.
3. **Toolkit proof inside the kept box:** `bl connect sandbox blaxel-devbox-smoke`, then run:

   ```bash
   claude --version
   command -v agent-browser && agent-browser --help >/tmp/agent-browser-help.txt
   docker --version
   op --version
   ```

   `docker info` is expected to fail unless you configured a daemon; the default image proves the CLI is present, not that nested Docker is running.
4. **Clean up the smoke box:** `bl delete sandbox blaxel-devbox-smoke` before the full run, so process names and ports start fresh.
5. **Full agent run:** run `python launch.py`; confirm the preview URL prints, Claude Code writes `/workspace/report.md`, the report is printed locally, and the box is deleted unless you pass `--keep`.
6. **Recording hygiene:** show the terminal flow, preview, report, and cleanup. Do not show `.env`, API keys, 1Password output, private target data, or internal tracking metadata.
7. **Follow-up-ready facts:** capture the exact run outcome, whether the sandbox was deleted or kept, and any unrun hosted gates. Keep external updates to one outcome line plus one blocker/action line.

## Make it yours

The demo is just one example — every piece is swappable:

- **Your task** → tell your agent what you want (the paste-in block at the top), or edit [`examples/assessment-task.md`](./examples/assessment-task.md) / pass `--task-file`.
- **Your target** → `python launch.py --repo https://github.com/you/app --task-file your-task.md` to point at your own **authorized** target instead of Northwind Console.
- **Your toolkit** → add scanners, CLIs, or runtimes to [`devbox/Dockerfile`](./devbox/Dockerfile) and `bl deploy` again — the agent's whole world changes.
- **Your secrets** → keep `OP_SERVICE_ACCOUNT_TOKEN` local, inject it into the sandbox at runtime with `run(..., env=...)` or `run_agent(..., extra_env=...)`, then let the agent `op read` / `op run` what it needs. The stock demo generates a fake login instead.
- **Your agent** → swap `run_agent()` in [`devbox.py`](./devbox.py); the rest of the kit stays the same.

It doesn't have to be security work at all — point the toolkit and the task at whatever you do.

## Security

The agent runs without approval prompts and the box marks itself a sandbox (`IS_SANDBOX=1`) — safe **only** because each run is an isolated, disposable sandbox. Credentials are injected at runtime, sourced from a file in the box, and wiped when the command finishes — never baked into the image or passed inline. Preview URLs and reports can still expose target behavior, so use authorized targets and don't share links or artifacts casually. The bundled target is intentionally vulnerable and self-contained. Full details in [`docs/security-model.md`](./docs/security-model.md).
