"""Stage an AppDir from Ubuntu 24.04's installed runtime dependencies."""
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
APPDIR = ROOT / "build" / "OverwatchServerSelector.AppDir"
LIBDIR = APPDIR / "usr/lib/x86_64-linux-gnu"


def copy(source, destination):
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "test", "tests"))
    else:
        shutil.copy2(source, destination)


def main():
    if Path("/etc/os-release").read_text().find('VERSION_ID="24.04"') == -1:
        raise RuntimeError("Build inside the Ubuntu 24.04 container")
    if APPDIR.exists():
        shutil.rmtree(APPDIR)
    LIBDIR.mkdir(parents=True)
    copy("/usr/bin/python3.12", APPDIR / "usr/bin/python3.12")
    copy("/etc/ssl/certs/ca-certificates.crt", APPDIR / "usr/share/ow-server-selector/ca-certificates.crt")
    copy("/usr/lib/python3.12", APPDIR / "usr/lib/python3.12")
    for package in ("gi", "cairo"):
        copy(Path("/usr/lib/python3/dist-packages") / package, APPDIR / "usr/lib/python3.12/dist-packages" / package)
    copy("/usr/lib/x86_64-linux-gnu/girepository-1.0", LIBDIR / "girepository-1.0")
    for directory in ("gio/modules", "gdk-pixbuf-2.0"):
        copy(Path("/usr/lib/x86_64-linux-gnu") / directory, LIBDIR / directory)
    for directory in ("glib-2.0/schemas", "icons/Adwaita", "icons/hicolor", "fonts/truetype/dejavu", "X11/xkb", "mime"):
        copy(Path("/usr/share") / directory, APPDIR / "usr/share" / directory)
    project = APPDIR / "usr/share/ow-server-selector"
    for directory in ("owselector", "data", "packaging", "tests"):
        copy(ROOT / directory, project / directory)
    for name in ("install.sh", "uninstall.sh", "README.md", "RELEASE.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        copy(ROOT / name, project / name)
    copy(ROOT / "packaging/appimage/AppRun", APPDIR / "AppRun")
    copy(ROOT / "packaging/appimage/fonts.conf", APPDIR / "usr/share/fontconfig/fonts.conf")
    (APPDIR / "AppRun").chmod(0o755)
    desktop = (ROOT / "packaging/io.github.owselector.Linux.desktop").read_text().replace("Exec=/usr/local/bin/ow-server-selector", "Exec=AppRun")
    (APPDIR / "io.github.owselector.Linux.desktop").write_text(desktop)
    copy(ROOT / "packaging/io.github.owselector.Linux.svg", APPDIR / "io.github.owselector.Linux.svg")
    (APPDIR / ".DirIcon").symlink_to("io.github.owselector.Linux.svg")
    copy(ROOT / "packaging/io.github.owselector.Linux.svg", APPDIR / "usr/share/icons/hicolor/scalable/apps/io.github.owselector.Linux.svg")
    # Copy the transitive ELF dependencies, including GI libraries loaded at runtime.
    seeds = [Path("/usr/bin/python3.12")]
    seeds.extend(Path("/usr/lib/x86_64-linux-gnu").glob("libgtk-4.so.*"))
    seeds.extend(Path("/usr/lib/x86_64-linux-gnu").glob("libadwaita-1.so.*"))
    seeds.extend(APPDIR.rglob("*.so"))
    seeds.extend(APPDIR.rglob("*.so.*"))
    visited = set()
    # glibc and the dynamic loader come from the host. Base requirement: glibc 2.39+.
    exclude = re.compile(r"^(ld-linux.*|libc\.so.*|libm\.so.*|libpthread\.so.*|libdl\.so.*|librt\.so.*|libresolv\.so.*)$")
    while seeds:
        source = seeds.pop()
        if source.resolve() in visited:
            continue
        visited.add(source.resolve())
        result = subprocess.run(["ldd", str(source)], text=True, capture_output=True)
        for line in result.stdout.splitlines():
            match = re.search(r"=> (/\S+)", line)
            if not match:
                continue
            dependency = Path(match.group(1))
            if exclude.match(dependency.name):
                continue
            destination = LIBDIR / dependency.name
            if not destination.exists():
                copy(dependency, destination)
                seeds.append(dependency)
    # The libraries behind Gtk/Adw typelibs need explicit copies as ldd does not
    # discover them through the Python executable.
    for source in list(Path("/usr/lib/x86_64-linux-gnu").glob("libgtk-4.so.*")) + list(Path("/usr/lib/x86_64-linux-gnu").glob("libadwaita-1.so.*")):
        copy(source, LIBDIR / source.name)
    # Preserve package copyright/license texts for every installed build package.
    licenses = APPDIR / "usr/share/doc/runtime-licenses"
    for source in Path("/usr/share/doc").glob("*/copyright"):
        copy(source, licenses / source.parent.name / "copyright")
    package_versions = subprocess.check_output(["dpkg-query", "-W", "-f=${Package}\t${Version}\n"], text=True)
    (APPDIR / "usr/share/doc/runtime-packages.txt").write_text(package_versions)
    subprocess.run(["glib-compile-schemas", str(APPDIR / "usr/share/glib-2.0/schemas")], check=True)
    print(f"AppDir ready: {APPDIR}")


if __name__ == "__main__":
    main()
