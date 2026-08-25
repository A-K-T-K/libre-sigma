import importlib
import importlib.util
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
from .base import AnalysisPlugin, PluginManifestItem

logger = logging.getLogger("libresigma.plugins")


class PluginRegistry:
    def __init__(self):
        self._plugins: Dict[str, AnalysisPlugin] = {}

    def register(self, plugin_instance: AnalysisPlugin):
        if not plugin_instance.id:
            raise ValueError(f"Plugin {plugin_instance.__class__.__name__} must have a non-empty 'id'")
        self._plugins[plugin_instance.id] = plugin_instance
        logger.info(f"Registered plugin: {plugin_instance.name} ({plugin_instance.id})")

    def get(self, plugin_id: str) -> Optional[AnalysisPlugin]:
        return self._plugins.get(plugin_id)

    def all(self) -> List[AnalysisPlugin]:
        return list(self._plugins.values())

    def get_manifest(self) -> List[PluginManifestItem]:
        manifest = []
        for p in self._plugins.values():
            schema = p.param_schema.model_json_schema()
            manifest.append(
                PluginManifestItem(
                    id=p.id,
                    name=p.name,
                    menu_path=p.menu_path,
                    description=p.description,
                    param_schema=schema,
                )
            )
        return manifest


registry = PluginRegistry()


def _get_modules_directories() -> List[Path]:
    """
    Freeze-safe directory resolution for plugin modules.
    Supports PyInstaller onedir, onefile (_MEIPASS), and standard development paths.
    """
    candidate_paths: List[Path] = []

    # If packaged / frozen by PyInstaller
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate_paths.append(Path(meipass) / "app" / "plugins" / "modules")
            candidate_paths.append(Path(meipass) / "backend" / "app" / "plugins" / "modules")

        exe_dir = Path(sys.executable).resolve().parent
        candidate_paths.append(exe_dir / "_internal" / "app" / "plugins" / "modules")
        candidate_paths.append(exe_dir / "_internal" / "backend" / "app" / "plugins" / "modules")
        candidate_paths.append(exe_dir / "app" / "plugins" / "modules")
        candidate_paths.append(exe_dir / "backend" / "app" / "plugins" / "modules")

    # Local development fallback
    file_parent = Path(__file__).resolve().parent
    candidate_paths.append(file_parent / "modules")

    # Filter only existing directories
    valid_paths = [p for p in candidate_paths if p.is_dir()]
    return valid_paths


def _load_module_from_file(file_path: Path, module_name: str) -> None:
    """
    Loads a python file dynamically via importlib.util.spec_from_file_location
    and registers all contained AnalysisPlugin subclasses.
    """
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, AnalysisPlugin)
                    and attr is not AnalysisPlugin
                ):
                    try:
                        instance = attr()
                        if instance.id not in registry._plugins:
                            registry.register(instance)
                    except Exception as err:
                        logger.error(f"Error instantiating plugin {attr_name} in {file_path.name}: {err}")
    except Exception as e:
        logger.error(f"Failed to load plugin module from {file_path}: {e}")


def discover_and_load_plugins(modules_package: str = "app.plugins.modules"):
    """
    Auto-discovers and registers all AnalysisPlugin subclasses.
    Scans freeze-safe paths using spec_from_file_location and falls back to pkgutil.
    """
    registered_count_before = len(registry.all())
    visited_files: Set[str] = set()

    # 1. Filesystem scan across freeze-safe directories
    plugin_dirs = _get_modules_directories()
    for pdir in plugin_dirs:
        for py_file in pdir.rglob("*.py"):
            if py_file.name.startswith(("_", ".")) or py_file.name == "__init__.py":
                continue
            abs_str = str(py_file.resolve())
            if abs_str in visited_files:
                continue
            visited_files.add(abs_str)

            # Construct safe relative module name
            try:
                rel_parts = py_file.relative_to(pdir.parent).with_suffix("").parts
                mod_name = "app.plugins." + ".".join(rel_parts)
            except Exception:
                mod_name = f"app.plugins.modules.{py_file.stem}"

            _load_module_from_file(py_file, mod_name)

    # 2. Package scan fallback (for embedded bytecode in PyInstaller archives)
    try:
        import pkgutil
        package_module = importlib.import_module(modules_package)
        prefix = modules_package + "."
        for _, modname, _ in pkgutil.walk_packages(package_module.__path__, prefix):
            try:
                mod = importlib.import_module(modname)
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (
                        inspect.isclass(attr)
                        and issubclass(attr, AnalysisPlugin)
                        and attr is not AnalysisPlugin
                    ):
                        try:
                            instance = attr()
                            if instance.id not in registry._plugins:
                                registry.register(instance)
                        except Exception as err:
                            logger.error(f"Error instantiating {attr_name} in {modname}: {err}")
            except Exception as e:
                logger.debug(f"pkgutil load skipped or already loaded {modname}: {e}")
    except Exception as e:
        logger.debug(f"pkgutil fallback error: {e}")

    loaded_total = len(registry.all())
    logger.info(f"Plugin discovery complete: {loaded_total} plugins registered (added {loaded_total - registered_count_before}).")
