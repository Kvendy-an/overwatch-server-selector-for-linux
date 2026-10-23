#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
helper_only=false
if [[ ${1:-} == --helper-only && $# -eq 1 ]]; then
    helper_only=true
elif [[ $# -ne 0 ]]; then
    echo 'Usage: install.sh [--helper-only]' >&2
    exit 1
fi
if [[ ${EUID} -ne 0 ]]; then
    echo 'Run this installer with sudo: sudo ./install.sh' >&2
    exit 1
fi
command -v nft >/dev/null || { echo 'Install nftables first. See README.md.' >&2; exit 1; }
command -v pkexec >/dev/null || { echo 'Install PolicyKit first. See README.md.' >&2; exit 1; }
/usr/bin/python3 -I -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
if ! $helper_only; then
 /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")' || {
    echo 'Install GTK 4, libadwaita and Python GObject first. See README.md.' >&2
    exit 1
}
fi
# Refuse pre-existing symlink directories at privilege boundaries.
for directory in /usr/local/lib/ow-server-selector /usr/local/lib/ow-server-selector/owselector /usr/local/lib/ow-server-selector/data /var/lib/ow-server-selector; do
    [[ ! -L "$directory" ]] || { echo "Refusing symlink: $directory" >&2; exit 1; }
    install -d -o root -g root -m 755 "$directory"
done
install -o root -g root -m 644 owselector/*.py /usr/local/lib/ow-server-selector/owselector/
install -o root -g root -m 644 data/servers.json data/DROPSHIP-LICENSE /usr/local/lib/ow-server-selector/data/
install -d -o root -g root -m 755 /usr/local/libexec /usr/local/bin
install -o root -g root -m 755 packaging/ow-server-selector-helper /usr/local/libexec/
if ! $helper_only; then
    install -o root -g root -m 755 packaging/ow-server-selector /usr/local/bin/
    install -d -o root -g root -m 755 /usr/local/share/applications /usr/local/share/icons/hicolor/scalable/apps
    install -o root -g root -m 644 packaging/io.github.owselector.Linux.desktop /usr/local/share/applications/
    install -o root -g root -m 644 packaging/io.github.owselector.Linux.svg /usr/local/share/icons/hicolor/scalable/apps/
fi
install -o root -g root -m 644 packaging/ow-server-selector.service packaging/ow-server-selector.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ow-server-selector.timer
if $helper_only; then
    echo 'Firewall helper and automatic-update timer installed. Return to the AppImage.'
else
    echo 'Installed. Open Overwatch Server Selector from your app menu.'
fi
echo 'No server blocks are created until you apply a selection.'
