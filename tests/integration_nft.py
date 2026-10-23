"""Compile and apply rules inside a disposable network namespace, never on the host."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from owselector.core import BUNDLE, TABLE, parse_feed, read_feed, render_rules


def main():
    if len(sys.argv) == 1:
        host_namespace = os.readlink("/proc/self/ns/net")
        return subprocess.run(["unshare", "--user", "--map-root-user", "--net", sys.executable,
                               __file__, host_namespace]).returncode
    if len(sys.argv) != 2 or sys.argv[1] == os.readlink("/proc/self/ns/net"):
        raise RuntimeError("Refusing to operate outside an isolated network namespace")
    nft = shutil.which("nft")
    if not nft:
        raise RuntimeError("nftables is required")
    servers = parse_feed(read_feed(BUNDLE))
    def run(args, script=None):
        result = subprocess.run([nft, *args], input=script, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result
    run(["-f", "-"], "table inet unrelated_test {\n chain output {\n type filter hook output priority 0; policy accept;\n }\n}\n")
    for tokens, exists in [(["gmec2"], False), (["gbr1", "gsg1", "gtk1", "gue4"], True), ([], True)]:
        script = render_rules(servers, tokens, 1000, exists)
        run(["--check", "-f", "-"], script)
        run(["-f", "-"], script)
        tables = json.loads(run(["-j", "list", "tables"]).stdout)["nftables"]
        names = {x["table"]["name"] for x in tables if "table" in x}
        assert "unrelated_test" in names
        assert (TABLE in names) == bool(tokens)
    print("nftables integration passed: IPv4/IPv6 load, replacement, unblock, other table retained.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
