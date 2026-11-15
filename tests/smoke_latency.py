"""Offline GTK test of background ping delivery; never changes the firewall."""
from pathlib import Path
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from owselector.gui import Selector, GLib, Gio

app = Selector()
app.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
app.state = {"blocked": ["gmec2"], "auto_update": True}
app.blocked = {"gmec2"}
app.client.update = lambda: "Offline test feed"
errors = []
heartbeats = 0
finished = False
calls = []


def fake_measure(target):
    calls.append(target)
    time.sleep(0.15)
    return "42 ms", "Test measurement"


def verify():
    global heartbeats, finished
    heartbeats += 1
    if app.window is None or app.busy or app.pinging:
        return GLib.SOURCE_CONTINUE
    try:
        assert calls, "Measurements did not run"
        assert heartbeats >= 3, "Main loop did not stay responsive"
        assert app.ping_labels['gmec2'].get_text() == 'Blocked'
        blocked = next(s for s in app.client.servers if s.token == 'gmec2')
        assert blocked.ping not in calls
        for server in app.client.servers:
            if server.token != 'gmec2':
                assert app.ping_labels[server.token].get_text() == '42 ms'
        app.preset.set_selected(2)
        assert app.ping_labels['ams1'].get_text() == '42 ms'
        assert app.ping_button.get_sensitive()
        assert app.ping_button.get_child().get_gicon().get_file().get_basename() == 'signal-bars-symbolic.svg'
        assert app.ping_button.get_tooltip_text() == 'Check server ping'
        finished = True
        print('Latency GTK smoke passed: background delivery, responsive main loop, saved blocks, row rebuilds.')
    except Exception as exc:
        errors.append(exc)
    finally:
        app.quit()
    return GLib.SOURCE_REMOVE


def timeout():
    errors.append(AssertionError('Ping UI test timed out'))
    app.quit()
    return GLib.SOURCE_REMOVE


GLib.timeout_add(50, verify)
GLib.timeout_add_seconds(10, timeout)
with patch('owselector.gui.measure', side_effect=fake_measure):
    app.run(['latency-smoke'])
if errors:
    raise errors[0]
assert finished
