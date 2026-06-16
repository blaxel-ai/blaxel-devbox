# Blaxel devbox image: your toolkit, baked once.
#
# This is a Blaxel native sandbox image. It bundles a real developer toolkit so
# an AI agent (here: Claude Code) can do real work — drive a browser, run tools,
# authenticate with injected credentials — inside an isolated, disposable sandbox
# instead of a vanilla cloud box. The bundled example is a security assessment,
# but the box is general-purpose — swap the tools for whatever you do.
#
# glibc base (Debian bookworm), not Alpine/musl: native deps for Chrome,
# node-gyp, and pip wheels resolve cleanly. Pin linux/amd64 so it matches the
# Blaxel sandbox-api binary copied in and builds the same on Apple Silicon hosts.
FROM --platform=linux/amd64 ghcr.io/blaxel-ai/sandbox:latest AS blaxel-sandbox
FROM --platform=linux/amd64 node:22-bookworm-slim

# The Blaxel sandbox API binary turns this image into a Blaxel sandbox: it serves
# the filesystem/process/preview API on :8080 that the SDK and `bl` talk to.
COPY --from=blaxel-sandbox /sandbox-api /usr/local/bin/sandbox-api

# HOME is the agent's working root. Set it before installing browser/CLI caches
# so Chrome and tool state land where the runtime user will look for them.
ENV HOME=/workspace
RUN mkdir -p /workspace
WORKDIR /workspace

# Core dev toolchain: git, build tools, python, common CLIs an agent expects.
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates curl wget gnupg git openssh-client \
      tar zip unzip jq patch diffutils \
      sed gawk grep vim nano less \
      tmux tree htop ripgrep fd-find \
      build-essential make \
      python3 python3-pip python3-venv \
      netcat-openbsd \
  && rm -rf /var/lib/apt/lists/*

# Docker CLI — run containerized tools and scanners. The client is installed
# here; running the Docker daemon inside a sandbox needs the right runtime
# settings at create time — see ../docs/stack-notes.md. Baking the CLI keeps the
# image honest about what's available without pretending dockerd is running.
RUN apt-get update && apt-get install -y --no-install-recommends docker.io \
  && rm -rf /var/lib/apt/lists/*

# Claude Code CLI — the agent harness that runs inside the box.
# Headless usage: `claude --print --dangerously-skip-permissions "..."`.
# Anthropic recommends --dangerously-skip-permissions ONLY inside a sandbox,
# which is exactly this environment. Auth is via ANTHROPIC_API_KEY at runtime.
RUN npm install -g @anthropic-ai/claude-code

# Claude Code refuses --dangerously-skip-permissions when running as root unless
# it detects a recognized sandbox. This box runs as root and IS a sandbox, so
# declare it: IS_SANDBOX=1 is Anthropic's sanctioned signal for container/sandbox
# use. Without this, both the headless recipe and interactive `claude` runs error
# with "cannot be used with root/sudo privileges".
ENV IS_SANDBOX=1

# Vercel agent-browser — headless Chrome automation built for AI agents, for
# recon and driving authenticated web flows. We pre-install Chrome's runtime shared libs
# explicitly (the slim base above purges apt lists, and Chrome otherwise fails
# its first launch with missing libglib/libnss). apt lists are kept until after
# `agent-browser install --with-deps` so that step can resolve anything extra,
# then cleaned. Chrome runs on first use (--headless=new, no Xvfb).
RUN apt-get update && apt-get install -y --no-install-recommends \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
      libglib2.0-0 libxshmfence1 fonts-liberation \
  && npm install -g agent-browser \
  && agent-browser install --with-deps \
  && rm -rf /var/lib/apt/lists/*

# 1Password CLI (`op`) — installed so secrets can be pulled at runtime via
# `op run` / `op read` instead of being baked into the image. No secrets live in
# this repo or image; see ../docs/stack-notes.md for the safe-injection pattern.
ARG OP_VERSION=2.30.3
RUN set -eux; \
    curl -fsSL "https://cache.agilebits.com/dist/1P/op2/pkg/v${OP_VERSION}/op_linux_amd64_v${OP_VERSION}.zip" -o /tmp/op.zip; \
    unzip -o /tmp/op.zip op -d /usr/local/bin; \
    rm -f /tmp/op.zip; \
    chmod +x /usr/local/bin/op; \
    op --version

# ---------------------------------------------------------------------------
# ADD YOUR OWN TOOLS HERE
#
# This image is the agent's whole world — anything you install here shows up in
# the box. It's just a Dockerfile, so add whatever your workflow needs, then
# re-run `bl deploy` and refresh DEVBOX_IMAGE. The tools above (1Password, etc.)
# are only examples; swap or extend them freely. Patterns:
#
#   apt packages:  RUN apt-get update && apt-get install -y --no-install-recommends <packages> && rm -rf /var/lib/apt/lists/*
#   Node CLIs:     RUN npm install -g <package>
#   Python tools:  RUN pip install --no-cache-dir <package>
#   a binary:      RUN curl -fsSL <url> -o /usr/local/bin/<tool> && chmod +x /usr/local/bin/<tool>
#   your scripts:  COPY <local-file> /usr/local/bin/<tool>
#
# Keep the image linux/amd64 and the sandbox-api COPY line near the top.
# ---------------------------------------------------------------------------

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
