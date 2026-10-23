"""Relocate runtime loader paths before importing GTK."""
import os
from pathlib import Path
import sys
import tempfile

project = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project))
appdir = Path(sys.executable).resolve().parents[2]
cache = appdir / "usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache"

with tempfile.TemporaryDirectory(prefix="ow-selector-loaders-") as temporary:
    if cache.exists():
        relocated = Path(temporary) / "loaders.cache"
        relocated.write_text(cache.read_text().replace("/usr/lib/x86_64-linux-gnu/", str(appdir / "usr/lib/x86_64-linux-gnu") + "/"))
        os.environ["GDK_PIXBUF_MODULE_FILE"] = str(relocated)
    from owselector.__main__ import main
    sys.exit(main())
