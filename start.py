#!/usr/bin/env python3
"""
LibRE Tab - Universal Cross-Platform Launcher
Works seamlessly across Windows, macOS, and Linux.

Usage:
    python start.py           # Auto-checks dependencies and starts LibRE Tab
    python start.py --web     # Force web mode (browser) instead of native Tauri
    python start.py --tauri   # Force native desktop window mode
"""

import argparse
import atexit
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_DIR = ROOT_DIR / "backend"
REQUIREMENTS_TXT = BACKEND_DIR / "requirements.txt"

processes = []


def cleanup():
    """Terminates all spawned child processes on exit."""
    for proc in processes:
        if proc and proc.poll() is None:
            try:
                if platform.system() == "Windows":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True,
                    )
                else:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


atexit.register(cleanup)


def signal_handler(sig, frame):
    print("\n[LibRE Tab] Shutting down gracefully...")
    cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, signal_handler)


def log(msg: str):
    print(f"\033[92m[LibRE Tab]\033[0m {msg}")


def log_warn(msg: str):
    print(f"\033[93m[LibRE Tab Warning]\033[0m {msg}")


def log_err(msg: str):
    print(f"\033[91m[LibRE Tab Error]\033[0m {msg}")


def check_python_dependencies():
    """Checks and installs missing Python packages."""
    log("Checking Python dependencies...")
    try:
        import fastapi
        import lifelines
        import numpy
        import orjson
        import pandas
        import pmdarima
        import pyDOE3
        import scipy
        import statsmodels
        import uvicorn
        log("Python statistical engine dependencies verified.")
    except ImportError as e:
        log_warn(f"Missing dependency ({e}). Installing from backend/requirements.txt...")
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_TXT)]
        res = subprocess.run(cmd, cwd=str(ROOT_DIR))
        if res.returncode != 0:
            log_err("Failed to install Python dependencies.")
            sys.exit(1)
        log("Python dependencies successfully installed.")


def check_frontend_dependencies():
    """Checks and installs frontend node_modules if missing."""
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        log("Frontend node_modules missing. Running npm install...")
        npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
        if not shutil.which(npm_cmd) and not shutil.which("npm"):
            log_err("Node.js / npm is required to run the frontend. Please install Node.js (https://nodejs.org).")
            sys.exit(1)
        cmd = [npm_cmd if shutil.which(npm_cmd) else "npm", "install"]
        res = subprocess.run(cmd, cwd=str(FRONTEND_DIR), shell=(platform.system() == "Windows"))
        if res.returncode != 0:
            log_err("Failed to install frontend dependencies.")
            sys.exit(1)
        log("Frontend dependencies successfully installed.")
    else:
        log("Frontend dependencies verified.")


def has_tauri_prerequisites() -> bool:
    """Checks if Cargo and Tauri tools are available."""
    cargo_cmd = "cargo.exe" if platform.system() == "Windows" else "cargo"
    has_cargo = bool(shutil.which(cargo_cmd) or shutil.which("cargo"))
    if not has_cargo:
        cargo_home = Path.home() / ".cargo" / "bin"
        if (cargo_home / cargo_cmd).exists():
            has_cargo = True
    return has_cargo


