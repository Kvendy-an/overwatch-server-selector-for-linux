"""Unprivileged desktop preferences, feed refresh, and helper client."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .core import BUNDLE, atomic_json, fetch_feed, parse_feed, read_feed, validate_selection

HELPER = Path("/usr/local/libexec/ow-server-selector-helper")
ROOT_STATE = Path("/var/lib/ow-server-selector/state.json")
PROJECT = Path(__file__).resolve().parent.parent


def host_environment():
    """Keep bundled AppImage libraries/Python out of host administrative tools."""
    environment = os.environ.copy()
    for name in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH", "GI_TYPELIB_PATH", "GIO_MODULE_DIR", "GSETTINGS_SCHEMA_DIR", "FONTCONFIG_FILE"):
        environment.pop(name, None)
    return environment


class Client:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ow-server-selector"
        self.cache = self.directory / "servers.json"
        self.data = read_feed(BUNDLE)
        self.notice = "Using the bundled starter list. Checking for updates…"
        for path in (self.cache, ROOT_STATE.parent / "servers.json"):
            if path.exists():
                try:
                    self.data = read_feed(path)
                    self.notice = "Using the saved server list."
                except (OSError, ValueError) as exc:
                    self.notice = f"Saved list unavailable: {exc}"
        self.servers = parse_feed(self.data)

    def state(self):
        try:
            return json.loads(ROOT_STATE.read_text())
        except (OSError, ValueError):
            return {"blocked": [], "uid": None, "auto_update": True}

    def update(self):
        data = fetch_feed()
        parse_feed(data)
        atomic_json(self.cache, data, mode=0o600)
        self.data = data
        self.servers = parse_feed(data)
        return "Latest Dropship server list downloaded."

    def apply(self, tokens, auto_update):
        validate_selection(self.servers, tokens)
        if not HELPER.exists():
            raise RuntimeError("Enable firewall control using the setup button first")
        if not shutil.which("pkexec"):
            raise RuntimeError("Install PolicyKit (pkexec) to authenticate firewall changes")
        result = subprocess.run(["pkexec", str(HELPER), "apply"],
                                input=json.dumps({"blocked": tokens, "auto_update": auto_update}),
                                text=True, capture_output=True, timeout=180, env=host_environment())
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Authentication was cancelled; blocks were not changed")
        return json.loads(result.stdout)

    def install_helper(self):
        if not shutil.which("pkexec"):
            raise RuntimeError("Install PolicyKit (pkexec) first; see the release guide")
        # Root cannot normally read a user-owned FUSE AppImage mount. Stage only
        # the helper's source and installer in a regular temporary directory.
        with tempfile.TemporaryDirectory(prefix="ow-selector-setup-") as temporary:
            stage = Path(temporary)
            stage.chmod(0o755)
            shutil.copy2(PROJECT / "install.sh", stage / "install.sh")
            shutil.copytree(PROJECT / "owselector", stage / "owselector", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(PROJECT / "data", stage / "data")
            shutil.copytree(PROJECT / "packaging", stage / "packaging")
            result = subprocess.run(["pkexec", "/usr/bin/bash", str(stage / "install.sh"), "--helper-only"],
                                    text=True, capture_output=True, timeout=180, env=host_environment())
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "Setup was cancelled")
            return result.stdout.strip()
