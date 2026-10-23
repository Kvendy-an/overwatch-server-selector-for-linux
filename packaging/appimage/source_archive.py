"""Ship the exact project sources alongside each AppImage release."""
import hashlib
from pathlib import Path
import shutil
import sys
import tarfile

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from owselector import __version__

dist = root / "dist"
name = f"overwatch-server-selector-{__version__}"
paths = []
for directory in ("owselector", "data", "packaging", "tests"):
    paths.extend(p for p in (root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
for filename in ("README.md", "RELEASE.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "install.sh", "uninstall.sh", ".gitignore", ".containerignore", ".dockerignore"):
    paths.append(root / filename)
with tarfile.open(dist / f"{name}-source.tar.gz", "w:gz") as archive:
    for path in sorted(paths):
        archive.add(path, arcname=f"{name}/{path.relative_to(root)}")
shutil.copy2(root / "RELEASE.md", dist / "RELEASE.md")
artifacts = sorted([*dist.glob("*.AppImage"), *dist.glob("*-source.tar.gz")])
checksums = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in artifacts]
(dist / "SHA256SUMS").write_text("".join(checksums))
