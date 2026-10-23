"""GTK 4 / libadwaita desktop interface."""

import sys
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from .client import Client, HELPER

REGIONS = {
    "Europe": {"ams1", "gen1"},
    "Middle East": {"gmec2"},
    "North America": {"las1", "ord1", "gue4"},
    "South America": {"gbr1"},
    "Asia": {"gsg1", "gtk1", "tpe1", "icn1"},
    "Oceania": {"syd2"},
}

CSS = b"""
.hero { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; }
.eyebrow { color: #f2a65a; font-weight: 700; letter-spacing: 2px; font-size: 11px; }
.accent-button { background: #e88a37; color: #201b16; font-weight: 700; }
.status-card { padding: 18px; border-radius: 14px; background: alpha(@accent_bg_color, 0.10); }
.muted { opacity: 0.7; }
.mono { font-family: monospace; font-size: 11px; }
.server-row { padding-top: 3px; padding-bottom: 3px; }
"""


def label(text, css=None):
    widget = Gtk.Label(label=text, xalign=0, wrap=True)
    if css:
        widget.add_css_class(css)
    return widget


class Selector(Adw.Application):
    def __init__(self, preview=False):
        flags = Gio.ApplicationFlags.NON_UNIQUE if preview else Gio.ApplicationFlags.DEFAULT_FLAGS
        super().__init__(application_id="io.github.owselector.Linux", flags=flags)
        self.preview = preview
        self.client = Client()
        self.busy = False
        self.rows = {}
        self.state = self.client.state()
        self.blocked = set(self.state["blocked"])
        self.window = None
        self.connect("activate", self.activate)

    def activate(self, *_):
        if self.window:
            self.window.present()
            return
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        self.window = Adw.ApplicationWindow(application=self, title="Overwatch Server Selector",
                                            default_width=740, default_height=850)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(self.window.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        title = label("SERVER SELECTOR", "eyebrow")
        title.set_wrap(False)
        header.set_title_widget(title)
        self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh server list")
        self.refresh_button.connect("clicked", lambda *_: self.update_feed())
        header.pack_end(self.refresh_button)
        self.setup_button = Gtk.Button(label="Enable firewall control")
        self.setup_button.connect("clicked", lambda *_: self.setup())
        self.setup_button.set_visible(not HELPER.exists())
        header.pack_start(self.setup_button)
        outer.append(header)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=680, tightening_threshold=550)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22,
                               margin_start=24, margin_end=24, margin_top=20, margin_bottom=24)
        clamp.set_child(self.content)
        scroll.set_child(clamp)
        outer.append(scroll)
        self.content.append(label("OVERWATCH  /  LINUX", "eyebrow"))
        self.content.append(label("Your next match.\nYour preferred servers.", "hero"))
        self.content.append(label("Block the servers you want to avoid. Apply before launching Overwatch.", "muted"))
        self.content.append(label("Blocks apply to all apps for your Linux account using these server IP ranges, including shared cloud addresses.", "muted"))
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("status-card")
        self.summary = label("", "heading")
        self.detail = label("")
        card.append(self.summary)
        card.append(self.detail)
        self.content.append(card)
        presets = Adw.PreferencesGroup(title="Quick selection", description="Keep a region available and block the others, or choose individual servers below.")
        row = Adw.ActionRow(title="Preferred region")
        self.preset = Gtk.DropDown.new_from_strings(["Custom", "All servers available", *REGIONS.keys()])
        self.preset.set_valign(Gtk.Align.CENTER)
        self.preset.connect("notify::selected", self.choose_preset)
        row.add_suffix(self.preset)
        presets.add(row)
        self.content.append(presets)
        self.server_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        self.content.append(self.server_box)
        self.build_rows()
        updates = Adw.PreferencesGroup(title="Server list", description="Maintained by Dropship · downloaded over HTTPS")
        self.auto = Adw.SwitchRow(title="Automatic updates", subtitle="Refresh saved blocks hourly, even when this app is closed.")
        self.auto.set_active(self.state.get("auto_update", True))
        self.auto.connect("notify::active", lambda *_: self.update_summary())
        updates.add(self.auto)
        self.content.append(updates)
        self.feed_status = label(self.client.notice, "muted")
        self.content.append(self.feed_status)
        self.content.append(label("Blocks affect all apps for your Linux account connecting to these IP ranges, including shared cloud addresses. They remain after closing the app and are restored after reboot by the installed service.", "muted"))
        self.content.append(label("Server blocking influences matchmaking; a preferred server is not guaranteed. If a match cannot connect, use Unblock all immediately.", "muted"))
        self.feedback = label("")
        self.feedback.set_selectable(True)
        self.content.append(self.feedback)
        actions = Gtk.Box(spacing=12, margin_start=24, margin_end=24, margin_top=12, margin_bottom=18)
        self.unblock_button = Gtk.Button(label="Unblock all", hexpand=True)
        self.unblock_button.add_css_class("destructive-action")
        self.unblock_button.connect("clicked", lambda *_: self.apply([]))
        self.apply_button = Gtk.Button(label="Apply selection", hexpand=True)
        self.apply_button.add_css_class("accent-button")
        self.apply_button.connect("clicked", lambda *_: self.apply(sorted(self.blocked)))
        actions.append(self.unblock_button)
        actions.append(self.apply_button)
        outer.append(actions)
        self.window.set_content(outer)
        self.update_summary()
        self.window.present()
        self.refresh_button.grab_focus()
        if not HELPER.exists():
            self.feedback.set_text("Click Enable firewall control to install the helper and update timer. Setup requires administrator authentication.")
        if self.preview:
            self.feed_status.set_text("Bundled Dropship list · preview mode")
        else:
            self.update_feed()
            GLib.timeout_add_seconds(3600, self.periodic_refresh)

    def build_rows(self):
        while self.server_box.get_first_child():
            self.server_box.remove(self.server_box.get_first_child())
        self.rows.clear()
        grouped = {region: [] for region in REGIONS}
        grouped["Other servers"] = []
        for server in self.client.servers:
            region = next((r for r, ids in REGIONS.items() if server.token in ids), "Other servers")
            grouped[region].append(server)
        for region, servers in grouped.items():
            if not servers:
                continue
            group = Adw.PreferencesGroup(title=region)
            for server in servers:
                row = Adw.SwitchRow(title=server.title.title(),
                                    subtitle=f"{server.token.upper()}  ·  {len(server.networks)} address ranges  ·  switch on to block")
                row.add_css_class("server-row")
                row.set_active(server.token in self.blocked)
                row.connect("notify::active", self.toggle_server, server.token)
                group.add(row)
                self.rows[server.token] = row
            self.server_box.append(group)

    def toggle_server(self, row, _param, token):
        if row.get_active():
            self.blocked.add(token)
        else:
            self.blocked.discard(token)
        if hasattr(self, "preset"):
            self.preset.set_selected(0)
        if hasattr(self, "apply_button"):
            self.update_summary()

    def choose_preset(self, dropdown, _param):
        index = dropdown.get_selected()
        if index == 0:
            return
        available = set() if index == 1 else REGIONS[list(REGIONS)[index - 2]]
        self.blocked = set() if index == 1 else {s.token for s in self.client.servers if s.token not in available}
        self.build_rows()
        self.update_summary()

    def update_summary(self):
        known = {s.token for s in self.client.servers}
        blocked = self.blocked & known
        available = len(known - blocked)
        self.summary.set_text(f"{available} servers available  ·  {len(blocked)} selected to block")
        saved = set(self.state["blocked"])
        if self.blocked != saved or self.auto.get_active() != self.state.get("auto_update", True):
            text = "Selection changed. Apply to update your saved blocks."
        elif saved:
            text = f"{len(saved)} blocks saved for Linux UID {self.state.get('uid')}."
        else:
            text = "No blocks saved. Matchmaking can use any server."
        if self.state.get("error"):
            text += " " + self.state["error"]
        if self.blocked - known:
            text += " Some saved servers were removed from the feed. Unblock all before choosing again."
        self.detail.set_text(text)
        self.apply_button.set_sensitive(not self.busy and available > 0 and not (self.blocked - known))
        self.unblock_button.set_sensitive(not self.busy)
        self.refresh_button.set_sensitive(not self.busy)
        self.setup_button.set_sensitive(not self.busy)
        self.preset.set_sensitive(not self.busy)
        self.auto.set_sensitive(not self.busy)
        for row in self.rows.values():
            row.set_sensitive(not self.busy)

    def background(self, work, done):
        if self.busy:
            return
        self.busy = True
        self.update_summary()
        def execute():
            try:
                result, error = work(), None
            except Exception as exc:
                result, error = None, str(exc)
            GLib.idle_add(finish, result, error)
        def finish(result, error):
            self.busy = False
            done(result, error)
            self.update_summary()
            return GLib.SOURCE_REMOVE
        threading.Thread(target=execute, daemon=True).start()

    def update_feed(self):
        self.feed_status.set_text("Checking Dropship for the latest server list…")
        def done(result, error):
            self.feed_status.set_text(f"Update unavailable; saved list kept. {error}" if error else result)
            if not error:
                self.build_rows()
        self.background(self.client.update, done)

    def periodic_refresh(self):
        # The root timer owns automatic firewall updates; this only refreshes the UI feed.
        if not self.busy:
            self.state = self.client.state()
            self.update_feed()
        return GLib.SOURCE_CONTINUE

    def apply(self, tokens):
        if self.preview:
            self.feedback.set_text("Preview mode: firewall changes are disabled.")
            return
        auto_update = self.auto.get_active()
        self.feedback.set_text("Authenticate to update firewall rules…")
        def done(result, error):
            if error:
                self.feedback.set_text(error)
            else:
                self.state = result
                self.blocked = set(tokens)
                self.build_rows()
                self.preset.set_selected(0)
                self.feedback.set_text("All server blocks removed." if not tokens else "Blocks applied. Launch Overwatch when you’re ready.")
        self.background(lambda: self.client.apply(tokens, auto_update), done)

    def setup(self):
        if self.preview:
            self.feedback.set_text("Preview mode: helper installation is disabled.")
            return
        self.feedback.set_text("Authenticate to install firewall control and automatic updates…")
        def done(result, error):
            self.feedback.set_text(error or result)
            if not error:
                self.setup_button.set_visible(False)
                self.state = self.client.state()
        self.background(self.client.install_helper, done)


def main():
    if not Gtk.init_check():
        print("A graphical desktop session is required. Run the app as your normal desktop user.", file=sys.stderr)
        return 1
    preview = "--preview" in sys.argv
    app = Selector(preview=preview)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
