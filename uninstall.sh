#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then
    echo 'Run this uninstaller with sudo: sudo ./uninstall.sh' >&2
    exit 1
fi
systemctl disable --now ow-server-selector.timer
systemctl stop ow-server-selector.service
# Stop if blocks cannot be removed. Keep the helper available for recovery.
/usr/local/libexec/ow-server-selector-helper disable
rm -f /etc/systemd/system/ow-server-selector.service /etc/systemd/system/ow-server-selector.timer
rm -f /usr/local/bin/ow-server-selector /usr/local/libexec/ow-server-selector-helper
rm -f /usr/local/share/applications/io.github.owselector.Linux.desktop /usr/local/share/icons/hicolor/scalable/apps/io.github.owselector.Linux.svg
rm -rf -- /usr/local/lib/ow-server-selector
systemctl daemon-reload
echo 'Uninstalled and removed server blocks. Saved data remains in /var/lib/ow-server-selector.'
