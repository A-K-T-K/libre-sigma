import argparse
import logging
import multiprocessing
import os
import socket
import sys
import threading
import time

# Ensure stdout is unbuffered
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# If frozen by PyInstaller, set up sys.path correctly
if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)
    backend_path = os.path.join(bundle_dir, "backend")
    if os.path.exists(backend_path) and backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    internal_path = os.path.join(os.path.dirname(sys.executable), "_internal")
    if os.path.exists(internal_path) and internal_path not in sys.path:
        sys.path.insert(0, internal_path)
else:
    backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

import uvicorn
from app.main import app, start_watchdog_thread


def get_ephemeral_port(host: str = "127.0.0.1") -> int:
    """Finds an unused ephemeral port assigned by the OS."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def main():
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="LibRE Sigma Statistical Engine")
    parser.add_argument("--host", default="127.0.0.1", help="Host IP to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0, help="Port to bind (0 for ephemeral OS assignment)")
    parser.add_argument("--no-watchdog", action="store_true", help="Disable the heartbeat watchdog monitor")
    parser.add_argument("--log-level", default="warning", help="Uvicorn log level (default: warning)")
    args = parser.parse_args()

    port = args.port
    if port == 0:
        port = get_ephemeral_port(args.host)

    app.state.port = port

    # Start background watchdog for orphan process cleanup
    if not args.no_watchdog:
        start_watchdog_thread(timeout_seconds=10.0, grace_seconds=25.0)

    # Configure and run uvicorn
    config = uvicorn.Config(
        app=app,
        host=args.host,
        port=port,
        log_level=args.log_level,
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config=config)
    server.run()


if __name__ == "__main__":
    main()
