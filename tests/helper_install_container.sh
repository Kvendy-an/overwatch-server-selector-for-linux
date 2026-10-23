#!/usr/bin/env bash
# This fixture only runs in the disposable packaging test container.
set -euo pipefail
if [[ ${OW_SELECTOR_INSTALL_TEST_CONTAINER:-} != 1 || $EUID -ne 0 || ! -f /run/.containerenv ]]; then
    echo 'Run this fixture only through the disposable Podman test container.' >&2
    exit 1
fi
mkdir -p /tmp/ow-selector-test-bin
cat > /tmp/ow-selector-test-bin/systemctl <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >> /tmp/ow-selector-systemctl.log
EOF
cat > /tmp/ow-selector-test-bin/pkexec <<'EOF'
#!/bin/sh
exit 0
EOF
cat > /usr/bin/nft <<'EOF'
#!/bin/sh
printf '{"nftables": []}\n'
EOF
chmod +x /usr/bin/nft /tmp/ow-selector-test-bin/*
export PATH="/tmp/ow-selector-test-bin:$PATH"
bash /src/install.sh --helper-only
test -x /usr/local/libexec/ow-server-selector-helper
test ! -e /usr/local/bin/ow-server-selector
test ! -e /usr/local/share/applications/io.github.owselector.Linux.desktop
test "$(stat -c %u /usr/local/lib/ow-server-selector/owselector/helper.py)" = 0
grep -Fx 'enable --now ow-server-selector.timer' /tmp/ow-selector-systemctl.log
/usr/local/libexec/ow-server-selector-helper status
echo 'Helper-only installation passed inside container; systemctl and nft were mocked.'
