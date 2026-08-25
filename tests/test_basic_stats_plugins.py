import os
import sys
import json

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.plugins.loader import discover_and_load_plugins, registry


def test_manifest():
    discover_and_load_plugins("app.plugins.modules")
    manifest = registry.get_manifest()
    print(f"Total Plugins Loaded: {len(manifest)}")
    basic_stats = [
        p for p in manifest
        if len(p.menu_path) >= 2 and p.menu_path[0] == "Stat" and p.menu_path[1] == "Basic Statistics"
    ]
    print(f"Basic Statistics Plugins Count: {len(basic_stats)}")
    for idx, p in enumerate(basic_stats, 1):
        print(f" {idx:2d}. {p.name} (id: {p.id}, path: {' > '.join(p.menu_path)})")

    assert len(basic_stats) >= 15, f"Expected at least 15 basic stats plugins, got {len(basic_stats)}"
    print("Basic stats test passed!")


if __name__ == "__main__":
    test_manifest()
