"""devbox.py — a tiny, reusable kit for Blaxel devboxes.

This is the base layer. It wraps the Blaxel SDK in a handful of small, readable
functions so a recipe (see launch.py) reads top-to-bottom. Build on top of these
primitives or copy them into your own project.

The mental model:
    provision()   -> get a sandbox running YOUR image (the agent's toolkit, baked once)
    run()         -> run a command in it (secrets injected safely, never inline)
    serve()       -> start a long-running server in it (your app or a target)
    preview()     -> get a public URL to whatever the box is serving
    run_agent()   -> hand the box to Claude Code for one headless task
    read_file()   -> read a file back out of the box (e.g. the agent's report)
    clone()       -> pull a repo/target into the box so the agent works on real code

Nothing here is devbox-specific magic; it's the same SDK calls you'd write
yourself, named and commented so the seams are obvious.
"""
from __future__ import annotations

import re
import shlex
from contextlib import suppress

from blaxel.core import SandboxInstance

WORKDIR = "/workspace"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")        # process/file-name safe
_SAFE_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")  # valid shell identifier


async def provision(name: str, image: str, *, memory: int = 4096, port: int = 3000):
    """Create the devbox, or reuse it if a box with this name already exists.

    `image` is the id of YOUR devbox image (from `bl deploy` in ./devbox).
    Swap the image and you swap the entire stack the agent runs in.
    """
    return await SandboxInstance.create_if_not_exists({
        "name": name,
        "image": image,
        "memory": memory,
        "ports": [{"target": port, "protocol": "HTTP"}],
    })


async def run(sandbox, name: str, command: str, *, timeout: int = 120,
              wait_for_ports=None, env: dict | None = None) -> str:
    """Run a command in the box and return its logs.

    The command is written to a script file in the box and executed from there,
    so quotes/newlines in it can't break the shell. Secrets in `env` go to a
    separate file that is sourced and then deleted on exit (a shell `trap`), so
    they never appear inline in the command string/process args and don't linger
    in the sandbox after the command finishes. This is the one place secrets
    touch the box, on purpose. Raises if a completed command exits non-zero.
    """
    if not _SAFE_NAME.match(name):
        raise ValueError(f"unsafe process name {name!r}: use letters, digits, '.', '-', '_'")
    if env and any(not _SAFE_ENV_KEY.match(k) for k in env):
        raise ValueError("env keys must be valid shell identifiers")
    script_path = f"{WORKDIR}/.cmd.{name}.sh"
    cleanup = [script_path]
    preamble = ""
    if env:
        env_path = f"{WORKDIR}/.env.{name}"
        cleanup.append(env_path)
        exports = "".join(f"export {k}={shlex.quote(str(v))}\n" for k, v in env.items())
        await sandbox.fs.write(env_path, exports)
        # Source the secrets into the environment, then delete the file right
        # away (the values stay in the process env). The trap is a fallback;
        # this keeps the secret file from lingering for the life of a long-
        # running server started via serve().
        preamble = (f"set -a; . {shlex.quote(env_path)}; set +a\n"
                    f"rm -f {shlex.quote(env_path)}\n")
    trap = "trap " + shlex.quote("rm -f " + " ".join(cleanup)) + " EXIT\n"
    await sandbox.fs.write(script_path, trap + preamble + command + "\n")

    spec = {"name": name, "command": f"bash {shlex.quote(script_path)}",
            "working_dir": WORKDIR}
    should_poll = not wait_for_ports
    if wait_for_ports:
        spec["wait_for_ports"] = wait_for_ports  # return once the port is open
    else:
        # Do not hold the process-create HTTP request open for long tasks like
        # Claude Code runs; proxies can 504 before the command is done. Start the
        # process, then poll its status through short requests instead.
        spec["wait_for_completion"] = False
        spec["timeout"] = timeout
    try:
        proc = await sandbox.process.exec(spec)
        if should_poll:
            proc = await sandbox.process.wait(name, max_wait=(timeout + 30) * 1000, interval=1000)
    except Exception:
        # If the sandbox API rejects the process before the shell starts, the
        # in-script trap never runs. Best-effort cleanup keeps injected secret
        # files from lingering after process-create failures.
        if should_poll:
            with suppress(Exception):
                await sandbox.process.kill(name)
        for path in cleanup:
            with suppress(Exception):
                await sandbox.fs.rm(path)
        raise

    logs = getattr(proc, "logs", "") or ""
    if should_poll and not logs:
        with suppress(Exception):
            logs = await sandbox.process.logs(name)
    status = getattr(proc, "status", None)
    status_value = getattr(status, "value", status)
    if should_poll and status_value and status_value != "completed":
        raise RuntimeError(f"command '{name}' did not complete (status {status_value}) in the devbox:\n{logs}")
    code = getattr(proc, "exit_code", None)
    if isinstance(code, int) and code != 0:
        raise RuntimeError(f"command '{name}' failed (exit {code}) in the devbox:\n{logs}")
    return logs