def wait_for_server(url: str, timeout: float = 30.0) -> bool:
    """Polls a URL until it responds with HTTP 200."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def run_tauri_mode():
    """Launches the native Tauri desktop application."""
    log("Launching LibRE Tab Native Desktop Shell (Tauri)...")
    node_cmd = sys.executable  # Placeholder, node will be used
    script = str(ROOT_DIR / "run_tauri.js")
    
    cmd = ["node", script, "dev"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        shell=(platform.system() == "Windows"),
    )
    processes.append(proc)
    proc.wait()


def run_web_mode():
    """Launches the FastAPI backend and Vite frontend with automatic browser launch."""
    log("Starting Python Statistical Backend on http://127.0.0.1:8000...")
    backend_cmd = [
        sys.executable,
        str(ROOT_DIR / "backend_entry.py"),
        "--port",
        "8000",
        "--no-watchdog",
    ]
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(ROOT_DIR),
    )
    processes.append(backend_proc)

    log("Starting Vite Frontend Server on http://localhost:5173...")
    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
    frontend_cmd = [npm_cmd if shutil.which(npm_cmd) else "npm", "run", "dev"]
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(FRONTEND_DIR),
        shell=(platform.system() == "Windows"),
    )
    processes.append(frontend_proc)

    log("Waiting for application to be ready...")
    if wait_for_server("http://localhost:5173", timeout=20.0):
        log("LibRE Tab is ready! Opening in your default desktop browser...")
        webbrowser.open("http://localhost:5173")
    else:
        log("Frontend server started. Open http://localhost:5173 in your browser.")

    print("\n" + "=" * 60)
    print("  LibRE Tab is running!")
    print("  - Web App: http://localhost:5173")
    print("  - Backend API: http://127.0.0.1:8000/docs")
    print("  Press Ctrl+C to stop all servers.")
    print("=" * 60 + "\n")

    frontend_proc.wait()


def find_existing_desktop_binary() -> Path | None:
    """Searches for already-built native desktop executables."""
    ext = ".exe" if platform.system() == "Windows" else ""
    candidates = [
        ROOT_DIR / "dist-portable" / "LibRETab-v1.0.0-Beta-Portable" / f"LibRETab{ext}",
        ROOT_DIR / "dist-portable" / f"LibRETab{ext}",
        FRONTEND_DIR / "src-tauri" / "target" / "release" / f"libre-tab{ext}",
        FRONTEND_DIR / "src-tauri" / "target" / "release" / f"LibRE Tab{ext}",
        FRONTEND_DIR / "src-tauri" / "target" / "debug" / f"libre-tab{ext}",
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            return cand
    return None


def run_prebuilt_binary(binary_path: Path):
    """Instantly launches a pre-compiled native desktop binary."""
    log(f"Found compiled native desktop binary: {binary_path.name}")
    log("Launching desktop application directly (instant launch)...")
    proc = subprocess.Popen([str(binary_path)], cwd=str(binary_path.parent))
    processes.append(proc)
    proc.wait()


def main():
    parser = argparse.ArgumentParser(description="LibRE Tab Universal Launcher")
    parser.add_argument("--web", action="store_true", help="Force browser/web mode")
    parser.add_argument("--tauri", action="store_true", help="Force native desktop Tauri mode")
    parser.add_argument("--dev", action="store_true", help="Force live hot-reloading development mode")
    args = parser.parse_args()

    print("=" * 60)
    print("   LibRE Tab - Scientific Statistical Analysis Platform")
    print("   Platform:", platform.system(), platform.release(), f"({platform.machine()})")
    print("   Python:", sys.version.split()[0])
    print("=" * 60)

    # 1. If prebuilt binary exists and user did not request dev mode or web mode, launch instantly!
    if not args.dev and not args.web:
        existing_binary = find_existing_desktop_binary()
        if existing_binary and not args.tauri:
            try:
                run_prebuilt_binary(existing_binary)
                return
            except Exception as e:
                log_warn(f"Direct binary launch failed ({e}). Falling back to standard launcher...")

    # 2. Verify dependencies (runs in < 5ms if already satisfied)
    check_python_dependencies()
    check_frontend_dependencies()

    # 3. Determine execution mode
    if args.web:
        run_web_mode()
    elif args.tauri:
        run_tauri_mode()
    else:
        if has_tauri_prerequisites():
            try:
                run_tauri_mode()
            except Exception as e:
                log_warn(f"Native Tauri desktop failed to start ({e}). Falling back to browser mode...")
                run_web_mode()
        else:
            log("Rust/Cargo not detected in PATH. Starting in high-performance browser mode...")
            run_web_mode()


if __name__ == "__main__":
    main()

