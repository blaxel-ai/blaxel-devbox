#!/usr/bin/env python3
"""Intentionally-vulnerable demo target.

A self-contained TRAINING target for the devbox assessment demo — the thing the
agent assesses. It plants two classic, obvious issues so the agent has something
real to find. **Do not copy this code into anything real.**

Planted issues:
  1. Broken access control + secret exposure: GET /internal/config returns
     secrets with NO authentication.
  2. Reflected XSS: GET /dashboard?q=... echoes `q` into the page unescaped.

Login credentials come from APP_USER / APP_PASS in the environment, injected at
runtime by the devbox (never hardcoded). Stdlib only; takes the port as argv
(default 3000) and binds 0.0.0.0. The UI is styled to look like a real internal
app — the markup is deliberately insecure underneath.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

APP_USER = os.environ.get("APP_USER", "analyst")
APP_PASS = os.environ.get("APP_PASS", "changeme")
SESSION = "demo-session-token"
BRAND = "Northwind Console"

# VULN 1: these "secrets" are served with no auth check on /internal/config.
CONFIG_LEAK = {
    "service": "northwind-console",
    "db_dsn": "postgres://admin:demo-password@db.internal:5432/app",
    "api_key": "demo-api-key-do-not-use-1234567890",
    "note": "leaked via unauthenticated /internal/config",
}

STYLE = """<style>
:root{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--brand:#4f46e5;--brand2:#6366f1;--bg:#f1f5f9}
*{box-sizing:border-box}
body{margin:0;color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--brand);text-decoration:none}
body.auth{min-height:100vh;display:grid;place-items:center;background:linear-gradient(135deg,#1e293b,#0f172a);padding:24px}
.card{background:#fff;width:380px;max-width:92vw;padding:34px;border-radius:18px;box-shadow:0 24px 70px rgba(2,6,23,.45)}
.brand{font-size:21px;font-weight:750;letter-spacing:-.02em}
.brand b{color:var(--brand)}
.sub{margin:.35rem 0 1.6rem;color:var(--muted)}
label{display:block;font-size:13px;font-weight:600;color:#334155;margin-bottom:14px}
input{width:100%;margin-top:6px;padding:11px 13px;border:1px solid var(--line);border-radius:11px;font-size:14px;outline:none;transition:.15s}
input:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(79,70,229,.16)}
.btn{width:100%;margin-top:4px;padding:12px;border:0;border-radius:11px;background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;font-weight:650;font-size:14px;cursor:pointer}
.btn:hover{filter:brightness(1.06)}
.hint{margin:1.3rem 0 0;font-size:12px;color:var(--muted);text-align:center}
body.app{background:var(--bg)}
.topbar{display:flex;align-items:center;gap:18px;padding:12px 22px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.brand-sm{font-weight:750;white-space:nowrap;letter-spacing:-.01em}
.brand-sm b{color:var(--brand)}
.search{flex:1;display:flex;gap:8px;max-width:560px}
.search input{margin:0}
.search .btn{width:auto;margin:0;padding:9px 18px}
.who{color:var(--muted);font-size:14px;white-space:nowrap}
main{max-width:980px;margin:0 auto;padding:30px 22px}
h1{margin:0 0 20px;font-size:25px;letter-spacing:-.02em}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:26px}
.stat{background:#fff;border:1px solid var(--line);border-radius:15px;padding:20px}
.stat .n{font-size:27px;font-weight:750;letter-spacing:-.02em}
.stat .l{color:var(--muted);font-size:13px;margin-top:4px}
.panel{background:#fff;border:1px solid var(--line);border-radius:15px;padding:22px}
.panel h2{margin:0 0 10px;font-size:16px}
.muted{color:var(--muted)}
@media(max-width:640px){.cards{grid-template-columns:1fr}.search{display:none}}
</style>"""


def html(title: str, body: str, body_class: str = "") -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title>{STYLE}</head>"
        f'<body class="{body_class}">{body}</body></html>'
    )


def login_page() -> str:
    body = (
        '<div class="card">'
        f'<div class="brand">\u25c6 Nort<b>hwind</b> Console</div>'
        '<p class="sub">Sign in to your workspace</p>'
        '<form method="POST" action="/login">'
        '<label>Username<input name="user" placeholder="you@company.com" autofocus></label>'
        '<label>Password<input name="pass" type="password" placeholder="\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"></label>'
        '<button class="btn" type="submit">Sign in</button>'
        '</form>'
        '<p class="hint">Internal use only \u00b7 v2.4.1</p>'
        '</div>'
    )
    return html(f"{BRAND} \u2014 Sign in", body, "auth")


def dashboard_page(term: str) -> str:
    # VULN 2: `term` is concatenated into the HTML unescaped (reflected XSS).
    body = (
        '<header class="topbar">'
        f'<div class="brand-sm">\u25c6 Nort<b>hwind</b> Console</div>'
        '<form class="search" method="GET" action="/dashboard">'
        '<input name="q" placeholder="Search records, users, configs\u2026">'
        '<button class="btn" type="submit">Search</button>'
        '</form>'
        f'<div class="who">{APP_USER} \u25be</div>'
        '</header>'
        '<main>'
        '<h1>Dashboard</h1>'
        '<div class="cards">'
        '<div class="stat"><div class="n">1,287</div><div class="l">Active users</div></div>'
        '<div class="stat"><div class="n">42</div><div class="l">Open tickets</div></div>'
        '<div class="stat"><div class="n">99.95%</div><div class="l">Uptime (30d)</div></div>'
        '</div>'
        '<div class="panel">'
        '<h2>Search results</h2>'
        '<p class="muted">Results for: ' + term + '</p>'
        '</div>'
        '</main>'
    )
    return html(f"{BRAND} \u2014 Dashboard", body, "app")


def message_page(code: int, heading: str, note: str) -> str:
    body = (
        '<div class="card">'
        f'<div class="brand">\u25c6 Nort<b>hwind</b> Console</div>'
        f'<p class="sub">{heading}</p>'
        f'<p class="muted">{note}</p>'
        '<p class="hint"><a href="/">\u2190 Back to sign in</a></p>'
        '</div>'
    )
    return html(f"{BRAND} \u2014 {code}", body, "auth")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _cookies(self) -> dict:
        raw = self.headers.get("Cookie", "")
        return dict(p.strip().split("=", 1) for p in raw.split(";") if "=" in p)

    def do_GET(self) -> None:
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            self._send(200, login_page())
        elif u.path == "/dashboard":
            if self._cookies().get("session") != SESSION:
                self._send(401, message_page(401, "Login required", "Your session has expired or is missing."))
                return
            self._send(200, dashboard_page(q.get("q", [""])[0]))
        elif u.path == "/internal/config":
            # VULN 1: no auth check — anyone can read these secrets.
            self._send(200, json.dumps(CONFIG_LEAK, indent=2), "application/json")
        else:
            self._send(404, message_page(404, "Not found", "That page doesn't exist."))

    def do_POST(self) -> None:
        if urlparse(self.path).path == "/login":
            length = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(length).decode())
            if form.get("user", [""])[0] == APP_USER and form.get("pass", [""])[0] == APP_PASS:
                self.send_response(302)
                self.send_header("Set-Cookie", f"session={SESSION}; HttpOnly")
                self.send_header("Location", "/dashboard")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self._send(401, message_page(401, "Sign-in failed", "Invalid username or password."))
        else:
            self._send(404, message_page(404, "Not found", "That page doesn't exist."))


if __name__ == "__main__":
    # Port comes from argv, NOT $PORT: the sandbox sets PORT=80, which would
    # otherwise hijack the bind and the preview (on :3000) could never reach us.
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    print(f"listening on 0.0.0.0:{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
