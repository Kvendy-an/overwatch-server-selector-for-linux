"""Run with a graphical session: python3 tests/smoke_gui.py. Never touches firewall."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from owselector.gui import Selector, GLib, Gtk
from gi.repository import GdkPixbuf

if not Gtk.init_check():
    raise RuntimeError("A graphical display is required for the GTK smoke test")

app = Selector(preview=True)
errors = []
verified = False


def verify():
    global verified
    try:
        assert len(app.rows) == len(app.client.servers)
        icon = Path(__file__).resolve().parent.parent / "packaging/io.github.owselector.Linux.svg"
        assert GdkPixbuf.Pixbuf.new_from_file(str(icon)).get_width() == 128
        app.preset.set_selected(2)  # Europe remains available.
        assert "ams1" not in app.blocked and "gen1" not in app.blocked
        assert "gmec2" in app.blocked
        assert all(row.get_active() == (token in app.blocked) for token, row in app.rows.items())
        app.preset.set_selected(1)  # Unblock everything in the draft selection.
        assert not app.blocked
        app.rows["gmec2"].set_active(True)
        assert app.blocked == {"gmec2"}
        app.apply(["gmec2"])
        assert "disabled" in app.feedback.get_text()
        app.setup()
        assert "installation is disabled" in app.feedback.get_text()
        assert app.apply_button.get_sensitive()
        verified = True
        print("GTK smoke passed: window, region presets, toggles, preview safety.")
    except Exception as exc:
        errors.append(exc)
    finally:
        app.quit()
    return GLib.SOURCE_REMOVE


GLib.timeout_add(700, verify)
app.run([sys.argv[0]])
if errors:
    raise errors[0]
assert verified, "GTK did not activate the preview window"
