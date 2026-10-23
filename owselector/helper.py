"""Root helper. Only the installed root-owned copy is invoked by the GUI."""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys

from .core import BUNDLE, MAX_BYTES, TABLE, atomic_json, fetch_feed, parse_feed, read_feed, render_rules

STATE_DIR = Path("/var/lib/ow-server-selector")
STATE = STATE_DIR / "state.json"
CACHE = STATE_DIR / "servers.json"
NFT = "/usr/sbin/nft" if Path("/usr/sbin/nft").exists() else "/usr/bin/nft"


def stamp():
    return datetime.now(timezone.utc).isoformat()


def run_nft(args, script=None):
    return subprocess.run([NFT, *args], input=script, text=True, capture_output=True,
                          timeout=30, env={"PATH": "/usr/sbin:/usr/bin", "LC_ALL": "C"})


def table_exists():
    result = run_nft(["-j", "list", "tables"])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Cannot read nftables")
    tables = json.loads(result.stdout).get("nftables", [])
    return any(item.get("table", {}).get("family") == "inet" and
               item.get("table", {}).get("name") == TABLE for item in tables)


def apply_rules(servers, tokens, uid):
    script = render_rules(servers, tokens, uid, exists=table_exists())
    if not script:
        return
    # Check and commit the same complete transaction. A failed commit retains old rules.
    for args in (["--check", "-f", "-"], ["-f", "-"]):
        result = run_nft(args, script)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "nftables rejected the rules")


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"blocked": [], "uid": None, "auto_update": True}


def caller_uid():
    raw = os.environ.get("PKEXEC_UID") or os.environ.get("SUDO_UID")
    if raw is None:
        raise ValueError("Apply must be called through pkexec or sudo by a regular user")
    uid = int(raw)
    if uid < 1000:
        raise ValueError("Use a regular user account")
    pwd.getpwuid(uid)
    return uid


def saved_feed():
    return read_feed(CACHE if CACHE.exists() else BUNDLE)


def apply_request(request, uid):
    if not isinstance(request, dict) or set(request) != {"blocked", "auto_update"}:
        raise ValueError("Expected blocked IDs and automatic-update preference")
    if type(request["auto_update"]) is not bool:
        raise ValueError("Automatic-update preference must be boolean")
    previous = load_state()
    if previous["uid"] not in (None, uid) and previous["blocked"]:
        raise ValueError("Another account owns the current blocks; unblock them first")
    # Unblocking works even if the feed is corrupt or unavailable.
    data = None
    if request["blocked"] == []:
        servers = ()
    else:
        try:
            data = fetch_feed()
        except Exception:
            data = saved_feed()
        servers = parse_feed(data)
    apply_rules(servers, request["blocked"], uid)
    if data is not None:
        atomic_json(CACHE, data)
    state = {"blocked": request["blocked"], "uid": uid,
             "auto_update": request["auto_update"], "applied_at": stamp(),
             "last_checked": previous.get("last_checked"), "error": None}
    atomic_json(STATE, state)
    return state


def refresh():
    state = load_state()
    if not state["blocked"]:
        return state
    try:
        data = saved_feed()
        if state["auto_update"]:
            data = fetch_feed()
        # Removed IDs stop the refresh, retaining the last working firewall and cache.
        apply_rules(parse_feed(data), state["blocked"], state["uid"])
        atomic_json(CACHE, data)
        state.update(applied_at=stamp(), last_checked=stamp(), error=None)
        atomic_json(STATE, state)
    except Exception as exc:
        # At boot restore the last good list if the internet is unavailable.
        try:
            apply_rules(parse_feed(saved_feed()), state["blocked"], state["uid"])
        except Exception as fallback:
            state["error"] = f"Update failed: {exc}. Restoring saved blocks failed: {fallback}"
        else:
            state["error"] = f"Update failed; saved blocks retained: {exc}"
            state["applied_at"] = stamp()
        atomic_json(STATE, state)
        raise RuntimeError(state["error"]) from exc
    return state


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["apply", "refresh", "disable", "status"])
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        parser.error("This helper requires administrator authentication")
    STATE_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
    with (STATE_DIR / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if args.action == "apply":
                raw = sys.stdin.buffer.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("Request too large")
                state = apply_request(json.loads(raw), caller_uid())
            elif args.action == "refresh":
                state = refresh()
            elif args.action == "disable":
                if table_exists():
                    result = run_nft(["-f", "-"], f"delete table inet {TABLE}\n")
                    if result.returncode:
                        raise RuntimeError(result.stderr.strip())
                state = load_state()
                state.update(blocked=[], error=None, applied_at=stamp())
                atomic_json(STATE, state)
            else:
                state = load_state()
                state["table_present"] = table_exists()
            print(json.dumps(state))
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
