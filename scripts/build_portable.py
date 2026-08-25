#!/usr/bin/env python3
"""
Automated Portable Release Packager for LibRE Sigma Beta v1.0.0 (Lightweight Edition)
Creates a clean, standalone, uninstaller-free portable desktop package with:
- Native Tauri desktop launcher
- Bundled WebView2 runtime loader
- Python scientific computing sidecar (FastAPI + SciPy + Statsmodels + Lifelines + Sklearn)
- Auto-generated ZIP distribution archive
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

from build_sidecar import build_sidecar, get_target_triple, clean_unnecessary_files


def run_command(cmd, cwd=None, env=None):
    print(f"\n[EXEC] {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    subprocess.run(cmd, cwd=cwd, env=env or os.environ, check=True, shell=isinstance(cmd, str))


def build_portable():
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    target_triple = get_target_triple()
    ext = ".exe" if os.name == "nt" else ""
    version = "v1.0.0-Beta"
    package_name = f"LibRESigma-{version}-Portable"

    dist_portable_dir = root_dir / "dist-portable"
    release_dir = dist_portable_dir / package_name
    zip_path = dist_portable_dir / f"{package_name}.zip"

    print("=" * 75)
    print(f"  LIBRE SIGMA LIGHTWEIGHT PORTABLE DESKTOP PACKAGER ({version})")
    print(f"  Target Platform: {target_triple}")
    print("=" * 75)

    # 1. Clean previous portable release artifacts
    if dist_portable_dir.exists():
        shutil.rmtree(dist_portable_dir, ignore_errors=True)
    release_dir.mkdir(parents=True, exist_ok=True)

    # 2. Build Python Scientific Sidecar
    print("\n>>> STEP 1: Building Optimized Python Scientific Sidecar...")
    build_sidecar()

    # 3. Build React Frontend
    print("\n>>> STEP 2: Building Production React Frontend...")
    frontend_dir = root_dir / "frontend"
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    run_command([npm_cmd, "run", "build"], cwd=frontend_dir)

    # 4. Build Tauri Desktop Shell
    print("\n>>> STEP 3: Compiling Tauri Native Desktop Shell...")
    run_tauri_script = root_dir / "run_tauri.js"
    if run_tauri_script.exists():
        run_command(["node", str(run_tauri_script), "build"], cwd=root_dir)
    else:
        run_command([npm_cmd, "run", "tauri", "--", "build"], cwd=frontend_dir)

    # 5. Assemble Portable Release Directory
    print("\n>>> STEP 4: Assembling Standalone Portable Release Package...")

    tauri_target_dir = frontend_dir / "src-tauri" / "target" / "release"
    tauri_exe_candidates = [
        tauri_target_dir / f"LibRE Sigma{ext}",
        tauri_target_dir / f"libre-sigma{ext}",
        tauri_target_dir / f"LibRESigma{ext}",
        tauri_target_dir / f"LibRE Tab{ext}",
        tauri_target_dir / f"libre-tab{ext}",
        tauri_target_dir / f"LibRETab{ext}",
    ]

    built_tauri_exe = None
    for cand in tauri_exe_candidates:
        if cand.exists():
            built_tauri_exe = cand
            break

    if not built_tauri_exe:
        raise FileNotFoundError(f"Could not locate compiled Tauri executable in {tauri_target_dir}")

    # Copy main launcher as LibRESigma.exe
    target_launcher = release_dir / f"LibRESigma{ext}"
    shutil.copy2(built_tauri_exe, target_launcher)
    print(f"  [+] Copied Main Launcher: {target_launcher.name}")

    # Copy WebView2Loader.dll if present
    webview2_dll = tauri_target_dir / "WebView2Loader.dll"
    if webview2_dll.exists():
        shutil.copy2(webview2_dll, release_dir / "WebView2Loader.dll")
        print("  [+] Copied WebView2Loader.dll")

    # Copy sidecar binaries and _internal support folder directly into root (single copy, no redundant duplication)
    sidecar_binaries_src = frontend_dir / "src-tauri" / "binaries"
    if sidecar_binaries_src.exists():
        for item in sidecar_binaries_src.iterdir():
            dest = release_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
                if item.name.startswith("libresigma-server-") or item.name.startswith("libretab-server-"):
                    shutil.copy2(item, release_dir / f"libresigma-server{ext}")
        print("  [+] Copied Sidecar Binaries and Python Scientific Runtime")

    # 6. Purge test folders and caches from the final portable release
    clean_unnecessary_files(release_dir)

    # 7. Generate Portable Instructions Readme
    readme_content = f"""================================================================================
  LibRE Sigma - Portable Desktop Release ({version})
  Open-Source Statistical Analysis & Reliability Engineering Platform
================================================================================

QUICK START INSTRUCTIONS:
1. Double-click 'LibRESigma.exe'.
2. The application starts immediately in offline, privacy-first mode.

FEATURES IN THIS PORTABLE RELEASE:
- Zero Installation: Unzip anywhere (USB drive, Desktop, Local Drive) and run.
- Zero Telemetry: 100% offline, local-first computing engine.
- Automatic Process Management: The desktop interface automatically spawns and
  monitors the Python scientific engine with dynamic ephemeral port binding.
  When you close the app, all background processes terminate cleanly.
- 122 Built-in Statistical & Reliability Modules:
  • Basic Statistics (t-Tests, ANOVA, Normality, Non-Parametrics)
  • Statistical Process Control (SPC Xbar-R, I-MR, CUSUM, EWMA, Capability)
  • Taguchi Orthogonal Arrays (L4-L27) & Response Surface DOE
  • Reliability & Survival Analysis (Weibull, Kaplan-Meier, ALT)
  • Multivariate Statistics & Time Series Forecasting

SYSTEM REQUIREMENTS:
- Windows 10 / 11 (64-bit)
- Microsoft Edge WebView2 Runtime (pre-installed on Windows 10/11)

================================================================================
"""
    readme_path = release_dir / "README.txt"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("  [+] Generated Portable README.txt")

    # 8. Create Compressed ZIP Distribution Package
    print(f"\n>>> STEP 5: Generating Distribution ZIP Package: {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in release_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(dist_portable_dir)
                zipf.write(file_path, arcname)

    folder_size_mb = sum(f.stat().st_size for f in release_dir.rglob("*") if f.is_file()) / (1024 * 1024)
    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)

    print("=" * 75)
    print(f"  [SUCCESS] OPTIMIZED PORTABLE RELEASE GENERATED!")
    print(f"  Folder:   {release_dir} ({folder_size_mb:.1f} MB)")
    print(f"  ZIP File: {zip_path} ({zip_size_mb:.1f} MB)")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    build_portable()
