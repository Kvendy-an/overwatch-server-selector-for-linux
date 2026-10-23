# AppImage release 0.1.0

Native Overwatch server selector with region presets, individual server blocks, and automatic updates from the maintained Dropship feed.

## Launch

Download or copy `Overwatch-Server-Selector-0.1.0-x86_64.AppImage`, then enable executable permission in your file manager's Properties → Permissions. Double-click to launch.

From a terminal:

```bash
chmod +x Overwatch-Server-Selector-0.1.0-x86_64.AppImage
./Overwatch-Server-Selector-0.1.0-x86_64.AppImage
```

The release bundles Python 3.12, GTK 4, libadwaita, PyGObject, fonts, and supporting libraries. The native GUI does not require a separate Python or GTK installation.

Supported build baseline: **x86_64 Linux with glibc 2.39 or newer**, such as Ubuntu 24.04+, Debian 13+, or Fedora 40+. Older glibc systems, musl distributions, and ARM are outside this release's target. A working Wayland or X11 desktop session is required.

If FUSE mounting is unavailable, the runtime supports extraction and launch:

```bash
./Overwatch-Server-Selector-0.1.0-x86_64.AppImage --appimage-extract-and-run
```

## Enable firewall control

Click **Enable firewall control** in the header and authenticate. This installs a root-owned helper and the automatic-update timer. It does not create blocks until you apply a selection. The helper is copied outside the AppImage so it keeps working when the image is closed, moved, or deleted.

The host needs **nftables, PolicyKit (`pkexec`), systemd, and system Python 3.10+** for this privileged helper. These host services cannot operate inside the portable GUI runtime. If they are missing, install them before clicking setup:

```bash
# Fedora
sudo dnf install nftables polkit python3

# Ubuntu / Debian
sudo apt install nftables pkexec python3
```

Run the AppImage as your regular desktop user. Use the setup button for administrator authentication; do not run the whole AppImage with sudo. On a machine where the source app's helper is already installed, setup is unnecessary.

Keep **Automatic updates** enabled and apply your selection to refresh saved blocks hourly, even when the AppImage is closed. See `README.md` for firewall scope, recovery, and uninstall instructions. Blocking affects all apps for your account using the selected IP ranges.

## Verify and diagnose

The release includes a SHA-256 checksum file:

```bash
sha256sum -c Overwatch-Server-Selector-0.1.0-x86_64.AppImage.sha256
```

Use `--preview` to open the interface with network downloads, helper installation, and firewall changes disabled. Use `self-test` to run a short, offline native interface test that exits automatically:

```bash
./Overwatch-Server-Selector-0.1.0-x86_64.AppImage --preview
./Overwatch-Server-Selector-0.1.0-x86_64.AppImage self-test
```

This is an unsigned release. The bundled AppImage build tools and runtime are verified against the pinned checksums in `packaging/appimage/tools.sha256`. Runtime package versions and license texts are included inside the image under `usr/share/doc`.

## Build from source

Requires Podman (or Docker), curl, and Python 3 on the build host. The build installs its dependencies in an Ubuntu 24.04 container and writes the AppDir under `build/` and release artifacts under `dist/`.

```bash
./packaging/appimage/build.sh

# Alternatively:
CONTAINER_ENGINE=docker ./packaging/appimage/build.sh
```

The script uses temporary storage under `/tmp/ow-selector-containers` for Podman. Override `APPIMAGE_CONTAINER_STORAGE` and `APPIMAGE_CONTAINER_RUNROOT` if desired. Build tool downloads use continuous release URLs with pinned SHA-256 hashes; if an upstream continuous release changes, the build deliberately stops on a checksum mismatch. Retain the verified tools under `build/tools`, or review and update their checksums before rebuilding.

The app's source is available in the source archive and inside the AppImage. To replace a bundled LGPL library or inspect the package:

```bash
./Overwatch-Server-Selector-0.1.0-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun --preview
```

Ubuntu runtime package versions are recorded in `usr/share/doc/runtime-packages.txt`; their source packages are available from the [Ubuntu archive](https://archive.ubuntu.com/ubuntu/pool/). Individual copyright and license files are included under `usr/share/doc/runtime-licenses`. The AppImage runtime comes from [AppImage/type2-runtime](https://github.com/AppImage/type2-runtime).
