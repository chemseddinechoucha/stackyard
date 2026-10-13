"""Stackyard GUI (Tkinter)."""
from __future__ import annotations

import queue
import re
import threading
import time
import tkinter as tk
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import core
import installer
import theme

ASSETS = core.APP_DIR / "assets"

STATE_COLORS = {"running": theme.PALETTE["success"], "starting": theme.PALETTE["warning"],
                "external": theme.PALETTE["info"], "stopped": theme.PALETTE["stopped"]}
STATE_TEXT = {"running": "Running", "starting": "Starting...", "external": "Running (external)", "stopped": "Stopped"}


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _bind_card_hover(card, outer, normal_color, hover_color):
    """Highlight a card's border while the pointer is anywhere over it."""
    def update(_e=None):
        try:
            px, py = card.winfo_pointerxy()
            w = card.winfo_containing(px, py)
        except tk.TclError:
            w = None
        inside = w is not None and (w is card or str(w).startswith(str(card) + "."))
        outer.configure(background=hover_color if inside else normal_color)
    for w in _walk(card):
        w.bind("<Enter>", update, add="+")
        w.bind("<Leave>", update, add="+")


APPS = [
    ("phpmyadmin", "phpMyAdmin", "Web interface for MySQL (installed in www\\phpmyadmin)"),
    ("composer", "Composer", "PHP dependency manager (uses the active PHP version)"),
    ("nodejs", "Node.js", "JavaScript runtime - install several versions and switch between them"),
]


# ============================================================================ dialogs
class FormDialog(simpledialog.Dialog):
    """Generic modal form. fields = [(key, label, default, browse)] where browse is None or 'dir'."""

    def __init__(self, parent, title, fields, validator=None):
        self._fields = fields
        self._validator = validator
        self._vars: dict[str, tk.StringVar] = {}
        self._vals: dict[str, str] = {}
        super().__init__(parent, title)

    def body(self, master):
        first = None
        for i, (key, label, default, browse) in enumerate(self._fields):
            ttk.Label(master, text=label).grid(row=i, column=0, sticky="w", padx=6, pady=4)
            var = tk.StringVar(value=default)
            self._vars[key] = var
            e = ttk.Entry(master, textvariable=var, width=50)
            e.grid(row=i, column=1, padx=6, pady=4)
            if browse == "dir":
                ttk.Button(master, text="...", width=3, command=lambda v=var: self._browse(v)).grid(row=i, column=2)
            first = first or e
        return first

    def _browse(self, var):
        d = filedialog.askdirectory(parent=self, initialdir=var.get() or str(core.BASE_DIR))
        if d:
            var.set(d.replace("/", "\\") if core.IS_WIN else d)

    def validate(self):
        vals = {k: v.get().strip() for k, v in self._vars.items()}
        if self._validator:
            err = self._validator(vals)
            if err:
                messagebox.showerror("Invalid input", err, parent=self)
                return False
        self._vals = vals
        return True

    def apply(self):
        self.result = self._vals


class PickDialog(simpledialog.Dialog):
    def __init__(self, parent, title, prompt, choices):
        self._prompt, self._choices = prompt, choices
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text=self._prompt).pack(anchor="w", padx=8, pady=(8, 4))
        self._cb = ttk.Combobox(master, values=self._choices, state="readonly", width=40)
        self._cb.current(0)
        self._cb.pack(padx=8, pady=(0, 8))
        return self._cb

    def apply(self):
        self.result = self._cb.get()


