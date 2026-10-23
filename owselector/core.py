"""Validated server data and deterministic nftables generation (no privileges)."""

from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.request import Request, urlopen

FEED_URL = "https://stowmyy.github.io/dropship/ips.json"
MAX_BYTES = 2_000_000
TABLE = "ow_server_selector"
BUNDLE = Path(__file__).resolve().parent.parent / "data" / "servers.json"


@dataclass(frozen=True)
class Server:
    token: str
    title: str
    networks: tuple


def parse_feed(data):
    try:
        records = data["servers"]["overwatch"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Server list has an unsupported format") from exc
    if not isinstance(records, list) or not 2 <= len(records) <= 64:
        raise ValueError("Server list must contain 2–64 servers")
    servers, seen = [], set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid server record")
        token, title, block = (record.get(k) for k in ("token", "title", "block"))
        if not isinstance(token, str) or not re.fullmatch(r"[a-z0-9]{2,16}", token):
            raise ValueError("Invalid server ID")
        if token in seen:
            raise ValueError("Duplicate server ID")
        if not isinstance(title, str) or not 1 <= len(title) <= 80 or any(ord(c) < 32 for c in title):
            raise ValueError("Invalid server name")
        if not isinstance(block, str) or not block or len(block) > 100_000:
            raise ValueError("Invalid address list")
        parts = block.split(",")
        if len(parts) > 4096:
            raise ValueError("Too many address ranges")
        networks = []
        for part in parts:
            network = ipaddress.ip_network(part.strip(), strict=True)
            if network.prefixlen < (16 if network.version == 4 else 32):
                raise ValueError("Address range is too broad")
            if not network.is_global or not network.network_address.is_global or not network.broadcast_address.is_global:
                raise ValueError("Only public server addresses are accepted")
            networks.append(network)
        seen.add(token)
        servers.append(Server(token, title, tuple(networks)))
    return tuple(servers)


def read_feed(path):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("Server list is too large")
    data = json.loads(raw)
    parse_feed(data)
    return data


def fetch_feed():
    request = Request(FEED_URL, headers={"User-Agent": "ow-server-selector-linux/0.1"})
    with urlopen(request, timeout=20) as response:
        if not response.geturl().startswith("https://"):
            raise ValueError("The server list must use HTTPS")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Downloaded server list is too large")
    data = json.loads(raw)
    parse_feed(data)
    return data


def atomic_json(path, data, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_selection(servers, tokens):
    if not isinstance(tokens, list) or any(not isinstance(t, str) for t in tokens):
        raise ValueError("Blocked servers must be a list of IDs")
    if len(tokens) != len(set(tokens)):
        raise ValueError("Duplicate selected server")
    known = {s.token for s in servers}
    unknown = set(tokens) - known
    if unknown:
        raise ValueError("Server IDs no longer in the list: " + ", ".join(sorted(unknown)))
    if tokens and set(tokens) == known:
        raise ValueError("Leave at least one server unblocked")
    return set(tokens)


def render_rules(servers, tokens, uid, exists=False):
    """Only operate on our table; all addresses and IDs validated before rendering."""
    if type(uid) is not int or uid < 1000 or uid > 2**32 - 2:
        raise ValueError("Select a regular Linux user account (UID >= 1000)")
    blocked = validate_selection(servers, tokens)
    lines = [f"delete table inet {TABLE}"] if exists else []
    if not blocked:
        return "\n".join(lines) + ("\n" if lines else "")
    networks = [n for s in servers if s.token in blocked for n in s.networks]
    lines.append(f"table inet {TABLE} {{")
    families = []
    for version, name, kind in ((4, "blocked_v4", "ipv4_addr"), (6, "blocked_v6", "ipv6_addr")):
        collapsed = list(ipaddress.collapse_addresses(n for n in networks if n.version == version))
        if collapsed:
            families.append((version, name))
            addresses = ", ".join(str(n) for n in collapsed)
            lines.extend([f"  set {name} {{", f"    type {kind}; flags interval;", f"    elements = {{ {addresses} }}", "  }"])
    lines.extend(["  chain output {", "    type filter hook output priority 10; policy accept;"])
    for version, name in families:
        family = "ip" if version == 4 else "ip6"
        lines.append(f'    meta skuid {uid} {family} daddr @{name} counter reject with icmpx type admin-prohibited')
    lines.extend(["  }", "}"])
    return "\n".join(lines) + "\n"
