#!/usr/bin/env bash
set -euo pipefail
test ! -e /usr/bin/python3
test ! -e /usr/lib/x86_64-linux-gnu/libgtk-4.so.1
test ! -e /usr/lib/x86_64-linux-gnu/libadwaita-1.so.0
images=(/src/dist/*.AppImage)
test "${#images[@]}" -eq 1
export APPIMAGE_EXTRACT_AND_RUN=1
export GSETTINGS_BACKEND=memory
export XDG_CACHE_HOME=/tmp/ow-selector-clean-cache
"${images[0]}" list
xvfb-run -a "${images[0]}" self-test
echo 'Clean Ubuntu test passed without host Python, GTK, or libadwaita.'
