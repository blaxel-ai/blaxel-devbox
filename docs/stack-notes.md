# Stack notes — extending the agent's toolkit

The devbox image ([`../devbox/Dockerfile`](../devbox/Dockerfile)) is the base layer — the toolkit the agent operates with. This is how to extend it without surprises.

## Swapping or adding tools

Every tool is a line in the Dockerfile. Add your scanners, your internal CLIs, a language runtime — then rebuild and redeploy:

```bash
cd devbox && bl deploy && cd ..
until DEVBOX_IMAGE=$(bl get sandbox blaxel-devbox -ojson | jq -r '.[0].spec.runtime.image // empty') && [ -n "$DEVBOX_IMAGE" ]; do sleep 5; done
export DEVBOX_IMAGE
```

Keep the image `linux/amd64` and keep the `COPY --from=ghcr.io/blaxel-ai/sandbox:latest /sandbox-api ...` line — that binary is what makes the image a Blaxel sandbox (it serves the filesystem/process/preview API on `:8080`).

## Proving the baked toolkit

For a share or reviewer smoke test, keep a preview-only box alive:

```bash
python launch.py --name blaxel-devbox-smoke --no-agent --keep
bl connect sandbox blaxel-devbox-smoke
```

Then run inside the box:

```bash
claude --version
command -v agent-browser && agent-browser --help >/tmp/agent-browser-help.txt
docker --version
op --version
```

Delete the smoke box before a full default-name run so process names and ports start fresh:

```bash
bl delete sandbox blaxel-devbox-smoke
```

What this proves:
- Claude Code is installed and can be launched by the recipe with `IS_SANDBOX=1`.
- agent-browser is installed with Chrome runtime dependencies baked into the image.
- Docker CLI is installed. `docker info` only proves a daemon if you configured one; it is expected to fail in the default image.
- 1Password CLI is installed. `op read` / `op run` only work after you runtime-inject `OP_SERVICE_ACCOUNT_TOKEN`.

## Secrets (the safe pattern)

Never bake credentials into the image or pass them inline on a command line. Inject them at runtime:

- The kit's `run(..., env={...})` writes the values to a file *inside the box*, sources it, and deletes that file immediately (with a `trap` as a fallback), so secrets stay out of the command string and process logs and don't linger on disk. This is the only place the kit writes injected secrets to disk; the values still live in the process environment while the command runs.
- In production, source them from **1Password**: pass a service-account token into the box at runtime with `run(..., env={"OP_SERVICE_ACCOUNT_TOKEN": ...})` or `run_agent(..., extra_env={"OP_SERVICE_ACCOUNT_TOKEN": ...})`, then let the agent pull what it needs:

  ```bash
  # op authenticates from OP_SERVICE_ACCOUNT_TOKEN, injected at runtime.
  # op run resolves op://... references you put in the environment:
  export TARGET_TOKEN="op://vault/item/field"
  op run -- your-command           # TARGET_TOKEN becomes the real secret for that command
  op read "op://vault/item/field"  # or read a single secret directly
  ```

The injection-and-wipe path is identical whether the value comes from the generated demo login or `op` (production) — only the source changes. A local `.env` value is not magically available inside the sandbox; thread it through the kit's runtime `env` / `extra_env` path.

## Docker inside the box

The Docker **CLI** is installed so the agent can build images and run containerized tools/scanners. Running the Docker **daemon** inside a sandbox needs the right runtime settings at create time rather than being on by default. See the Blaxel Docker tutorial: https://docs.blaxel.ai/Tutorials/Docker — then point the CLI at that daemon, or set `DOCKER_HOST` to a remote daemon at runtime.

## agent-browser

`agent-browser install --with-deps` runs at build time, and the image bakes Chrome's runtime libraries, so headless Chrome launches on first use (`--headless=new`, no Xvfb needed). The agent invokes it directly (`agent-browser open ...`, etc.). In a smoke test, `command -v agent-browser && agent-browser --help` proves the CLI is present; the full `python launch.py` run proves browser-driven work by producing `/workspace/report.md` with observed target evidence. Docs: https://github.com/vercel-labs/agent-browser

## Ports and previews

`80`, `443`, and `8080` are reserved by Blaxel. Expose your target's port (the template uses `3000`) and bind servers to `0.0.0.0`, not `localhost`, or the preview URL can't reach them.

One gotcha: the sandbox sets `PORT=80` in the environment. Pass the port explicitly rather than reading `$PORT` — the demo runs `server.py 3000`, and any custom target should bind `0.0.0.0:3000` (or change the port consistently across the server, `serve()`, and `blaxel.toml`).
