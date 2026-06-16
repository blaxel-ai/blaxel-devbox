#!/usr/bin/env python3
"""launch.py — run a security agent inside an isolated Blaxel devbox.

The default flow:
    1. provision a fresh, disposable sandbox from your image (the agent's toolkit, baked once)
    2. serve a demo target app inside it (intentionally vulnerable, self-contained)
    3. inject the target credential at runtime (the 1Password pattern), get a preview URL
    4. hand the box to Claude Code for one assessment: authenticate, probe, write a report
    5. surface the findings report, print the preview URL + `bl connect`, then tear down

Point it at your own (authorized) target and task to make it real:

    python launch.py                               # demo: agent assesses the bundled target
    python launch.py --no-agent                    # just the target + preview URL
    python launch.py --repo URL --task-file t.md   # your repo/target, your task
    python launch.py --task-file t.md              # your task against the demo target
    python launch.py --keep                        # leave the box running on exit
"""
from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from pathlib import Path

import devbox

DEV_PORT = 3000
HERE = Path(__file__).parent
TARGET_DIR = HERE / "examples" / "target-app"


def env_or_exit(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.exit(f"missing required env var: {name}  (see .env.example)")
    return val


async def _ensure_remote_dir(sandbox, path: str) -> None:
    """Create a directory in the box, tolerating an already-existing one."""
    try:
        await sandbox.fs.mkdir(path)
    except Exception as exc:
        try:
            await sandbox.fs.ls(path)
        except Exception:
            raise exc


async def upload_dir(sandbox, local_dir: Path, dest: str) -> None:
    """Copy the demo target's files into the box (injected at runtime, not baked)."""
    root = dest.rstrip("/")
    await _ensure_remote_dir(sandbox, root)

    paths = [p for p in local_dir.rglob("*") if "__pycache__" not in p.parts and p.suffix != ".pyc"]

    for d in sorted(p for p in paths if p.is_dir()):
        rel = d.relative_to(local_dir).as_posix()
        await _ensure_remote_dir(sandbox, f"{root}/{rel}")

    for f in sorted(p for p in paths if p.is_file()):
        rel = f.relative_to(local_dir).as_posix()
        await sandbox.fs.write(f"{root}/{rel}", f.read_text(encoding="utf-8"))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run a security agent in a Blaxel devbox.")
    parser.add_argument("--image", default=os.environ.get("DEVBOX_IMAGE", "blaxel-devbox:latest"))
    parser.add_argument("--name", default=os.environ.get("DEVBOX_NAME", "blaxel-devbox-demo"))
    parser.add_argument("--repo", help="git repo / target to clone into the box")
    parser.add_argument("--task-file", help="custom assessment task for the agent")
    parser.add_argument("--no-agent", action="store_true", help="skip the agent run")
    parser.add_argument("--keep", action="store_true", help="don't delete the box on exit")
    args = parser.parse_args()

    env_or_exit("BL_WORKSPACE")  # BL_API_KEY is also read by the SDK, or use `bl login`
    anthropic_key = "" if args.no_agent else env_or_exit("ANTHROPIC_API_KEY")

    # Resolve the assessment task up front so a bad path fails before provisioning.
    task_text = None
    if not args.no_agent:
        task_path = Path(args.task_file) if args.task_file else HERE / "examples" / "assessment-task.md"
        try:
            task_text = task_path.read_text(encoding="utf-8")
        except OSError as exc:
            sys.exit(f"cannot read task file {str(task_path)!r}: {exc}")

    # Demo target credential: generated per run and injected at runtime (never baked).
    # In production this comes from 1Password (`op read`); here it's a one-off value.
    target_env = {"APP_USER": "analyst", "APP_PASS": secrets.token_urlsafe(12)}

    # 1. provision a fresh, disposable box
    print(f"provisioning devbox '{args.name}' from {args.image} ...")
    sandbox = await devbox.provision(args.name, args.image, port=DEV_PORT)

    # Everything after provisioning runs under try/finally so any failure still
    # tears the box down instead of leaking it (and the injected creds with it).
    keep = args.keep
    try:
        if args.repo:
            # 2a. bring your own (authorized) target
            print(f"cloning {args.repo} ...")
            print((await devbox.clone(sandbox, args.repo)).strip() or "(cloned)")
        else:
            # 2b. serve the bundled, intentionally-vulnerable demo target
            print(f"uploading + starting the demo target app on :{DEV_PORT} ...")
            await upload_dir(sandbox, TARGET_DIR, "/workspace/target-app")
            await devbox.serve(
                sandbox,
                f"python3 -u /workspace/target-app/server.py {DEV_PORT}",
                port=DEV_PORT, name="target-app", env=target_env,
            )

        # 3. preview URL
        url = await devbox.preview(sandbox, port=DEV_PORT)
        print("\n=== devbox ready ===")
        note = "  (your app once it serves on :3000)" if args.repo else ""
        print(f"  preview URL : {url}{note}")
        print(f"  interactive : bl connect sandbox {args.name}")

        # 4. hand the box to the security agent
        if task_text is not None:
            # the agent gets the target credential through the same safe path
            extra_env = {} if args.repo else target_env
            print("\nrunning the security agent (Claude Code, headless) ...\n")
            print((await devbox.run_agent(
                sandbox, task_text, anthropic_key=anthropic_key, extra_env=extra_env,
            )).strip())

            # surface the findings report the agent was asked to write
            try:
                report = await devbox.read_file(sandbox, "/workspace/report.md")
            except Exception:
                report = ""
            if report.strip():
                print("\n=== findings report (/workspace/report.md) ===\n")
                print(report.strip())
            else:
                print("\n(no /workspace/report.md found — see the agent output above)")

        # 5. keep, or prompt before deleting (Ctrl-C at the prompt keeps it)
        if not args.keep:
            try:
                input("\npress Enter to delete the box (Ctrl-C to keep it) ... ")
            except KeyboardInterrupt:
                keep = True
    finally:
        if keep:
            print(f"\nbox kept. clean up later with: bl delete sandbox {args.name}")
        else:
            await sandbox.delete()
            print("\nbox deleted.")


if __name__ == "__main__":
    asyncio.run(main())
