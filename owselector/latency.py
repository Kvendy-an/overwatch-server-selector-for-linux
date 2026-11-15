"""Bounded, unprivileged ICMP measurements against the feed's public targets."""

import ipaddress
import re
import shutil
import statistics
import subprocess

from .client import host_environment


def measure(target):
    """Return (display text, explanation); no reply is not a latency estimate."""
    try:
        address = ipaddress.ip_address(target)
        if not address.is_global:
            raise ValueError("Non-public target")
    except (ValueError, TypeError):
        return "—", "No public ping target in the server list."
    executable = shutil.which("ping", path="/usr/bin:/bin")
    if not executable:
        return "Unavailable", "Install iputils (ping) to measure latency."
    environment = host_environment()
    environment["LC_ALL"] = "C"
    try:
        result = subprocess.run(
            [executable, "-n", "-6" if address.version == 6 else "-4",
             "-c", "3", "-i", "0.2", "-W", "1", "-w", "4", str(address)],
            capture_output=True, text=True, timeout=5, env=environment,
        )
    except subprocess.TimeoutExpired:
        return "No reply", f"{address} did not respond to ICMP in time."
    except OSError:
        return "Unavailable", "The system ping command could not be started."
    samples = [float(value) for value in re.findall(r"time[=<]([0-9]+(?:\.[0-9]+)?)\s*ms", result.stdout)]
    if samples:
        return f"{statistics.median(samples):.0f} ms", f"Median of {len(samples)} ICMP replies from {address}; in-game latency may differ."
    if result.returncode not in (0, 1):
        return "Unavailable", "ICMP measurement is unavailable on this system."
    return "No reply", f"{address} did not answer ICMP; the game server may still be reachable."
