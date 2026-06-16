# Demo target (intentionally vulnerable)

A tiny, self-contained training target for the devbox assessment demo — the thing the agent assesses. **Intentionally insecure. Do not reuse this code.**

`server.py` is Python stdlib only (no deps). It takes its port as an argument (`server.py 3000`) and binds `0.0.0.0` on it — it deliberately does **not** read `$PORT`, because the sandbox sets `PORT=80`, which would otherwise hijack the bind and break the preview. The login credentials come from `APP_USER` / `APP_PASS` in the environment, injected at runtime by `launch.py` — never hardcoded.

## Planted issues

1. **Broken access control + secret exposure** — `GET /internal/config` returns secrets with no authentication.
2. **Reflected XSS** — `GET /dashboard?q=...` echoes `q` into the page unescaped.

Swap this out for your own **authorized** target (or `--repo` your app) when you make the demo real.