class ExtDialog(tk.Toplevel):
    """Toggle PHP extensions in php.ini (double-click or press space)."""

    def __init__(self, app: "App", php_dir: Path):
        super().__init__(app)
        self.app, self.php_dir = app, php_dir
        self.title(f"PHP extensions - {php_dir.name}")
        self.geometry("360x520")
        self.transient(app)
        self.states = dict(core.list_php_extensions(php_dir))
        self.original = dict(self.states)
        ttk.Label(self, text="Double-click an extension to toggle it.").pack(anchor="w", padx=10, pady=(10, 4))
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10)
        self.tree = ttk.Treeview(frame, columns=("state",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Extension")
        self.tree.heading("state", text="Enabled")
        self.tree.column("#0", width=220)
        self.tree.column("state", width=70, anchor="center")
        sb = ttk.Scrollbar(frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for name in sorted(self.states):
            self.tree.insert("", "end", iid=name, text=name, values=("yes" if self.states[name] else "",))
        self.tree.bind("<Double-1>", self._toggle)
        self.tree.bind("<space>", self._toggle)
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=10)
        ttk.Button(bar, text="Save", command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right", padx=6)

    def _toggle(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        name = sel[0]
        self.states[name] = not self.states[name]
        self.tree.item(name, values=("yes" if self.states[name] else "",))

    def _save(self):
        changes = {k: v for k, v in self.states.items() if v != self.original.get(k)}
        if changes:
            try:
                core.set_php_extensions(self.php_dir, changes)
            except OSError as e:
                messagebox.showerror("Stackyard", str(e), parent=self)
                return
            self.app.log("PHP extensions changed: " + ", ".join(f"{k}={'on' if v else 'off'}" for k, v in changes.items()))
            self.app.after_config_change("PHP")
        self.destroy()


# ============================================================================ application
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Stackyard - local development environment")
        try:                                    # match Tk's points-per-pixel to the real display DPI
            self.tk.call("tk", "scaling", self.winfo_fpixels("1i") / 72.0)
        except tk.TclError:
            pass
        self.theme = theme.apply(self)
        self.configure(background=self.theme["palette"]["window"])
        self.geometry("1140x820")
        self.minsize(980, 680)
        self._set_icon()
        self.cfg = core.Config()
        self.q: queue.Queue = queue.Queue()
        self.busy: set[str] = set()
        self._polling = False
        self.rows: dict[str, dict] = {}
        self.last_state: dict[str, str] = {}
        self.services = core.build_services(self.cfg, self.log)
        self.cfg_files: list = []
        self.cfg_index: int | None = None
        self._crlf = False

        self._header()
        self._build_log()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.tab_services = ttk.Frame(self.nb, style="Tab.TFrame")
        self.tab_versions = ttk.Frame(self.nb, style="Tab.TFrame")
        self.tab_config = ttk.Frame(self.nb, style="Tab.TFrame")
        self.tab_vhosts = ttk.Frame(self.nb, style="Tab.TFrame")
        self.tab_apps = ttk.Frame(self.nb, style="Tab.TFrame")
        for t, name in ((self.tab_services, "Services"), (self.tab_versions, "Versions"),
                        (self.tab_config, "Configuration"), (self.tab_vhosts, "Virtual hosts"),
                        (self.tab_apps, "Apps")):
            self.nb.add(t, text=f"  {name}  ")
        self._build_services_tab()
        self._build_versions_tab()
        self._build_config_tab()
        self._build_vhosts_tab()
        self._build_apps_tab()
        self.nb.bind("<<NotebookTabChanged>>", self._tab_changed)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(80, self._drain)
        self.bg(lambda: core.startup(self.cfg), done=self._after_startup)
        self.after(400, self.poll_status)

    # ------------------------------------------------------------------ infrastructure
    def ui(self, fn):
        self.q.put(fn)

    def _drain(self):
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        self.after(80, self._drain)

    def log(self, msg: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.q.put(lambda: self._append_log(f"[{stamp}] {msg}\n"))

    def _append_log(self, text: str):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", text)
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def bg(self, fn, done=None, busy_key: str | None = None):
        if busy_key:
            if busy_key in self.busy:
                return
            self.busy.add(busy_key)

        def run():
            try:
                res = fn()
            except Exception as e:  # noqa: BLE001 - surface everything to the user
                msg = str(e) or e.__class__.__name__
                self.log("ERROR: " + msg.splitlines()[0])
                self.ui(lambda: messagebox.showerror("Stackyard", msg, parent=self))
                res, failed = None, True
            else:
                failed = False
            finally:
                if busy_key:
                    self.ui(lambda: self.busy.discard(busy_key))
            if done and not failed:
                self.ui(lambda: done(res))
            elif failed:
                self.ui(self.poll_now)

        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------ chrome
    def _button(self, parent, text, command, style="TButton", **kw):
        """A themed button with a hand cursor (all action buttons look clickable)."""
        return ttk.Button(parent, text=text, command=command, style=style, cursor="hand2", **kw)

    @staticmethod
    def _bind_hover(widget, on_enter, on_leave):
        widget.bind("<Enter>", lambda _e: on_enter(), add="+")
        widget.bind("<Leave>", lambda _e: on_leave(), add="+")

    def _set_icon(self):
        """Window + taskbar icon. Missing or unreadable assets are ignored (the app works without them)."""
        ico, png = ASSETS / "stackyard.ico", ASSETS / "stackyard-icon-256.png"
        try:
            if core.IS_WIN and ico.is_file():
                self.iconbitmap(default=str(ico))      # also used by every dialog
            elif png.is_file():
                self._icon_img = tk.PhotoImage(file=str(png))
                self.iconphoto(True, self._icon_img)
        except tk.TclError:
            pass

    def _header(self):
        p = self.theme["palette"]
        h = ttk.Frame(self, style="Header.TFrame", padding=(18, 12))
        h.pack(fill="x")
        tk.Frame(self, height=1, background=p["border"]).pack(fill="x")

        left = ttk.Frame(h, style="Header.TFrame")
        left.pack(side="left", fill="x", expand=True)
        top = ttk.Frame(left, style="Header.TFrame")
        top.pack(anchor="w")
        try:
            self._mark_img = tk.PhotoImage(file=str(ASSETS / "stackyard-mark-32.png"))
            ttk.Label(top, image=self._mark_img, style="Card.TLabel").pack(side="left", padx=(0, 10))
        except tk.TclError:
            pass
        ttk.Label(top, text="Stackyard", style="HeaderTitle.TLabel").pack(side="left")
        self.root_lbl = ttk.Label(left, text=f"Root folder:  {core.BASE_DIR}", style="HeaderSub.TLabel")
        self.root_lbl.pack(anchor="w", pady=(2, 0))

        right = ttk.Frame(h, style="Header.TFrame")
        right.pack(side="right")
        self._button(right, "Change root folder...", self.change_root).pack(side="right", padx=(8, 0))
        if core.IS_WIN:
            if core.is_admin():
                ttk.Label(right, text="Administrator", style="Admin.TLabel").pack(side="right")
            else:
                self._button(right, "Restart as administrator", self.restart_admin).pack(side="right")

    def restart_admin(self):
        if messagebox.askyesno("Stackyard", "Restart Stackyard with administrator rights?\n"
                               "(needed to edit the Windows hosts file and use ports below 1024 on some systems)"):
            core.relaunch_as_admin()
            self.destroy()

    def _build_log(self):
        p = self.theme["palette"]
        card = theme.make_card(self, padding=(14, 10))
        card._card_outer.pack(side="bottom", fill="x", padx=12, pady=(0, 12))
        head = ttk.Frame(card, style="Card.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="Log", style="CardTitle.TLabel").pack(side="left")
        self._button(head, "Clear", self._clear_log, width=7).pack(side="right")
        holder = ttk.Frame(card, style="Card.TFrame")
        holder.pack(fill="x", pady=(8, 0))
        self.logbox = tk.Text(holder, height=8, state="disabled", wrap="word",
                              font=self.theme["mono_font"], background=p["surface_alt"],
                              foreground=p["text"], relief="flat", padx=10, pady=8,
                              highlightthickness=1, highlightbackground=p["border"],
                              highlightcolor=p["border"])
        sb = ttk.Scrollbar(holder, command=self.logbox.yview)
        self.logbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.logbox.pack(side="left", fill="both", expand=True)

    def _clear_log(self):
        self.logbox.configure(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.configure(state="disabled")

    def _after_startup(self, notes):
        for n in notes:
            self.log(n)
        if core.BASE_WARNING:
            self.log("WARNING: " + core.BASE_WARNING)
        self.log(f"Ready. Base folder: {core.BASE_DIR}")
        self.refresh_versions()
        self.after(300, self._first_run_check)

    def _first_run_check(self):
        if core.BASE_WARNING:
            messagebox.showwarning("Stackyard", core.BASE_WARNING + "\n\nUse 'Change root folder...' to pick another one.")
        elif not any(core.list_versions(t) for t in core.TOOLS) and not core.saved_base_dir():
            if messagebox.askyesno(
                    "Stackyard", f"No Apache, PHP, MySQL or Node.js folders were found in:\n{core.BASE_DIR}\n\n"
                    "Choose the root folder that contains them now?"):
                self.change_root()

    def change_root(self):
        if any(s in ("running", "starting") for s in self.last_state.values()):
            messagebox.showwarning("Stackyard", "Stop all services before changing the root folder.")
            return
        d = filedialog.askdirectory(
            parent=self, mustexist=True, initialdir=str(core.BASE_DIR),
            title="Choose the root folder (the one containing httpd-*, php-*, mysql-*, www ...)")
        if not d:
            return
        new = Path(d)
        try:
            if new.resolve() == core.BASE_DIR.resolve():
                return
        except OSError:
            pass
        if not messagebox.askyesno(
                "Stackyard", f"Use this as the root folder?\n\n{new}\n\n"
                "Stackyard will look for httpd-*, php-*, mysql-*, nodejs-* and www in it. "
                "Virtual hosts pointing into the old www folder are moved to the new one. "
                "Nothing is copied or deleted."):
            return
        make_www = False
        if not (new / "www").is_dir():
            make_www = messagebox.askyesno("Stackyard", f"There is no 'www' folder in {new}.\nCreate it (your document root)?")

        def work():
            old_www = core.WWW_DIR
            core.set_base_dir(new)
            if make_www:
                core.WWW_DIR.mkdir(parents=True, exist_ok=True)
            moved = core.remap_vhosts(self.cfg, old_www, core.WWW_DIR)
            return moved, core.startup(self.cfg)
        self.bg(work, done=self._root_changed)

    def _root_changed(self, res):
        moved, notes = res
        for n in notes:
            self.log(n)
        self.root_lbl.configure(text=f"Root folder:  {core.BASE_DIR}")
        self.log(f"Root folder is now {core.BASE_DIR}" + (f" ({moved} virtual host path(s) moved)" if moved else ""))
        self.refresh_versions()
        self.refresh_apps()
        self.refresh_vhosts()
        self.cfg_index = None
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.edit_modified(False)
        self.cfg_title.configure(text="Select a file on the left.")
        self.refresh_config_list()
        self.vh_status.configure(text="Root folder changed - press 'Apply' to regenerate the Apache config and hosts file.")
        found = [core.TOOLS[t]["label"] for t in core.TOOLS if core.list_versions(t)]
        msg = f"Root folder set to {core.BASE_DIR}.\n\nFound: " + (", ".join(found) if found else "nothing yet")
        if not found:
            msg += ("\n\nPut your tool folders (httpd-<version>, php-<version>, mysql-<version>) and www in it, "
                    "then press Rescan on the Versions tab.")
        msg += "\n\nIf you added Stackyard to your PATH before, press 'Add Stackyard tools to my PATH' again (the old entries stay but become unused)."
        messagebox.showinfo("Stackyard", msg)
        self.poll_now()

    def _tab_changed(self, _e=None):
        tab = self.nb.nametowidget(self.nb.select())
        if tab is self.tab_config and not self.cfg_files:
            self.refresh_config_list()
        elif tab is self.tab_apps:
            self.refresh_apps()
        elif tab is self.tab_versions:
            self.refresh_versions()

    # ------------------------------------------------------------------ SERVICES tab
    def _build_services_tab(self):
        f = self.tab_services
        for w in f.winfo_children():
            w.destroy()
        p = self.theme["palette"]
        top = ttk.Frame(f, style="Tab.TFrame")
        top.pack(fill="x", padx=14, pady=(14, 8))
        self._button(top, "Start all", self.start_all, style="Accent.TButton").pack(side="left")
        self._button(top, "Stop all", self.stop_all).pack(side="left", padx=8)
        self._button(top, "+ Custom service", self.add_custom_service).pack(side="left", padx=(20, 0))
        self._button(top, "Open terminal", self.open_terminal).pack(side="right")
        self._button(top, "www folder", lambda: core.open_path(core.WWW_DIR)).pack(side="right", padx=8)
        self._button(top, "localhost", lambda: webbrowser.open("http://localhost/")).pack(side="right")

        self.svc_box = ttk.Frame(f, style="Tab.TFrame")
        self.svc_box.pack(fill="x", padx=14, pady=6)
        self.rows = {}
        for key, svc in self.services.items():
            card = theme.make_card(self.svc_box, padding=(16, 14))
            outer = card._card_outer
            outer.pack(fill="x", pady=6)
            dot = tk.Canvas(card, width=22, height=22, highlightthickness=0, background=p["surface"])
            dot.pack(side="left", padx=(0, 14))
            oval = dot.create_oval(3, 3, 19, 19, fill=STATE_COLORS["stopped"], outline="")
            info = ttk.Frame(card, style="Card.TFrame")
            info.pack(side="left", fill="x", expand=True)
            ttk.Label(info, text=svc.label, style="Svc.TLabel").pack(anchor="w")
            detail = ttk.Label(info, text="", style="RowMuted.TLabel")
            detail.pack(anchor="w")
            state = ttk.Label(card, text="Stopped", style="Card.TLabel", width=18)
            state.pack(side="left", padx=12)
            b_start = self._button(card, "Start", lambda k=key: self.svc_action(k, "start"), style="Accent.TButton", width=9)
            b_stop = self._button(card, "Stop", lambda k=key: self.svc_action(k, "stop"), width=9)
            b_rest = self._button(card, "Restart", lambda k=key: self.svc_action(k, "restart"), width=9)
            for b in (b_start, b_stop, b_rest):
                b.pack(side="left", padx=4)
            if key.startswith("custom-"):
                self._button(card, "Remove", lambda k=key: self.remove_custom_service(k),
                             style="Danger.TButton").pack(side="left", padx=(12, 0))
            self.rows[key] = dict(dot=dot, oval=oval, detail=detail, state=state, start=b_start, stop=b_stop, restart=b_rest)
            _bind_card_hover(card, outer, p["border"], p["accent"])

        opts = ttk.Frame(f, style="Tab.TFrame")
        opts.pack(fill="x", padx=14, pady=12)
        self.var_stop_exit = tk.BooleanVar(value=bool(self.cfg.data.get("stop_on_exit")))
        ttk.Checkbutton(opts, text="Stop services automatically when Stackyard closes", variable=self.var_stop_exit,
                        command=self._save_stop_exit).pack(anchor="w")
        ttk.Label(f, text=("Services started here keep running if you close Stackyard (unless the option above is on). "
                           "Stackyard re-detects them the next time it opens."), style="Dim.TLabel",
                  wraplength=980, justify="left").pack(anchor="w", padx=14, pady=(0, 6))

    def _save_stop_exit(self):
        self.cfg.data["stop_on_exit"] = bool(self.var_stop_exit.get())
        self.cfg.save()

    def poll_now(self):
        if not self._polling:
            self.poll_status()

    def poll_status(self):
        if self._polling:
            return
        self._polling = True

        def work():
            res = {}
            for k, s in list(self.services.items()):
                try:
                    res[k] = (s.status(), s.describe())
                except Exception as e:  # noqa: BLE001
                    res[k] = ("stopped", f"error: {e}")
            self.ui(lambda: self._apply_status(res))

        threading.Thread(target=work, daemon=True).start()

    def _apply_status(self, res):
        self._polling = False
        for k, (state, detail) in res.items():
            self.last_state[k] = state
            r = self.rows.get(k)
            if not r:
                continue
            r["dot"].itemconfigure(r["oval"], fill=STATE_COLORS[state])
            r["state"].configure(text=STATE_TEXT[state])
            r["detail"].configure(text=detail)
            busy = k in self.busy
            stopped = state == "stopped"
            r["start"].state(["!disabled"] if (stopped and not busy) else ["disabled"])
            r["stop"].state(["!disabled"] if (not stopped and not busy) else ["disabled"])
            r["restart"].state(["!disabled"] if not busy else ["disabled"])
        self.after(2500, self.poll_status)

    def svc_action(self, key: str, action: str):
        svc = self.services[key]
        self.bg(lambda: getattr(svc, action)(), done=lambda _: self.poll_now(), busy_key=key)
        self.after(150, self.poll_now)

    def start_all(self):
        def work():
            for key in ("mysql", "httpd", *[k for k in self.services if k.startswith("custom-")]):
                if key in self.services:
                    self.services[key].start()
        self.bg(work, done=lambda _: self.poll_now())

    def stop_all(self):
        def work():
            for key in reversed(list(self.services)):
                self.services[key].stop()
        self.bg(work, done=lambda _: self.poll_now())

    def open_terminal(self):
        try:
            core.open_terminal()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Stackyard", str(e))

    def add_custom_service(self):
        def check(v):
            if not v["label"]:
                return "Give the service a name."
            if not v["command"]:
                return "Enter the command to run."
            if v["port"] and not v["port"].isdigit():
                return "Port must be a number (or empty)."
            return None
        d = FormDialog(self, "Add custom service", [
            ("label", "Name", "", None),
            ("command", "Command", "npm run dev", None),
            ("cwd", "Working folder", str(core.WWW_DIR), "dir"),
            ("port", "Port to watch (optional)", "", None),
        ], check)
        if not d.result:
            return
        v = d.result
        entry = {"id": "custom-" + uuid.uuid4().hex[:8], "label": v["label"], "command": v["command"],
                 "cwd": v["cwd"], "port": int(v["port"]) if v["port"] else None}
        self.cfg.data["services"].append(entry)
        self.cfg.save()
        self.services = core.build_services(self.cfg, self.log)
        self._build_services_tab()
        self.poll_now()

    def remove_custom_service(self, key: str):
        if not messagebox.askyesno("Stackyard", "Remove this custom service?\n(A running process is not stopped.)"):
            return
        self.cfg.data["services"] = [e for e in self.cfg.data["services"] if e["id"] != key]
        self.cfg.save()
        self.services = core.build_services(self.cfg, self.log)
        self._build_services_tab()

    # ------------------------------------------------------------------ VERSIONS tab
    def _build_versions_tab(self):
        f = self.tab_versions
        self.ver = {}
        ttk.Label(f, text=("Drop a new version next to the others (e.g. php-8.4.1) and press Rescan. "
                           "Activating a version re-points the 'current' junction for that tool and regenerates the Apache config."),
                  style="Dim.TLabel", wraplength=980, justify="left").pack(anchor="w", padx=14, pady=(14, 2))
        bar = ttk.Frame(f, style="Tab.TFrame")  # at the TOP so it is never cut off on small windows
        bar.pack(fill="x", padx=14, pady=(6, 4))
        self._button(bar, "Rescan", self.refresh_versions).pack(side="left")
        self._button(bar, "Open base folder", lambda: core.open_path(core.BASE_DIR)).pack(side="left", padx=8)
        self._button(bar, "Add Stackyard tools to my PATH", self.add_path).pack(side="left", padx=8)
        for tool, meta in core.TOOLS.items():
            card = theme.make_card(f, padding=(16, 14))
            card._card_outer.pack(fill="x", padx=14, pady=6)
            ttk.Label(card, text=meta["label"], style="CardTitle.TLabel").pack(anchor="w")
            top = ttk.Frame(card, style="Card.TFrame")
            top.pack(fill="x", pady=(10, 2))
            cb = ttk.Combobox(top, state="readonly", width=34)
            cb.pack(side="left")
            cb.bind("<<ComboboxSelected>>", lambda _e, t=tool: self._ver_note(t))
            self._button(top, "Activate", lambda t=tool: self.activate(t), style="Accent.TButton").pack(side="left", padx=10)
            active = ttk.Label(top, text="", style="Card.TLabel")
            active.pack(side="left", padx=10)
            note = ttk.Label(card, text="", style="RowMuted.TLabel", wraplength=940, justify="left")
            note.pack(anchor="w", pady=(6, 0))
            self.ver[tool] = dict(cb=cb, active=active, note=note)
        self.refresh_versions()

    def refresh_versions(self):
        for tool, w in self.ver.items():
            vs = core.list_versions(tool)
            names = [v.name for v in vs]
            w["cb"]["values"] = names
            act = self.cfg.active_dir(tool)
            w["cb"].set(act.name if act else "")
            w["active"].configure(text=f"Active: {act.name}" if act else "None found")
            self._ver_note(tool)

    def _ver_note(self, tool):
        w = self.ver[tool]
        name = w["cb"].get()
        txt = core.version_note(tool, core.locate(name) or core.BASE_DIR / name) if name else (
            f"No folder named {'/'.join(core.TOOLS[tool]['prefixes'])}<version> found in {core.tools_dir()}.")
        w["note"].configure(text=txt)

    def activate(self, tool: str):
        name = self.ver[tool]["cb"].get()
        if not name:
            return
        if tool == "mysql" and self.last_state.get("mysql") != "stopped":
            messagebox.showwarning("Stackyard", "Stop MySQL before switching its version.")
            return
        if tool == "httpd" and self.last_state.get("httpd") != "stopped":
            if not messagebox.askyesno("Stackyard", "Apache is running. Stop it and switch version?"):
                return
            self.bg(lambda: self.services["httpd"].stop(), done=lambda _: self._do_activate(tool, name))
            return
        self._do_activate(tool, name)

    def _do_activate(self, tool, name):
        restart = tool == "php" and self.last_state.get("httpd") in ("running", "starting")

        def done(notes):
            for n in notes:
                self.log(n)
            self.refresh_versions()
            self.refresh_config_list(keep=True)
            if restart and messagebox.askyesno("Stackyard", "Restart Apache now to use the new PHP?"):
                self.svc_action("httpd", "restart")
            self.poll_now()
        self.bg(lambda: core.activate(self.cfg, tool, name), done=done)

    def add_path(self):
        entries = [p for p in core.path_entries()]
        msg = "Add these folders to your user PATH?\n\n" + "\n".join(str(p) for p in entries) + \
              "\n\nThey point to the ACTIVE version, so you only do this once."
        if not messagebox.askyesno("Stackyard", msg):
            return

        def done(added):
            if added:
                self.log("Added to PATH: " + "; ".join(added))
                messagebox.showinfo("Stackyard", "Done. Open a NEW terminal for it to take effect.")
            else:
                messagebox.showinfo("Stackyard", "Already in your PATH.")
        self.bg(lambda: core.add_to_user_path(entries), done=done)

    # ------------------------------------------------------------------ CONFIG tab
    def _build_config_tab(self):
        f = self.tab_config
        p = self.theme["palette"]
        left = ttk.Frame(f, style="Tab.TFrame")
        left.pack(side="left", fill="y", padx=(14, 6), pady=14)
        ttk.Label(left, text="Files", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))
        list_holder = tk.Frame(left, background=p["border"])
        list_holder.pack(fill="y", expand=True)
        self.cfg_list = tk.Listbox(list_holder, width=34, exportselection=False, activestyle="none", height=12,
                                   relief="flat", borderwidth=0, highlightthickness=0,
                                   font=self.theme["font"], selectmode="browse")
        self.cfg_list.configure(selectbackground=p["accent"], selectforeground=p["on_accent"],
                                background=p["surface"], foreground=p["text"])
        self.cfg_list.pack(padx=1, pady=1, fill="both", expand=True)
        self.cfg_list.bind("<<ListboxSelect>>", self._cfg_select)
        right = ttk.Frame(f, style="Tab.TFrame")
        right.pack(side="left", fill="both", expand=True, padx=(6, 14), pady=14)
        bar = ttk.Frame(right, style="Tab.TFrame")
        bar.pack(fill="x", pady=(0, 8))
        self._button(bar, "Save", self.cfg_save, style="Accent.TButton").pack(side="left")
        self._button(bar, "Reload", lambda: self._cfg_open(self.cfg_index)).pack(side="left", padx=6)
        self._button(bar, "Open in Notepad", self.cfg_external).pack(side="left")
        self._button(bar, "PHP extensions...", self.php_extensions).pack(side="left", padx=(16, 0))
        self._button(bar, "Test Apache config", self.test_apache).pack(side="left", padx=6)
        self._button(bar, "Restart Apache", lambda: self.svc_action("httpd", "restart")).pack(side="left")
        self.cfg_title = ttk.Label(right, text="Select a file on the left.", style="Dim.TLabel")
        self.cfg_title.pack(anchor="w", pady=(0, 6))
        holder = tk.Frame(right, background=p["border"])
        holder.pack(fill="both", expand=True)
        self.editor = tk.Text(holder, wrap="none", undo=True, font=self.theme["mono_font"],
                              relief="flat", borderwidth=0, highlightthickness=0, padx=8, pady=6,
                              background=p["surface"], foreground=p["text"], insertbackground=p["text"])
        ys = ttk.Scrollbar(holder, command=self.editor.yview)
        xs = ttk.Scrollbar(holder, orient="horizontal", command=self.editor.xview)
        self.editor.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.editor.pack(side="left", fill="both", expand=True, padx=1, pady=1)

    def refresh_config_list(self, keep: bool = False):
        self.cfg_files = core.config_files(self.cfg)
        self.cfg_list.delete(0, "end")
        for label, _p, _ro in self.cfg_files:
            self.cfg_list.insert("end", label)
        if keep and self.cfg_index is not None and self.cfg_index < len(self.cfg_files):
            self.cfg_list.selection_set(self.cfg_index)

    def _cfg_select(self, _e=None):
        sel = self.cfg_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == self.cfg_index:
            return
        if self.cfg_index is not None and self.editor.edit_modified():
            ans = messagebox.askyesnocancel("Stackyard", "Save changes to the current file first?")
            if ans is None:
                self.cfg_list.selection_clear(0, "end")
                self.cfg_list.selection_set(self.cfg_index)
                return
            if ans:
                self.cfg_save()
        self._cfg_open(idx)

    def _cfg_open(self, idx):
        if idx is None or idx >= len(self.cfg_files):
            return
        label, path, ro = self.cfg_files[idx]

        def work():
            core.prepare_config_file(self.cfg, path)
            return core.read_text(path) if path.exists() else ""
        self.bg(work, done=lambda text: self._cfg_show(idx, text))

    def _cfg_show(self, idx, text):
        label, path, ro = self.cfg_files[idx]
        self.cfg_index = idx
        self._crlf = "\r\n" in text
        text = text.replace("\r\n", "\n")
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        if ro:
            self.editor.configure(state="disabled")
        self.cfg_title.configure(text=f"{path}" + ("   (generated - regenerated automatically)" if ro else ""))
        self.cfg_list.selection_clear(0, "end")
        self.cfg_list.selection_set(idx)

    def cfg_save(self):
        if self.cfg_index is None:
            return
        label, path, ro = self.cfg_files[self.cfg_index]
        if ro:
            messagebox.showinfo("Stackyard", "This file is generated. Change settings on the Virtual hosts / Versions tabs.")
            return
        text = self.editor.get("1.0", "end-1c")
        if self._crlf:
            text = text.replace("\n", "\r\n")
        try:
            core.write_text(path, text, backup=True)
        except PermissionError:
            messagebox.showerror("Stackyard", f"Permission denied writing {path}.\n"
                                 "For the hosts file, restart Stackyard as administrator.")
            return
        self.editor.edit_modified(False)
        self.log(f"Saved {path} (previous version kept as {path.name}.bak)")
        if path.name in ("httpd.conf", "php.ini"):
            self.after_config_change(label)

    def after_config_change(self, what: str):
        if self.last_state.get("httpd") in ("running", "starting"):
            if messagebox.askyesno("Stackyard", f"{what} changed. Restart Apache to apply?"):
                self.svc_action("httpd", "restart")
        if self.cfg_index is not None and self.cfg_files[self.cfg_index][1].name == "php.ini":
            self._cfg_open(self.cfg_index)

    def cfg_external(self):
        if self.cfg_index is not None:
            core.open_in_editor(self.cfg_files[self.cfg_index][1])

    def php_extensions(self):
        php = self.cfg.active_dir("php")
        if not php:
            messagebox.showwarning("Stackyard", "No PHP found.")
            return
        try:
            ExtDialog(self, php)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Stackyard", str(e))

    def test_apache(self):
        httpd = self.cfg.active_dir("httpd")
        if not httpd:
            return

        def work():
            core.integrate_httpd(httpd)
            core.write_managed_conf(self.cfg)
            return core.test_httpd(httpd)

        def done(res):
            ok, out = res
            self.log("Apache config test: " + ("OK" if ok else "FAILED"))
            (messagebox.showinfo if ok else messagebox.showerror)("Apache config test", out or "OK")
        self.bg(work, done=done)

    # ------------------------------------------------------------------ VIRTUAL HOSTS tab
    def _build_vhosts_tab(self):
        f = self.tab_vhosts
        bar = ttk.Frame(f, style="Tab.TFrame")
        bar.pack(fill="x", padx=14, pady=(14, 8))
        self._button(bar, "Add", self.vh_add, style="Accent.TButton").pack(side="left")
        self._button(bar, "Edit", self.vh_edit).pack(side="left", padx=6)
        self._button(bar, "Remove", self.vh_remove, style="Danger.TButton").pack(side="left")
        self._button(bar, "Scan www folder", self.vh_scan).pack(side="left", padx=(16, 0))
        self._button(bar, "Open in browser", self.vh_open).pack(side="left", padx=6)
        self._button(bar, "Apply (hosts file + Apache)", self.vh_apply, style="Accent.TButton").pack(side="right")
        cols = ("domain", "folder", "port", "aliases")
        self.vh_tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse", height=12)
        for c, w in (("domain", 220), ("folder", 460), ("port", 70), ("aliases", 240)):
            self.vh_tree.heading(c, text=c.capitalize())
            self.vh_tree.column(c, width=w, anchor="w")
        self.vh_tree.pack(fill="both", expand=True, padx=14, pady=6)
        self.vh_tree.bind("<Double-1>", lambda _e: self.vh_edit())
        self.vh_status = ttk.Label(f, text="", style="Dim.TLabel", wraplength=980, justify="left")
        self.vh_status.pack(anchor="w", padx=14, pady=(0, 12))
        self.refresh_vhosts()

    def refresh_vhosts(self):
        self.vh_tree.delete(*self.vh_tree.get_children())
        for i, v in enumerate(self.cfg.vhosts):
            self.vh_tree.insert("", "end", iid=str(i), values=(v["domain"], v["path"], v["port"], v.get("aliases", "")))

    def _vh_validator(self, editing: int | None):
        def check(v):
            d = v["domain"].lower()
            if not core.DOMAIN_RE.match(d):
                return ("Invalid domain name (letters, digits, dots and dashes only), e.g. myapp.localhost "
                        "(needs no hosts-file change) or myapp.test")
            if not Path(v["path"]).is_dir():
                return "The folder does not exist."
            if not v["port"].isdigit() or not (0 < int(v["port"]) < 65536):
                return "Port must be a number between 1 and 65535."
            for i, o in enumerate(self.cfg.vhosts):
                if i != editing and o["domain"] == d:
                    return "A virtual host with this domain already exists."
            return None
        return check

    def _vh_dialog(self, title, data, editing):
        return FormDialog(self, title, [
            ("domain", "Domain", data.get("domain", ""), None),
            ("path", "Document root", data.get("path", str(core.WWW_DIR)), "dir"),
            ("port", "Port", str(data.get("port", 80)), None),
            ("aliases", "Aliases (space separated)", data.get("aliases", ""), None),
        ], self._vh_validator(editing)).result

    def vh_add(self):
        r = self._vh_dialog("Add virtual host", {}, None)
        if r:
            self.cfg.vhosts.append({"domain": r["domain"].lower(), "path": r["path"], "port": int(r["port"]), "aliases": r["aliases"]})
            self._vh_changed()

    def _vh_selected(self):
        sel = self.vh_tree.selection()
        return int(sel[0]) if sel else None

    def vh_edit(self):
        i = self._vh_selected()
        if i is None:
            return
        r = self._vh_dialog("Edit virtual host", self.cfg.vhosts[i], i)
        if r:
            self.cfg.vhosts[i] = {"domain": r["domain"].lower(), "path": r["path"], "port": int(r["port"]), "aliases": r["aliases"]}
            self._vh_changed()

    def vh_remove(self):
        i = self._vh_selected()
        if i is not None and messagebox.askyesno("Stackyard", f"Remove {self.cfg.vhosts[i]['domain']}?"):
            del self.cfg.vhosts[i]
            self._vh_changed()

    def vh_scan(self):
        added = core.scan_www(self.cfg)
        self.log(f"Scan: {len(added)} new virtual host(s)" + (": " + ", ".join(v["domain"] for v in added) if added else ""))
        self._vh_changed()

    def vh_open(self):
        i = self._vh_selected()
        if i is not None:
            v = self.cfg.vhosts[i]
            webbrowser.open(f"http://{v['domain']}" + ("" if int(v["port"]) == 80 else f":{v['port']}") + "/")

    def _vh_changed(self):
        self.cfg.save()
        self.refresh_vhosts()
        self.vh_status.configure(text="Changes not applied yet - press 'Apply' to update the hosts file and Apache.")

    def vh_apply(self):
        def done(res):
            self.vh_status.configure(text="Applied." if res["test_ok"] else "Apache config test failed - see the message.")
            if not res["test_ok"]:
                messagebox.showerror("Apache config test failed", res["output"])
                return
            self.log("Virtual hosts written; Apache config test OK.")
            if not res["hosts_ok"]:
                err = res.get("hosts_error", "")
                self.log("Hosts file NOT updated: " + err)
                if core.IS_WIN and not core.is_admin():
                    if messagebox.askyesno(
                            "Hosts file", "Could not update the Windows hosts file (administrator rights needed).\n\n"
                            "Restart Stackyard as administrator now? Then press Apply again."):
                        core.relaunch_as_admin()
                        self.destroy()
                        return
                elif messagebox.askyesno(
                        "Hosts file",
                        "Windows refused to let Stackyard write the hosts file, even with administrator rights:\n\n"
                        f"{err}\n\n"
                        "This is usually antivirus 'hosts file protection' (Windows Security, Kaspersky, Bitdefender...) "
                        "or another program locking the file.\n\n"
                        "Copy the needed lines to the clipboard and open the hosts file in Notepad so you can paste them?"):
                    self.clipboard_clear()
                    self.clipboard_append(core.hosts_block(self.cfg))
                    self.log("Hosts lines copied to the clipboard.")
                    core.open_in_editor(core.HOSTS_FILE)
            else:
                self.log("Hosts file updated.")
            if self.last_state.get("httpd") in ("running", "starting"):
                self.svc_action("httpd", "restart")
        self.bg(lambda: core.apply_vhosts(self.cfg), done=done)

    # ------------------------------------------------------------------ APPS tab
    def _build_apps_tab(self):
        f = self.tab_apps
        self.app_rows = {}
        for key, name, desc in APPS:
            card = theme.make_card(f, padding=(18, 16))
            card._card_outer.pack(fill="x", padx=14, pady=6)
            top = ttk.Frame(card, style="Card.TFrame")
            top.pack(fill="x")
            info = ttk.Frame(top, style="Card.TFrame")
            info.pack(side="left", fill="x", expand=True)
            ttk.Label(info, text=name, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(info, text=desc, style="Card.TLabel", wraplength=760, justify="left").pack(anchor="w", pady=(4, 0))
            st = ttk.Label(info, text="", style="RowMuted.TLabel")
            st.pack(anchor="w", pady=(2, 0))
            self._button(top, "Install / update", lambda k=key: self.install_app(k), style="Accent.TButton").pack(side="right")
            if key == "phpmyadmin":
                self._button(top, "Open", lambda: webbrowser.open("http://localhost/phpmyadmin/")).pack(side="right", padx=8)
            self.app_rows[key] = st
        bar = ttk.Frame(f, style="Tab.TFrame")
        bar.pack(fill="x", padx=14, pady=(12, 4))
        self._button(bar, "Install from URL (zip)...", self.install_url).pack(side="left")
        self._button(bar, "Open apps folder", lambda: core.open_path(core.BASE_DIR)).pack(side="left", padx=8)
        self.progress = ttk.Progressbar(f, mode="determinate", maximum=100, style="Accent.Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=14, pady=(6, 2))
        ttk.Label(f, text=("Tip: 'Install from URL' also adds another version of a tool - e.g. folder name php-8.4.1 with a PHP zip URL - "
                           "then switch to it on the Versions tab."), style="Dim.TLabel", wraplength=980, justify="left").pack(anchor="w", padx=14, pady=4)
        self.refresh_apps()

    def refresh_apps(self):
        for key, lbl in self.app_rows.items():
            lbl.configure(text=core.app_status(key))

    def _progress_cb(self):
        last = [0.0]

        def cb(done, total):
            now = time.time()
            if done != total and now - last[0] < 0.1:
                return
            last[0] = now
            pct = (done / total * 100) if total else 0
            self.q.put(lambda: self.progress.configure(value=pct))
        return cb

    def _install_done(self, _res=None):
        self.progress.configure(value=0)
        self.refresh_apps()
        self.refresh_versions()
        self.poll_now()

    def install_app(self, key: str):
        prog = self._progress_cb()
        if key == "phpmyadmin":
            self.bg(lambda: installer.install_phpmyadmin(self.cfg, self.log, prog), done=self._install_done, busy_key="install")
        elif key == "composer":
            self.bg(lambda: installer.install_composer(self.cfg, self.log, prog), done=self._install_done, busy_key="install")
        elif key == "nodejs":
            self.log("Fetching the list of Node.js versions...")
            self.bg(installer.node_versions, done=lambda vs: self._pick_node(vs, prog))

    def _pick_node(self, versions, prog):
        choices = [f"{v}  (LTS {lts})" if lts else v for v, lts in versions[:60]]
        # LTS first, then the rest
        choices.sort(key=lambda c: ("LTS" not in c,), reverse=False)
        if not choices:
            messagebox.showwarning("Stackyard", "No Node.js versions found.")
            return
        r = PickDialog(self, "Install Node.js", "Version to install:", choices).result
        if r:
            ver = r.split()[0]
            self.bg(lambda: installer.install_node(self.cfg, self.log, prog, ver), done=self._install_done, busy_key="install")

    def install_url(self):
        def check(v):
            if not v["name"]:
                return "Enter the folder name to install into."
            if not v["url"].lower().startswith(("http://", "https://")):
                return "Enter a http(s) URL to a .zip file."
            return None
        r = FormDialog(self, "Install from URL", [
            ("name", "Folder name (under base)", "", None),
            ("url", "Zip URL", "https://", None),
        ], check).result
        if r:
            prog = self._progress_cb()
            self.bg(lambda: installer.install_from_url(self.cfg, self.log, prog, r["name"], r["url"]),
                    done=self._install_done, busy_key="install")

    # ------------------------------------------------------------------ shutdown
    def on_close(self):
        running = [k for k, s in self.last_state.items() if s in ("running", "starting")]
        if running:
            stop = self.cfg.data.get("stop_on_exit")
            if not stop:
                ans = messagebox.askyesnocancel(
                    "Stackyard", "Services are still running. Stop them before closing?\n\n"
                    "Yes = stop and exit     No = leave running and exit")
                if ans is None:
                    return
                stop = ans
            if stop:
                self.configure(cursor="watch")
                self.update_idletasks()
                for k in reversed(list(self.services)):
                    try:
                        if self.last_state.get(k) in ("running", "starting"):
                            self.services[k].stop()
                    except Exception:  # noqa: BLE001
                        pass
        self.destroy()


def main():
    core.set_dpi_awareness()       # must run before the first window for crisp text on HiDPI
    core.set_app_user_model_id()   # lets the taskbar show our icon instead of Python's
    App().mainloop()
