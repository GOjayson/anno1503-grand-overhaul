"""Host and join Internet multiplayer trials through the verified launcher worker."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from ipaddress import IPv4Address
from queue import Empty, Queue
from threading import Thread

from .lan_identity import validate_display_name


@dataclass(frozen=True)
class LauncherAddon:
    label: str
    choose: Callable[[], tuple[str, str] | None] | None
    join_label: str


def run_launcher(start: Callable[..., None], *, defaults: Mapping[str, str] | None = None,
                 addon: LauncherAddon | None = None, private_link: bool = False) -> None:
    """Collect one request and give its values to the worker without touching the game."""
    import tkinter as tk
    from tkinter import ttk

    values = defaults or {}
    initial_role = "host" if values.get("role") == "host" else "guest"
    background, surface, text, muted = "#142024", "#203137", "#edf5f2", "#bad0c9"
    accent, focus, error = "#8de0c4", "#add4c8", "#ffb3a6"
    root = tk.Tk()
    root.title("Anno 1503 Grand Overhaul Multiplayer")
    root.minsize(440, 420)
    root.configure(background=background)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Internet.TFrame", background=background)
    style.configure("Internet.TLabel", background=background, foreground=text, font=("Segoe UI", 10))
    style.configure("Title.Internet.TLabel", font=("Segoe UI", 21, "bold"))
    style.configure("Note.Internet.TLabel", foreground=muted)
    style.configure("Internet.TEntry", fieldbackground=surface, foreground=text, insertcolor=text,
                    bordercolor="#425c61", lightcolor=surface, darkcolor=surface, padding=8)
    style.map("Internet.TEntry", bordercolor=[("focus", focus)], foreground=[("disabled", muted)])
    style.configure("Internet.TRadiobutton", background=background, foreground=text,
                    font=("Segoe UI", 11), padding=(8, 5))
    style.map("Internet.TRadiobutton", background=[("active", surface)],
              foreground=[("disabled", muted), ("selected", accent)])
    style.configure("Internet.TCheckbutton", background=background, foreground=text)
    style.map("Internet.TCheckbutton", background=[("active", surface)],
              foreground=[("disabled", muted), ("selected", accent)])
    style.configure("Internet.TButton", background=accent, foreground=background,
                    font=("Segoe UI", 11, "bold"), padding=(16, 7), bordercolor=accent)
    style.map("Internet.TButton", background=[("disabled", surface), ("active", "#b0eedb")],
              foreground=[("disabled", muted)])
    style.configure("Internet.Horizontal.TProgressbar", background=accent, troughcolor=surface,
                    lightcolor=accent, darkcolor=accent, bordercolor=surface)

    role = tk.StringVar(root, initial_role)
    display_name = tk.StringVar(root, values.get("display_name") or "")
    address = {mode: tk.StringVar(root, (values.get("host_address") or "") if mode == initial_role else "")
               for mode in ("host", "guest")}
    bind = {mode: tk.StringVar(root, (values.get("bind_address") or "") if mode == initial_role else "")
            for mode in ("host", "guest")}
    status = tk.StringVar(root)
    join_addon = tk.BooleanVar(root)
    addon_offer = None
    events: Queue[tuple[str, str]] = Queue()
    busy = False

    panel = ttk.Frame(root, padding=24, style="Internet.TFrame")
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="LAN multiplayer" if private_link else "Internet multiplayer",
              style="Title.Internet.TLabel").pack(anchor="w")
    modes = ttk.Frame(panel, style="Internet.TFrame")
    modes.pack(fill="x", pady=(9, 14))
    role_buttons = [ttk.Radiobutton(modes, text=label, value=value, variable=role, style="Internet.TRadiobutton")
                    for label, value in (("Host", "host"), ("Join", "guest"))]
    for button in role_buttons:
        button.pack(side="left", padx=(0, 10))

    def field(label, variable):
        caption = ttk.Label(panel, text=label, style="Internet.TLabel")
        caption.pack(anchor="w", pady=(0, 4))
        entry = ttk.Entry(panel, textvariable=variable, style="Internet.TEntry", font=("Segoe UI", 11))
        entry.pack(fill="x", pady=(0, 10))
        return caption, entry

    _, player_entry = field("Player display name", display_name)
    address_label, address_entry = field("", address[initial_role])
    bind_label, bind_entry = field("", bind[initial_role])
    addon_row = ttk.Frame(panel, style="Internet.TFrame")
    if addon is not None:
        addon_row.pack(fill="x", pady=(0, 10))
    address_actions = ttk.Frame(panel, style="Internet.TFrame")
    address_actions.pack(fill="x")
    port_note = ttk.Label(panel, style="Note.Internet.TLabel")
    port_note.pack(fill="x")

    status_label = ttk.Label(panel, textvariable=status, style="Note.Internet.TLabel", justify="left")
    status_label.pack(side="bottom", fill="x", pady=(8, 0))
    bar = ttk.Progressbar(panel, mode="indeterminate", style="Internet.Horizontal.TProgressbar")
    bar.pack(side="bottom", fill="x", pady=(8, 0))

    def set_status(message, *, failed=False):
        status.set(message)
        status_label.configure(foreground=error if failed else muted)

    def set_busy(running):
        nonlocal busy
        busy = running
        for widget in (*role_buttons, player_entry, address_entry, bind_entry, action, copy_address,
                       addon_button, clear_addon, join_option):
            widget.state(["disabled" if running else "!disabled"])
        if running:
            bar.start(18)
        else:
            bar.stop()

    def select_mode():
        selected = role.get()
        hosting = selected == "host"
        address_label.configure(text="Host IPv4 address" if private_link else
                                "Public IPv4 address" if hosting else "Host’s public IPv4 address")
        address_entry.configure(textvariable=address[selected])
        bind_label.configure(text="Local IPv4 address (optional)")
        bind_entry.configure(textvariable=bind[selected])
        port_note.configure(text="Forward TCP 51503 and UDP 61503 to the local IPv4 address."
                            if hosting and not private_link else "")
        refresh_addon_controls()
        if hosting:
            copy_address.pack(side="left", pady=(0, 6))
        else:
            copy_address.pack_forget()
        action.configure(text="Host game" if hosting else "Join game")
        set_status("")

    def submit():
        if busy:
            return
        selected = role.get()
        try:
            name = validate_display_name(display_name.get())
        except ValueError as exc:
            set_status(str(exc), failed=True)
            player_entry.focus_set()
            return
        host_address = address[selected].get().strip()
        if not host_address:
            set_status("Enter the host IPv4 address." if private_link else
                       "Enter your public IPv4 address." if selected == "host" else "Enter the host’s public IPv4 address.",
                       failed=True)
            address_entry.focus_set()
            return
        bind_address = bind[selected].get().strip()
        offered = (addon_offer if selected == "host" else "join" if join_addon.get() else None)
        set_busy(True)
        set_status("Checking the multiplayer setup…")

        def worker():
            try:
                request = dict(role=selected, display_name=name, host_address=host_address,
                               bind_address=bind_address,
                               progress=lambda message: events.put(("progress", str(message))))
                if offered is not None:
                    request["addon"] = offered
                start(**request)
            except (Exception, SystemExit) as exc:
                events.put(("error", str(exc) or "The multiplayer request could not finish."))
            else:
                events.put(("done", "Continue in Anno 1503."))

        try:
            Thread(target=worker, daemon=False).start()
        except RuntimeError as exc:
            set_busy(False)
            set_status(str(exc), failed=True)

    def share_ipv4():
        try:
            public = str(IPv4Address(address["host"].get().strip()))
        except ValueError:
            set_status("Enter the public IPv4 address to share.", failed=True)
            address_entry.focus_set()
            return
        root.clipboard_clear()
        root.clipboard_append(public)
        set_status("Host IPv4 address copied." if private_link else "Public IPv4 address copied.")

    def refresh_addon_controls():
        for widget in (addon_button, clear_addon, join_option):
            widget.pack_forget()
        if addon is None:
            return
        if role.get() == "host":
            if addon.choose is None:
                return
            addon_button.configure(text=addon.label + "…")
            addon_button.pack(side="left")
            if addon_offer:
                clear_addon.pack(side="left", padx=(7, 0))
        else:
            join_option.pack(side="left")

    def configure_addon():
        nonlocal addon_offer
        if addon is None or addon.choose is None:
            return
        root.withdraw()
        try:
            selected = addon.choose()
            if selected:
                addon_offer, summary = selected
                refresh_addon_controls()
                set_status(summary)
        except (OSError, ValueError, RuntimeError) as exc:
            set_status(str(exc), failed=True)
        finally:
            root.deiconify()

    def remove_addon():
        nonlocal addon_offer
        addon_offer = None
        refresh_addon_controls()
        set_status("")

    copy_address = ttk.Button(address_actions, text="Copy IPv4", command=share_ipv4,
                              style="Internet.TButton")
    addon_button = ttk.Button(addon_row, command=configure_addon, style="Internet.TButton")
    clear_addon = ttk.Button(addon_row, text="Use base game maps", command=remove_addon, style="Internet.TButton")
    join_option = ttk.Checkbutton(addon_row, text=addon.join_label if addon else "", variable=join_addon,
                                  style="Internet.TCheckbutton")
    action = ttk.Button(panel, command=submit, style="Internet.TButton")
    action.pack(side="bottom", anchor="e")
    for button in role_buttons:
        button.configure(command=select_mode)

    def poll():
        try:
            while True:
                kind, message = events.get_nowait()
                if kind != "progress":
                    set_busy(False)
                set_status(message, failed=kind == "error")
        except Empty:
            pass
        root.after(75, poll)

    def close():
        if busy:
            set_status("The multiplayer request is still running.")
        else:
            root.destroy()

    def resize(event):
        if event.widget is root:
            for label in (status_label, port_note):
                label.configure(wraplength=max(1, event.width - 48))

    select_mode()
    root.bind("<Configure>", resize)
    def submit_from_keyboard(_):
        submit()
        return "break"

    root.bind("<Return>", submit_from_keyboard)
    root.protocol("WM_DELETE_WINDOW", close)
    root.after(75, poll)
    player_entry.focus_set()
    root.mainloop()
