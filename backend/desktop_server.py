"""
backend/desktop_server.py
Dedicated entry point for packaged Windows Electron Desktop distribution.
Handles:
- Dynamic/configurable port binding on 127.0.0.1
- Parent process heartbeat monitoring (prevents orphan processes on exit)
- Safe AppData directory initialization
- Logging to %APPDATA%/BG_AI/logs/backend.log
"""
from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path

# Ensure backend root is on sys.path
_current_dir = Path(__file__).resolve().parent
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

# Force desktop mode
os.environ["BGAI_DESKTOP_MODE"] = "1"

from app.paths import get_app_data_dir, get_logs_dir, get_app_data_file
from dotenv import load_dotenv

# Priority: AppData/.env > bundled .env > current dir .env
app_data_env = get_app_data_file(".env")
if app_data_env.exists():
    load_dotenv(app_data_env, override=True)
else:
    load_dotenv(override=True)


def find_free_port(preferred: int = 8001) -> int:
    """Check if preferred port is free; if not, find a free ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass

    # Find any available port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def setup_desktop_logging():
    """Configure file logging to AppData/BG_AI/logs/backend.log as well as stdout."""
    log_dir = get_logs_dir()
    log_file = log_dir / "backend.log"

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_file), mode="a", encoding="utf-8"),
    ]

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    logging.info(f"BG AI Desktop Backend initialized. AppData: {get_app_data_dir()}")


def monitor_parent_process(parent_pid: int | None = None):
    """
    Monitors parent process or stdin. If parent process terminates,
    cleanly shut down this server to prevent orphan backend processes.
    """
    if parent_pid is not None and parent_pid > 0:
        import psutil  # if available
        while True:
            time.sleep(2.0)
            try:
                # Check if parent is still alive
                p = psutil.Process(parent_pid)
                if not p.is_running():
                    logging.info(f"Parent process {parent_pid} exited. Shutting down backend.")
                    os._exit(0)
            except Exception:
                logging.info(f"Parent process {parent_pid} no longer reachable. Shutting down backend.")
                os._exit(0)
    else:
        # Fallback: monitor stdin if piped
        try:
            while True:
                line = sys.stdin.readline()
                if not line:  # EOF when parent closes pipe
                    logging.info("Stdin pipe closed by parent. Shutting down backend.")
                    os._exit(0)
                time.sleep(1.0)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="BG AI Desktop Backend Server")
    parser.add_argument("--port", type=int, default=None, help="Port to listen on (default: auto)")
    parser.add_argument("--data-dir", type=str, default=None, help="Custom data directory")
    parser.add_argument("--parent-pid", type=int, default=None, help="Parent process PID to monitor")
    parser.add_argument("--secret", type=str, default=None, help="Per-launch desktop authentication secret")
    args = parser.parse_args()

    if args.data_dir:
        os.environ["BGAI_DATA_DIR"] = args.data_dir
    if args.secret:
        os.environ["BGAI_DESKTOP_SECRET"] = args.secret

    setup_desktop_logging()

    # Determine port
    port = args.port or int(os.getenv("BGAI_PORT", "0")) or find_free_port(8001)

    # Start parent monitor in daemon thread
    t = threading.Thread(target=monitor_parent_process, args=(args.parent_pid,), daemon=True)
    t.start()

    # Announce port for Electron
    print(f"BGAI_PORT:{port}", flush=True)
    logging.info(f"Starting uvicorn on 127.0.0.1:{port} (BGAI_PORT:{port})")

    import uvicorn
    from app.main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
