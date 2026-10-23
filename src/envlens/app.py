"""Polished GTK4 dashboard for comparing captured execution environments."""
from __future__ import annotations

import datetime as dt

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gdk, Gio, GObject, Gtk, Pango

from .snapshots import compare, data_dir, load_all, remove
from . import __version__

APP_ID = "io.github.stevenmcsorley.EnvLens"
SAFE_HINTS = ("PATH", "PWD", "HOME", "SHELL", "LANG", "TERM", "DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE")


def install_style() -> None:
    display = Gdk.Display.get_default()
    if display is None:
        return
    provider = Gtk.CssProvider()
    provider.load_from_path(str(__import__("pathlib").Path(__file__).parent / "data/style.css"))
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class EnvRow(GObject.Object):
    __gtype_name__ = "EnvLensEnvRow"

    def __init__(self, name, status, before, after):
        super().__init__()
        self.name, self.status, self.before, self.after = name, status, before, after


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="EnvLens", default_width=1160, default_height=850)
        self.add_css_class("envlens-window")
        self.captures = load_all()
        self.left_index = 0
        self.right_index = self._second_context()
        self.query = ""
        self.hide_same = True
        self._popover = None

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(outer)
        header = Adw.HeaderBar()
        header.add_css_class("envlens-header")
        brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        logo = Gtk.Label(label="⌘")
        logo.add_css_class("envlens-logo")
        brand.append(logo)
        brand_labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        brand_labels.set_valign(Gtk.Align.CENTER)
        name = Gtk.Label(label="EnvLens", xalign=0)
        name.add_css_class("envlens-brand")
        brand_labels.append(name)
        sub = Gtk.Label(label="Execution environment debugger", xalign=0)
        sub.add_css_class("envlens-brand-sub")
        brand_labels.append(sub)
        brand.append(brand_labels)
        header.set_title_widget(brand)
        self.status = Gtk.Label(label="NO CAPTURES")
        self.status.add_css_class("envlens-header-badge")
        header.pack_start(self.status)
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh captures")
        refresh.connect("clicked", self.refresh)
        header.pack_end(refresh)
        outer.append(header)

        self.toast = Adw.ToastOverlay()
        outer.append(self.toast)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        root.set_margin_start(26)
        root.set_margin_end(26)
        root.set_margin_top(20)
        root.set_margin_bottom(18)
        self.toast.set_child(root)

        self.hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        self.hero.add_css_class("envlens-hero")
        hero_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=11, hexpand=True, valign=Gtk.Align.CENTER)
        hero_content.set_margin_start(24)
        hero_content.set_margin_top(19)
        hero_content.set_margin_bottom(19)
        self.hero.append(hero_content)
        eyebrow = Gtk.Label(label="ONE CLEAR ANSWER TO ENVIRONMENT MISMATCHES", xalign=0)
        eyebrow.add_css_class("envlens-eyebrow")
        hero_content.append(eyebrow)
        headline = Gtk.Label(label="Why does it work here,\nbut not over there?", xalign=0)
        headline.add_css_class("envlens-headline")
        headline.set_wrap(True)
        hero_content.append(headline)
        self.hero_subtitle = Gtk.Label(label="Compare what your terminal and IDE actually pass to a command.", xalign=0)
        self.hero_subtitle.add_css_class("envlens-hero-sub")
        self.hero_subtitle.set_wrap(True)
        hero_content.append(self.hero_subtitle)
        self.hero.append(self._hero_art())
        root.append(self.hero)

        self.capture_card = self._build_capture_card()
        root.append(self.capture_card)
        self.compare_card = self._build_compare_card()
        self.compare_card.set_vexpand(True)
        root.append(self.compare_card)
        self.update_captures()

    def _hero_art(self):
        art = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9, valign=Gtk.Align.CENTER)
        art.add_css_class("envlens-hero-art")
        art.set_margin_end(22)
        for label, icon, accent in (("Terminal", "utilities-terminal-symbolic", "terminal"),
                                    ("IDE task", "applications-engineering-symbolic", "ide"),
                                    ("Actual difference", "view-refresh-symbolic", "diff")):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("envlens-art-row")
            row.add_css_class(accent)
            image = Gtk.Image.new_from_icon_name(icon)
            image.set_pixel_size(16)
            row.append(image)
            text = Gtk.Label(label=label, xalign=0, hexpand=True)
            row.append(text)
            row.append(Gtk.Label(label="···" if accent != "diff" else "↔"))
            art.append(row)
        return art

    def _build_capture_card(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("envlens-card")
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        top.set_margin_start(16); top.set_margin_end(16); top.set_margin_top(13)
        heading = Gtk.Label(label="Capture two contexts", xalign=0, hexpand=True)
        heading.add_css_class("envlens-section-title")
        top.append(heading)
        self.capture_count = Gtk.Label(label="0 / 2")
        self.capture_count.add_css_class("envlens-count")
        top.append(self.capture_count)
        card.append(top)

        steps = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        steps.set_margin_start(16); steps.set_margin_end(16)
        for title, label in (("1", "Run in your terminal"), ("2", "Run in your IDE terminal/task")):
            step = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
            dot = Gtk.Label(label=title)
            dot.add_css_class("envlens-step-dot")
            step.append(dot)
            text = Gtk.Label(label=label, xalign=0)
            text.add_css_class("envlens-step-text")
            step.append(text)
            steps.append(step)
        card.append(steps)

        command_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        command_row.set_margin_start(16); command_row.set_margin_end(16); command_row.set_margin_bottom(13)
        command = Gtk.Label(label="env -0 | envlens capture --label 'Terminal'", xalign=0, hexpand=True)
        command.add_css_class("envlens-code")
        command.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        command.set_selectable(True)
        command_row.append(command)
        copy = Gtk.Button(label="Copy command")
        copy.add_css_class("suggested-action")
        copy.connect("clicked", self.copy_command)
        command_row.append(copy)
        command_row.append(Gtk.Button(label="IDE version", action_name="win.copy-ide-command"))
        card.append(command_row)

        privacy = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        privacy.add_css_class("envlens-privacy")
        privacy.set_margin_start(16); privacy.set_margin_end(16); privacy.set_margin_bottom(13)
        lock = Gtk.Image.new_from_icon_name("changes-prevent-symbolic")
        privacy.append(lock)
        privacy_label = Gtk.Label(label="Secret-like values are never saved. Their fingerprints only show whether they match.", xalign=0, hexpand=True)
        privacy_label.set_wrap(True)
        privacy_label.add_css_class("envlens-privacy-text")
        privacy.append(privacy_label)
        card.append(privacy)
        return card

    def _build_compare_card(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("envlens-card")
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        toolbar.set_margin_start(16); toolbar.set_margin_end(16); toolbar.set_margin_top(13); toolbar.set_margin_bottom(10)
        title = Gtk.Label(label="Environment comparison", xalign=0, hexpand=True)
        title.add_css_class("envlens-section-title")
        toolbar.append(title)
        self.left_dropdown = Gtk.DropDown(model=Gtk.StringList.new(["Capture A"]))
        self.left_dropdown.set_size_request(165, -1)
        self.left_dropdown.connect("notify::selected", self.on_select)
        toolbar.append(self.left_dropdown)
        between = Gtk.Label(label="compared with")
        between.add_css_class("envlens-muted")
        toolbar.append(between)
        self.right_dropdown = Gtk.DropDown(model=Gtk.StringList.new(["Capture B"]))
        self.right_dropdown.set_size_request(165, -1)
        self.right_dropdown.connect("notify::selected", self.on_select)
        toolbar.append(self.right_dropdown)
        card.append(toolbar)

        filterbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        filterbar.set_margin_start(16); filterbar.set_margin_end(16); filterbar.set_margin_bottom(9)
        self.search = Gtk.SearchEntry(placeholder_text="Find a variable…", hexpand=True)
        self.search.connect("search-changed", self.on_search)
        filterbar.append(self.search)
        self.hide_same_switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=True)
        self.hide_same_switch.connect("notify::active", self.on_hide_same)
        filterbar.append(self.hide_same_switch)
        hide_label = Gtk.Label(label="Hide matching")
        hide_label.add_css_class("envlens-muted")
        filterbar.append(hide_label)
        card.append(filterbar)

        columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        columns.add_css_class("envlens-table-header")
        columns.set_margin_start(14); columns.set_margin_end(14)
        for text, expand, width in (("VARIABLE", False, 210), ("STATUS", False, 120), ("CONTEXT A", True, -1), ("CONTEXT B", True, -1)):
            label = Gtk.Label(label=text, xalign=0, hexpand=expand)
            label.add_css_class("envlens-column-label")
            if width > 0: label.set_size_request(width, -1)
            columns.append(label)
        card.append(columns)

        self.store = Gio.ListStore(item_type=EnvRow)
        self.filter = Gtk.CustomFilter.new(self.matches)
        self.filtered = Gtk.FilterListModel(model=self.store, filter=self.filter)
        self.selection = Gtk.NoSelection(model=self.filtered)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_row)
        factory.connect("bind", self.bind_row)
        view = Gtk.ListView(model=self.selection, factory=factory)
        view.add_css_class("envlens-list")
        scroller = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.set_child(view)
        overlay = Gtk.Overlay()
        overlay.set_child(scroller)
        self.empty_hint = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9,
                                  valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        self.empty_hint.set_margin_start(28); self.empty_hint.set_margin_end(28)
        hint_icon = Gtk.Label(label="↔")
        hint_icon.add_css_class("envlens-empty-icon")
        self.empty_hint.append(hint_icon)
        hint_title = Gtk.Label(label="Your differences will show up here")
        hint_title.add_css_class("envlens-empty-title")
        self.empty_hint.append(hint_title)
        hint_text = Gtk.Label(label="Capture an environment in each context. EnvLens compares the actual values and points out what changed.", wrap=True, justify=Gtk.Justification.CENTER)
        hint_text.set_max_width_chars(74)
        hint_text.add_css_class("envlens-muted")
        self.empty_hint.append(hint_text)
        overlay.add_overlay(self.empty_hint)
        card.append(overlay)

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom.set_margin_start(16); bottom.set_margin_end(16); bottom.set_margin_top(8); bottom.set_margin_bottom(11)
        self.summary = Gtk.Label(label="Capture two contexts to see what differs.", xalign=0, hexpand=True)
        self.summary.add_css_class("envlens-muted")
        bottom.append(self.summary)
        self.delete_button = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Delete selected capture")
        self.delete_button.connect("clicked", self.delete_selected)
        bottom.append(self.delete_button)
        card.append(bottom)
        copy_action = Gio.SimpleAction.new("copy-ide-command", None)
        copy_action.connect("activate", lambda *_: self.copy_ide_command())
        self.add_action(copy_action)
        return card

    def setup_row(self, _factory, item):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("envlens-row")
        for index in range(4):
            cell = Gtk.Label(xalign=0, hexpand=index >= 2)
            cell.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            cell.set_single_line_mode(True)
            if index == 0:
                cell.set_size_request(210, -1)
            elif index == 1:
                cell.set_size_request(120, -1)
                cell.set_halign(Gtk.Align.START)
            row.append(cell)
        item.set_child(row)

    def bind_row(self, _factory, item):
        data = item.get_item()
        cells = item.get_child().get_first_child()
        labels = []
        while cells:
            labels.append(cells); cells = cells.get_next_sibling()
        labels[0].set_label(data.name)
        labels[0].add_css_class("envlens-var-name")
        labels[1].set_label({"same":"Same", "same secret":"Secret matches", "added":"Only in B", "missing":"Only in A", "changed":"Different", "secret differs":"Secret differs"}.get(data.status, data.status))
        labels[1].add_css_class("envlens-status")
        labels[1].add_css_class("status-same" if data.status.startswith("same") else "status-diff")
        labels[1].set_halign(Gtk.Align.START)
        labels[2].set_label(data.before)
        labels[2].add_css_class("envlens-value")
        labels[3].set_label(data.after)
        labels[3].add_css_class("envlens-value")
        labels[0].set_tooltip_text(data.name)
        labels[2].set_tooltip_text(data.before)
        labels[3].set_tooltip_text(data.after)

    def refresh(self, *_):
        self.captures = load_all()
        self.left_index = 0
        self.right_index = self._second_context()
        self.update_captures()
        self.toast.add_toast(Adw.Toast.new(f"Loaded {len(self.captures)} captures"))

    def copy_command(self, *_):
        Gdk.Display.get_default().get_clipboard().set("env -0 | envlens capture --label 'Terminal'")
        self.toast.add_toast(Adw.Toast.new("Terminal capture command copied"))

    def copy_ide_command(self, *_):
        Gdk.Display.get_default().get_clipboard().set("env -0 | envlens capture --label 'IDE task'")
        self.toast.add_toast(Adw.Toast.new("IDE capture command copied"))

    def _second_context(self):
        return next(
            (i for i, item in enumerate(self.captures[1:], start=1)
             if item.get("label") != self.captures[0].get("label")),
            min(1, len(self.captures) - 1),
        ) if self.captures else 0

    def on_select(self, dropdown, _pspec):
        if dropdown is self.left_dropdown:
            self.left_index = dropdown.get_selected()
        else:
            self.right_index = dropdown.get_selected()
        self.update_rows()

    def on_search(self, entry):
        self.query = entry.get_text().casefold().strip()
        self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def on_hide_same(self, switch, _pspec):
        self.hide_same = switch.get_active()
        self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def matches(self, row):
        if self.hide_same and row.status.startswith("same"):
            return False
        return not self.query or self.query in row.name.casefold() or self.query in row.status

    def update_captures(self):
        labels = [f"{item['label']} · {dt.datetime.fromtimestamp(item['captured_at']).strftime('%b %d, %H:%M:%S')} · {item['id'][:4]}" for item in self.captures]
        for dropdown, index in ((self.left_dropdown, self.left_index), (self.right_dropdown, self.right_index)):
            model = Gtk.StringList.new(labels or ["Capture an environment first"])
            dropdown.set_model(model)
            dropdown.set_sensitive(len(labels) > 1)
            dropdown.set_selected(index if labels and index < len(labels) else 0)
        self.capture_count.set_label(f"{len(self.captures)} / 2")
        self.status.set_label("READY TO COMPARE" if len(self.captures) >= 2 else f"{len(self.captures)} CAPTURE" if self.captures else "AWAITING CAPTURES")
        self.delete_button.set_sensitive(bool(self.captures))
        self.update_rows()

    def update_rows(self):
        self.store.remove_all()
        if len(self.captures) < 2:
            self.summary.set_label("Capture two contexts to see what differs.")
            self.empty_hint.set_visible(True)
            self.filter.changed(Gtk.FilterChange.DIFFERENT)
            return
        self.empty_hint.set_visible(False)
        left = self.captures[min(self.left_index, len(self.captures)-1)]
        right = self.captures[min(self.right_index, len(self.captures)-1)]
        if left["id"] == right["id"]:
            alternate = (self.left_index + 1) % len(self.captures)
            right = self.captures[alternate]
            self.right_index = alternate
            self.right_dropdown.set_selected(alternate)
        rows = compare(left, right)
        rows.sort(key=lambda row: (row[1].startswith("same"), row[0].casefold()))
        self.store.splice(0, 0, [EnvRow(*row) for row in rows])
        changed = sum(not row[1].startswith("same") for row in rows)
        self.summary.set_label(f"{changed} differences · {len(rows)} variables · {left['label']} → {right['label']}")
        self.hero_subtitle.set_label(f"Comparing {left['label']} with {right['label']}. Find the difference that explains the failure.")
        self.filter.changed(Gtk.FilterChange.DIFFERENT)

    def delete_selected(self, *_):
        if not self.captures:
            return
        index = min(self.left_index, len(self.captures)-1)
        remove(self.captures[index])
        self.refresh()
        self.toast.add_toast(Adw.Toast.new("Capture deleted"))


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = None
        self.set_accels_for_action("win.copy-ide-command", ["<Primary><Shift>c"])

    def do_startup(self):
        Adw.Application.do_startup(self)

    def do_activate(self):
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        install_style()
        if self.window is None:
            self.window = MainWindow(self)
        self.window.present()


def run():
    return Application().run(None)