async def serve(sandbox, command: str, *, port: int = 3000, name: str = "dev-server",
                env: dict | None = None) -> None:
    """Start a long-running server (your app, or a target to assess). Bind it to
    0.0.0.0 so the preview URL can reach it (localhost-only servers aren't
    reachable through previews). `env` is injected via the safe path (written to
    a file in the box, sourced, wiped) — e.g. the target's credentials, which in
    production would come from 1Password."""
    await run(sandbox, name, command, wait_for_ports=[port], env=env)


async def preview(sandbox, *, port: int = 3000, name: str = "preview", public: bool = True):
    """Open a preview URL to whatever the box is serving on `port`."""
    p = await sandbox.previews.create_if_not_exists({
        "metadata": {"name": name},
        "spec": {"port": port, "public": public},
    })
    url = getattr(p.spec, "url", None)
    if not url:
        raise RuntimeError(f"preview '{name}' created but returned no URL")
    return url


async def clone(sandbox, repo_url: str, *, dest: str = "repo") -> str:
    """Shallow-clone a git repo into the box so the agent works on real code."""
    return await run(
        sandbox, "clone",
        f"git clone --depth 1 -- {shlex.quote(repo_url)} {shlex.quote(dest)} && echo cloned",
        timeout=180,
    )


async def run_agent(sandbox, task: str, *, anthropic_key: str,
                    extra_env: dict | None = None, timeout: int = 600) -> str:
    """Run ONE headless Claude Code task in the box and return its output.

    `claude --print` is Claude Code's headless mode. `--dangerously-skip-permissions`
    lets it act without approval prompts — Anthropic recommends that flag ONLY
    inside a sandbox, which is exactly what this box is. The prompt is passed via
    a file so nested quotes can't break the shell.

    `extra_env` injects extra secrets the agent needs for the task (e.g. target
    credentials) through the same safe path — written to a file, sourced, wiped.
    In production those come from 1Password (`op`); they are never baked into the
    image or the prompt. Swap this out to bring your own agent; the rest of the
    kit stays the same.
    """
    await sandbox.fs.write(f"{WORKDIR}/.task.md", task)
    command = (
        "cd /workspace && claude --print --dangerously-skip-permissions "
        '--output-format text "$(cat .task.md)"'
    )
    # IS_SANDBOX=1 marks this box as a recognized sandbox so Claude Code allows
    # --dangerously-skip-permissions while running as root. It's also baked into
    # the image; set here too so the recipe works even on a swapped base image.
    env = {"ANTHROPIC_API_KEY": anthropic_key, "IS_SANDBOX": "1"}
    if extra_env:
        env.update(extra_env)
    return await run(sandbox, "claude-task", command, env=env, timeout=timeout)


async def read_file(sandbox, path: str) -> str:
    """Read a file back out of the box (e.g. the agent's findings report)."""
    return await sandbox.fs.read(path)
