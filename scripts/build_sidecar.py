#!/usr/bin/env python3
"""
Scientific Sidecar Build Script for LibRE Tab (Optimized Lightweight Packaging)
Compiles the Python FastAPI backend into a standalone onedir sidecar bundle
with core statistical engines (NumPy, SciPy, Statsmodels, Scikit-Learn, Lifelines)
while excluding heavy deep-learning frameworks (PyTorch, Transformers).
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def get_target_triple() -> str:
    """Detects host target triple from rustc -vV or fallback."""
    try:
        res = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except Exception as e:
        print(f"[Warning] Failed to query rustc target triple ({e}). Falling back to x86_64-pc-windows-msvc.")
    return "x86_64-pc-windows-msvc" if os.name == "nt" else "x86_64-unknown-linux-gnu"


def clean_unnecessary_files(directory: Path):
    """Purges test fixtures inside 3rd party packages, debug symbols, and cache files."""
    print("  [+] Purging internal test fixtures and debug symbols...")
    count_removed = 0
    size_removed = 0

    # Only clean test directories inside site-packages, NOT app/plugins
    for item in list(directory.rglob("*")):
        if not item.exists():
            continue
        # Never touch anything inside app/ or plugins/
        if "app" in item.parts or "plugins" in item.parts:
            continue
        # Remove third-party test suites
        if item.is_dir() and item.name in ("tests", "test", "__pycache__", "testing"):
            try:
                for f in item.rglob("*"):
                    if f.is_file():
                        size_removed += f.stat().st_size
                shutil.rmtree(item, ignore_errors=True)
                count_removed += 1
            except Exception:
                pass
        # Remove debug pdb and unneeded files
        elif item.is_file() and item.suffix.lower() in (".pdb", ".pyc", ".pyo"):
            try:
                size_removed += item.stat().st_size
                item.unlink(missing_ok=True)
                count_removed += 1
            except Exception:
                pass

    print(f"  [+] Cleaned {count_removed} unneeded test/cache items ({size_removed / (1024*1024):.1f} MB saved).")


def build_sidecar():
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    target_triple = get_target_triple()
    ext = ".exe" if os.name == "nt" else ""
    sep = ";" if os.name == "nt" else ":"

    print("=" * 70)
    print(f"  BUILDING OPTIMIZED SCIENTIFIC PYTHON SIDECAR FOR: {target_triple}")
    print("=" * 70)

    # 1. Clean previous build artifacts
    dist_dir = root_dir / "dist"
    sidecar_dist = dist_dir / "libretab-server"

    if sidecar_dist.exists():
        shutil.rmtree(sidecar_dist, ignore_errors=True)

    # 2. Optimized PyInstaller invocation (DO NOT exclude unittest as scipy/statsmodels rely on it)
    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name", "libretab-server",
        "--onedir",
        "--noconfirm",
        "--clean",
        # Explicit data inclusion for plugin architecture
        f"--add-data=backend/app/plugins{sep}app/plugins",
        f"--add-data=backend/app{sep}app",
        # Heavy numerical and scientific engine collection
        "--collect-all", "numpy",
        "--collect-all", "scipy",
        "--collect-all", "pandas",
        "--collect-all", "statsmodels",
        "--collect-all", "sklearn",
        "--collect-all", "lifelines",
        "--collect-all", "uvicorn",
        "--collect-all", "fastapi",
        "--collect-all", "pydantic",
        "--collect-all", "app",
        # Strictly exclude unused giant AI frameworks
        "--exclude-module", "torch",
        "--exclude-module", "torchvision",
        "--exclude-module", "torchaudio",
        "--exclude-module", "transformers",
        "--exclude-module", "tokenizers",
        "--exclude-module", "matplotlib",
        "--exclude-module", "IPython",
        "--exclude-module", "ipykernel",
        "--exclude-module", "jupyter",
        "--exclude-module", "tkinter",
        # Entrypoint
        "backend_entry.py",
    ]

    print(f"\nExecuting PyInstaller command:\n{' '.join(pyinstaller_cmd)}\n")
    subprocess.run(pyinstaller_cmd, check=True)

    # 3. Clean test fixtures from third-party libraries
    clean_unnecessary_files(sidecar_dist)

    # 4. Deploy to Tauri binaries directory
    tauri_bin_dir = root_dir / "frontend" / "src-tauri" / "binaries"
    if tauri_bin_dir.exists():
        shutil.rmtree(tauri_bin_dir, ignore_errors=True)
    tauri_bin_dir.mkdir(parents=True, exist_ok=True)

    target_sidecar_exe = tauri_bin_dir / f"libretab-server-{target_triple}{ext}"
    built_exe = sidecar_dist / f"libretab-server{ext}"

    if not built_exe.exists():
        raise FileNotFoundError(f"Expected compiled executable at {built_exe} was not found!")

    # Copy the main executable with target triple name
    shutil.copy2(built_exe, target_sidecar_exe)

    # Copy the entire onedir support files (_internal, DLLs, etc.) into binaries directory
    for item in sidecar_dist.iterdir():
        dest = tauri_bin_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(item, dest)
        elif item.name != f"libretab-server{ext}":
            shutil.copy2(item, dest)

    print(f"\n[SUCCESS] Sidecar binary deployed to:\n  {target_sidecar_exe}")
    print(f"  Support libraries deployed in:\n  {tauri_bin_dir}\n")


if __name__ == "__main__":
    build_sidecar()
