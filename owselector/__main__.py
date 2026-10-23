"""The CLI remains usable without GTK installed."""

import argparse
import json
import os
from pathlib import Path
import runpy
import sys

from .client import Client
from .core import render_rules


def main():
    parser = argparse.ArgumentParser(description="Overwatch Server Selector for Linux")
    parser.add_argument("command", nargs="?", default="gui", choices=["gui", "list", "update", "preview", "block", "unblock", "status", "setup", "self-test"])
    parser.add_argument("tokens", nargs="*", help="Server IDs to block")
    parser.add_argument("--preview", action="store_true", help="Explore the GUI without firewall changes")
    parser.add_argument("--no-auto-update", action="store_true", help="Disable automatic refresh for this selection")
    args = parser.parse_args()
    if args.command == "self-test":
        if os.geteuid() == 0:
            parser.error("Run the interface self-test as your normal desktop user")
        runpy.run_path(str(Path(__file__).resolve().parent.parent / "tests/smoke_gui.py"), run_name="__main__")
        return 0
    if args.command == "gui":
        if os.geteuid() == 0:
            parser.error("Run the desktop app as your normal user, without sudo")
        try:
            from .gui import main as gui_main
        except (ImportError, ValueError) as exc:
            parser.error(f"GTK 4 and libadwaita are required. See README.md. ({exc})")
        return gui_main()
    client = Client()
    try:
        if args.command == "list":
            for server in client.servers:
                print(f"{server.token:8} {server.title:24} {len(server.networks)} ranges")
        elif args.command == "update":
            print(client.update())
        elif args.command == "preview":
            print(render_rules(client.servers, args.tokens, os.getuid()))
        elif args.command == "status":
            print(json.dumps(client.state(), indent=2))
        elif args.command == "setup":
            print(client.install_helper())
        else:
            tokens = [] if args.command == "unblock" else args.tokens
            print(json.dumps(client.apply(tokens, not args.no_auto_update), indent=2))
    except Exception as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
