"""Test harness for an ngui plugin repo: copy it as is into a new plugin.

`start_app` boots the real app (`python -m ngui run`) with the core plugins and this plugin linked,
so a test sees exactly what a user sees. Core plugins are read from ../nicegui-core-plugins
or from $NGUI_CORE_PLUGINS.
"""
import json
import os
import socket
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest

from ngui.config import Config, Home

REPO = Path(__file__).resolve().parent.parent
MANIFEST = tomllib.loads((REPO / "plugin.toml").read_text())
CORE = Path(os.environ.get("NGUI_CORE_PLUGINS", REPO.parent / "nicegui-core-plugins")).resolve()
ROLES = {"storage": "storage-sqlite", "auth": "auth-local", "theme": "theme-default", "layout": "layout-sidebar"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fetch(url: str) -> str:
    """Page body as text; NiceGUI embeds the page's elements as JSON in it."""
    with urlopen(url, timeout=5) as r:
        return r.read().decode()


def _is_up(url: str) -> bool:
    try:
        urlopen(url + "/", timeout=1).close()
        return True
    except HTTPError:
        return True
    except (URLError, OSError):
        return False


@pytest.fixture
def start_app(tmp_path):
    procs, log_path = [], tmp_path / "app.log"

    def start(env: dict[str, str] | None = None) -> str:
        home = Home(tmp_path / "home")
        plugin_id = MANIFEST["id"]
        links = {p: str(CORE / p) for p in [*ROLES.values(), "store"]} | {plugin_id: str(REPO)}
        home.save_config(Config(enabled=[*ROLES.values(), plugin_id], roles=dict(ROLES), links=links))
        # dependencies come from the test venv: mark them installed so the app does not pip install
        home.pydeps_dir.mkdir(parents=True, exist_ok=True)
        (home.pydeps_dir / ".installed.json").write_text(json.dumps(sorted(MANIFEST.get("dependencies", []))))
        port = _free_port()
        full = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
        full.update(env or {}, NGUI_HOME=str(home.root), NGUI_PORT=str(port), NGUI_CORE_REPO="")
        with log_path.open("ab") as log:
            proc = subprocess.Popen([sys.executable, "-m", "ngui", "run"], env=full, stdout=log,
                                    stderr=subprocess.STDOUT)
        procs.append(proc)
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 20
        while proc.poll() is None and not _is_up(url) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert proc.poll() is None and _is_up(url), log_path.read_text(errors="replace")
        return url

    start.log = lambda: log_path.read_text(errors="replace")
    yield start
    for proc in procs:
        proc.terminate()
        proc.wait(timeout=10)


def import_plugin_module(name: str):
    """Import a module of this plugin as part of a package, so its relative imports work."""
    import importlib
    import importlib.util
    pkg = "plugin_under_test"
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(pkg, REPO / "__init__.py",
                                                      submodule_search_locations=[str(REPO)])
        sys.modules[pkg] = importlib.util.module_from_spec(spec)
    return importlib.import_module(f"{pkg}.{name}")


def locale_keys() -> dict[str, set[str]]:
    return {f.stem: set(tomllib.loads(f.read_text())) for f in (REPO / "locales").glob("*.toml")}


def used_keys() -> set[str]:
    """Keys passed to t("...") anywhere in the plugin's Python files."""
    import re
    pattern = re.compile(r'\bt\(\s*"([^"]+)"')
    return {k for f in REPO.glob("*.py") for k in pattern.findall(f.read_text())}
