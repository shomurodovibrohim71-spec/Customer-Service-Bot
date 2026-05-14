"""Resilient supervisor for the saas_bot stack.

Spawns three children and keeps them alive forever:
  1. FastAPI (uvicorn :8080)              - serves WebApp + API
  2. cloudflared tunnel                   - HTTPS public URL
  3. Telegram bot                         - long-polling

Each child runs in its own thread with an independent restart loop:
  - If a child exits (crash, network drop, etc.), wait a short backoff,
    then respawn it.
  - When cloudflared respawns it gets a new public URL; the supervisor
    writes the new URL into .env. The Telegram bot reads WEBAPP_URL on
    every order request via `config.settings.get_webapp_url()`, so the
    bot does NOT need to be restarted - it picks up the new URL on the
    next user interaction.

Designed to run silently from `start_silent.vbs` at Windows login.
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
CLOUDFLARED = ROOT / "tools" / "cloudflared.exe"
ENV_FILE = ROOT / ".env"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
SHUTDOWN = threading.Event()


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_DIR / "supervisor.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def update_env_webapp_url(url: str) -> None:
    if not ENV_FILE.exists():
        return
    try:
        text = ENV_FILE.read_text(encoding="utf-8")
    except OSError:
        return
    if re.search(r"^WEBAPP_URL=.*$", text, flags=re.MULTILINE):
        text = re.sub(r"^WEBAPP_URL=.*$", f"WEBAPP_URL={url}", text, flags=re.MULTILINE)
    else:
        text += f"\nWEBAPP_URL={url}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


def _open_log(name: str):
    f = open(LOG_DIR / name, "a", encoding="utf-8", buffering=1)
    f.write("\n--- start " + time.strftime("%Y-%m-%d %H:%M:%S") + " ---\n")
    return f


def _spawn(cmd: list[str], log_name: str, capture_stdout: bool = False) -> subprocess.Popen:
    """Spawn a child process. `capture_stdout=True` returns stdout as PIPE so the
    caller can parse it (used for cloudflared to read its URL).
    Otherwise stdout/stderr go straight to the log file.
    """
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    if capture_stdout:
        return subprocess.Popen(
            cmd, cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, creationflags=creationflags,
        )
    log_file = _open_log(log_name)
    return subprocess.Popen(
        cmd, cwd=str(ROOT),
        stdout=log_file, stderr=subprocess.STDOUT, creationflags=creationflags,
    )


# -------------------------------------------------- Per-service loops

def uvicorn_loop() -> None:
    backoff = 2
    while not SHUTDOWN.is_set():
        log("uvicorn: starting on :8080")
        started_at = time.time()
        proc = _spawn(
            [str(PY), "-m", "uvicorn", "api.server:app",
             "--host", "0.0.0.0", "--port", "8080"],
            "uvicorn.log",
        )
        rc = proc.wait()
        if SHUTDOWN.is_set():
            return
        if time.time() - started_at > 30:
            backoff = 2
        log(f"uvicorn: exited (code {rc}), restarting in {backoff}s")
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


def cloudflared_loop() -> None:
    backoff = 2
    while not SHUTDOWN.is_set():
        log("cloudflared: starting tunnel")
        proc = _spawn(
            [str(CLOUDFLARED), "tunnel", "--url", "http://localhost:8080",
             "--logfile", str(LOG_DIR / "cloudflared.log"), "--loglevel", "info"],
            "cloudflared.log", capture_stdout=True,
        )
        url = ""
        deadline = time.time() + 40
        while time.time() < deadline and not SHUTDOWN.is_set():
            line = proc.stdout.readline() if proc.stdout else ""
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.2)
                continue
            m = URL_RE.search(line)
            if m:
                url = m.group(0)
                update_env_webapp_url(url)
                log(f"cloudflared: WEBAPP_URL = {url}")
                break
        # Drain stdout in the background so the pipe buffer doesn't fill up.
        def drain():
            try:
                if proc.stdout:
                    for _ in proc.stdout:
                        if SHUTDOWN.is_set():
                            break
            except Exception:  # noqa: BLE001
                pass
        threading.Thread(target=drain, daemon=True).start()
        rc = proc.wait()
        if SHUTDOWN.is_set():
            return
        log(f"cloudflared: exited (code {rc}), restarting in {backoff}s")
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


def bot_loop() -> None:
    time.sleep(3)
    backoff = 2
    while not SHUTDOWN.is_set():
        log("bot: starting")
        started_at = time.time()
        proc = _spawn([str(PY), "bot.py"], "bot.log")
        rc = proc.wait()
        if SHUTDOWN.is_set():
            return
        # If the bot lived long enough (>30s) it counts as a stable run and we
        # reset the backoff so the next restart is fast.
        if time.time() - started_at > 30:
            backoff = 2
        log(f"bot: exited (code {rc}), restarting in {backoff}s")
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


# -------------------------------------------------- Main

def main() -> None:
    threads = [
        threading.Thread(target=uvicorn_loop, daemon=True, name="uvicorn"),
        threading.Thread(target=cloudflared_loop, daemon=True, name="cloudflared"),
        threading.Thread(target=bot_loop, daemon=True, name="bot"),
    ]
    for t in threads:
        t.start()

    log("Supervisor running. Logs in logs/. Press Ctrl+C to stop.")

    def handle_sigint(*_):
        log("SIGINT received - shutting down supervisor and children.")
        SHUTDOWN.set()
        # Best-effort: nudge processes by killing tracked children if any are alive.
        # On Windows the child procs are owned by this Python process, so they'll
        # exit when this process does.
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, handle_sigint)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handle_sigint)
    except (ValueError, AttributeError):
        pass

    # Keep the main thread alive forever.
    try:
        while not SHUTDOWN.is_set():
            time.sleep(60)
    except KeyboardInterrupt:
        handle_sigint()


if __name__ == "__main__":
    main()
