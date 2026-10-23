"""Render the app preview for visual QA; never touches firewall rules."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from owselector.gui import Selector, GLib, Gtk
import gi
gi.require_version("Graphene", "1.0")
from gi.repository import Graphene

app = Selector(preview=True)
errors = []


def capture():
    try:
        window = app.window
        paintable = Gtk.WidgetPaintable.new(window)
        snapshot = Gtk.Snapshot.new()
        width, height = window.get_width(), window.get_height()
        paintable.snapshot(snapshot, width, height)
        node = snapshot.to_node()
        renderer = window.get_renderer()
        viewport = Graphene.Rect().init(0, 0, width, height)
        texture = renderer.render_texture(node, viewport)
        path = Path(__file__).resolve().parent.parent / "artifacts" / "preview.png"
        path.parent.mkdir(exist_ok=True)
        texture.save_to_png(str(path))
        print(path)
    except Exception as exc:
        errors.append(exc)
    finally:
        app.quit()
    return GLib.SOURCE_REMOVE


GLib.timeout_add(1000, capture)
app.run([sys.argv[0]])
if errors:
    raise errors[0]
