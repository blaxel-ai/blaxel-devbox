# AGENTS.md

Guidance for anyone — human or AI agent — cloning this repo to build their own Blaxel devbox. Read this before changing things: it explains what the pieces are, how to extend them, and the invariants that keep the demo working. `README.md` is the product framing and quickstart; this file is the "how to work in and extend the code" guide.

## What this is

A **base layer** for running AI agents inside isolated, disposable [Blaxel](https://blaxel.ai) sandboxes that carry *your* toolkit. The bundled demo is a security-assessment agent: it serves an intentionally-vulnerable target, the agent authenticates with a runtime-injected credential, probes it with a headless browser, and writes a findings report — all in a throwaway sandbox with a live preview URL.

Clone it and re-skin the image, the task, and the target for whatever your agents actually do.

## The three pieces (how it fits together)

1. **The image — `devbox/`** — your toolkit, baked once into a Blaxel sandbox image (`Dockerfile` + `blaxel.toml` + `entrypoint.sh`). This is the agent's whole world; swap tools here. Bakes Claude Code, Vercel agent-browser (headless Chrome), Docker CLI, 1Password CLI (`op`), and dev essentials.
2. **The kit — `devbox.py`** — small, readable Blaxel SDK helpers: `provision`, `run`, `serve`, `preview`, `run_agent`, `read_file`, `clone`. Build on these or copy them into your project.
3. **The recipe — `launch.py`** — one end-to-end flow built on the kit: provision → serve a target → inject creds → run the agent → surface the report → tear down. Read it top-to-bottom; copy and adapt it.

Supporting files:
- `examples/assessment-task.md` — the agent's task. Swap for your own.
- `examples/target-app/` — a tiny **intentionally-vulnerable** demo target (training-only, self-contained).
- `docs/security-model.md` — isolation, secret injection/wipe, auditability, lifecycle.
- `docs/stack-notes.md` — extending the toolkit, the Docker daemon, 1Password, ports.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env        # BL_WORKSPACE + ANTHROPIC_API_KEY (BL_API_KEY optional if you `bl login`)
set -a; source .env; set +a
cd devbox && bl deploy && cd ..
until DEVBOX_IMAGE=$(bl get sandbox blaxel-devbox -ojson | jq -r '.[0].spec.runtime.image // empty') && [ -n "$DEVBOX_IMAGE" ]; do sleep 5; done
export DEVBOX_IMAGE
python launch.py
```

`bl deploy` builds **remotely** on Blaxel — no local Docker daemon is needed.

## How to build on it

- **Add tools to the agent:** add a line to `devbox/Dockerfile`, then `bl deploy` and refresh `DEVBOX_IMAGE` (add scanners, language runtimes, your internal CLIs).
- **Point at your own target/repo:** `python launch.py --repo <url> --task-file <your-task.md>`. Only assess targets you are authorized to.
- **Change the task:** edit `examples/assessment-task.md` or pass `--task-file`.
- **Bring your own secrets:** keep `OP_SERVICE_ACCOUNT_TOKEN` local, pass it into the box with `run(..., env=...)` / `run_agent(..., extra_env=...)`, and pull with `op read` / `op run` in the task. The stock demo does not need 1Password; it generates a one-off target login.
- **Swap the agent:** replace `run_agent()` in `devbox.py`; the rest of the kit is unchanged.

## Invariants — don't break these

- **Secrets never get baked.** No secret belongs in the repo or the image. Inject at runtime through `run(env=...)`: the kit writes them to a file in the box, sources it, and **deletes that file immediately** (with a `trap` as fallback). Production secrets come from 1Password; the injection path is identical.
- **Pass ports explicitly.** The sandbox sets `PORT=80`. A server that reads `$PORT` will bind 80 and the preview (on `:3000`) will never reach it — you'll see a `wait_for_ports` 504 / preview 502 with no obvious cause. Pass the port as an argument (the demo runs `server.py 3000`), bind `0.0.0.0` (not `localhost`), and keep the port consistent across the server, `serve()`, and `blaxel.toml`. `80`, `443`, and `8080` are reserved by Blaxel.
- **Keep the image a Blaxel sandbox.** Keep `linux/amd64` and the `COPY --from=ghcr.io/blaxel-ai/sandbox:latest /sandbox-api ...` line — that binary serves the filesystem/process/preview API on `:8080`.
- **`IS_SANDBOX=1` + `--dangerously-skip-permissions`** are acceptable *only* because the box is isolated and disposable. Keep credentials least-privilege and short-lived; tear boxes down (`bl delete sandbox <name>`) or pass `--keep` knowingly.
- **The demo target is intentionally vulnerable, training-only, and self-contained.** Don't reuse its code, and don't point the agent at systems you don't own or aren't authorized to assess.

## Verify changes

For code-only changes, run the lightweight local checks:

```bash
python3 -m py_compile devbox.py launch.py examples/target-app/server.py
python launch.py --help
python -m pip check
git diff --check
```

For image, toolkit, or launcher changes, also run the live Blaxel flow described in `README.md` under “Prove it before sharing.” At minimum, rebuild the image with `bl deploy`, smoke-test a kept sandbox with `--no-agent --keep`, verify the baked tools inside the box, then run `python launch.py` end to end.

## Layout

| Path | What |
| --- | --- |
| `devbox/` | the toolkit image (edit to change the stack) |
| `devbox.py` | the SDK kit |
| `launch.py` | the end-to-end recipe |
| `examples/assessment-task.md` | the agent task |
| `examples/target-app/` | intentionally-vulnerable demo target (training-only) |
| `docs/security-model.md` | security model |
| `docs/stack-notes.md` | extending the toolkit |
| `.env.example` | required environment variables |
