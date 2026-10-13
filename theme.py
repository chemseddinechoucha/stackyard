"""Stackyard look & feel.

A hand-tuned ttk theme: larger, more readable type, generous spacing and a calm
blue/grey palette. Standard library only - no third-party packages.

``apply(app)`` configures the named Tk fonts and the ttk styles, then returns a
dict of design tokens (colours, font tuples, named styles) that the widgets use.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# --------------------------------------------------------------------- palette
PALETTE = {
    "window":        "#eef1f5",   # app background
    "surface":       "#ffffff",   # cards / content
    "surface_alt":   "#f4f6f9",   # subtle fills (log, headings, troughs)
    "border":        "#d7dce2",
    "border_strong": "#c2c9d2",
    "text":          "#1b2430",
    "muted":         "#5f6b7a",
    "accent":        "#2f6feb",
    "accent_active": "#2559c9",
    "accent_soft":   "#e8efff",
    "on_accent":     "#ffffff",
    "hover":         "#e9f0fc",
    "select":        "#cfe0fb",
    "button":        "#ffffff",
    "button_active": "#eaeef4",
    "success":       "#2e9e4f",
    "warning":       "#cf8a08",
    "info":          "#3b82c4",
    "stopped":       "#adb5bd",
    "danger":        "#d9534f",
}

# Base type sizes (points). Bumped well above the Tk defaults for readability.
BASE_SIZE = 11
SMALL_SIZE = 10
HEADING_SIZE = 12
TITLE_SIZE = 20
MONO_SIZE = 11


def _pick_family(app: tk.Misc, candidates: tuple[str, ...], fallback: str) -> str:
    try:
        available = set(tkfont.families(app))
    except tk.TclError:
        return fallback
    for name in candidates:
        if name in available:
            return name
    return fallback


def apply(app: tk.Tk) -> dict:
    """Theme ``app`` and return the design tokens."""
    p = PALETTE
    ui = _pick_family(app, ("Segoe UI Variable Text", "Segoe UI", "Verdana", "Helvetica"), "Segoe UI")
    mono = _pick_family(app, ("Cascadia Mono", "Cascadia Code", "Consolas", "Courier New"), "Consolas")

    _rescale_named_fonts(ui, mono)

    # Make classic (non-ttk) widgets such as Text/Listbox pick up the larger type.
    app.option_add("*Font", "TkDefaultFont")
    for cls in ("Text", "Listbox", "Entry", "Canvas"):
        app.option_add(f"*{cls}.font", "TkDefaultFont")
    app.option_add("*Text.selectBackground", p["select"])
    app.option_add("*Text.selectForeground", p["text"])
    app.option_add("*Text.insertBackground", p["text"])
    app.option_add("*Listbox.selectBackground", p["accent"])
    app.option_add("*Listbox.selectForeground", p["on_accent"])
    app.option_add("*TCombobox*Listbox.font", (ui, BASE_SIZE))
    app.option_add("*TCombobox*Listbox.selectBackground", p["select"])
    app.option_add("*TCombobox*Listbox.selectForeground", p["text"])
    app.option_add("*TCombobox*Listbox.background", p["surface"])
    app.option_add("*TCombobox*Listbox.foreground", p["text"])

    st = ttk.Style(app)
    if "clam" in st.theme_names():
        st.theme_use("clam")

    _configure_styles(st, p, ui, mono)

    return {
        "palette": p,
        "ui": ui,
        "mono": mono,
        "font": (ui, BASE_SIZE),
        "font_small": (ui, SMALL_SIZE),
        "font_bold": (ui, BASE_SIZE, "bold"),
        "title": (ui, TITLE_SIZE, "bold"),
        "subtitle": (ui, BASE_SIZE),
        "card_title": (ui, HEADING_SIZE, "bold"),
        "mono_font": (mono, MONO_SIZE),
    }


def _rescale_named_fonts(ui: str, mono: str) -> None:
    wanted = {
        "TkDefaultFont": (ui, BASE_SIZE, "normal"),
        "TkTextFont": (ui, BASE_SIZE, "normal"),
        "TkMenuFont": (ui, BASE_SIZE, "normal"),
        "TkTooltipFont": (ui, SMALL_SIZE, "normal"),
        "TkHeadingFont": (ui, SMALL_SIZE, "bold"),
        "TkFixedFont": (mono, MONO_SIZE, "normal"),
        "TkCaptionFont": (ui, BASE_SIZE, "normal"),
        "TkSmallCaptionFont": (ui, SMALL_SIZE, "normal"),
        "TkIconFont": (ui, BASE_SIZE, "normal"),
    }
    for name, (family, size, weight) in wanted.items():
        try:
            tkfont.nametofont(name).configure(family=family, size=size, weight=weight)
        except tk.TclError:
            pass


def _configure_styles(st: ttk.Style, p: dict, ui: str, mono: str) -> None:
    st.configure(
        ".",
        background=p["window"], foreground=p["text"],
        fieldbackground=p["surface"], bordercolor=p["border"],
        lightcolor=p["surface"], darkcolor=p["surface"],
        troughcolor=p["surface_alt"], focuscolor=p["accent"],
        selectbackground=p["select"], selectforeground=p["text"],
        font=(ui, BASE_SIZE),
    )

    # -- frames & labels -----------------------------------------------------
    st.configure("TFrame", background=p["window"])
    st.configure("Tab.TFrame", background=p["window"])
    st.configure("Card.TFrame", background=p["surface"])
    st.configure("TLabel", background=p["window"], foreground=p["text"])
    st.configure("Card.TLabel", background=p["surface"], foreground=p["text"])
    st.configure("Header.TFrame", background=p["surface"])
    st.configure("HeaderTitle.TLabel", background=p["surface"], foreground=p["text"], font=(ui, TITLE_SIZE, "bold"))
    st.configure("HeaderSub.TLabel", background=p["surface"], foreground=p["muted"], font=(ui, SMALL_SIZE))
    st.configure("Title.TLabel", background=p["window"], foreground=p["text"], font=(ui, TITLE_SIZE, "bold"))
    st.configure("Subtitle.TLabel", background=p["window"], foreground=p["muted"], font=(ui, BASE_SIZE))
    st.configure("Dim.TLabel", background=p["window"], foreground=p["muted"], font=(ui, SMALL_SIZE))
    st.configure("Svc.TLabel", background=p["surface"], foreground=p["text"], font=(ui, HEADING_SIZE, "bold"))
    st.configure("RowMuted.TLabel", background=p["surface"], foreground=p["muted"], font=(ui, SMALL_SIZE))
    st.configure("CardTitle.TLabel", background=p["surface"], foreground=p["text"], font=(ui, HEADING_SIZE, "bold"))
    st.configure("Badge.TLabel", background=p["accent_soft"], foreground=p["accent"], font=(ui, SMALL_SIZE, "bold"), padding=(8, 3))
    st.configure("Admin.TLabel", background=p["success"], foreground=p["on_accent"], font=(ui, SMALL_SIZE, "bold"), padding=(8, 3))

    # -- buttons -------------------------------------------------------------
    st.configure(
        "TButton",
        background=p["button"], foreground=p["text"],
        bordercolor=p["border_strong"], lightcolor=p["button"], darkcolor=p["button"],
        focuscolor=p["accent"], relief="flat", borderwidth=1,
        padding=(12, 6), font=(ui, BASE_SIZE),
    )
    st.map(
        "TButton",
        background=[("pressed", p["accent_soft"]), ("active", p["button_active"]), ("disabled", p["surface_alt"])],
        foreground=[("disabled", p["muted"])],
        lightcolor=[("active", p["button_active"])], darkcolor=[("active", p["button_active"])],
    )
    st.configure(
        "Accent.TButton",
        background=p["accent"], foreground=p["on_accent"],
        bordercolor=p["accent"], lightcolor=p["accent"], darkcolor=p["accent"],
        focuscolor=p["on_accent"], relief="flat", borderwidth=1,
        padding=(14, 6), font=(ui, BASE_SIZE, "bold"),
    )
    st.map(
        "Accent.TButton",
        background=[("pressed", p["accent_active"]), ("active", p["accent_active"]), ("disabled", "#a9c2f0")],
        lightcolor=[("active", p["accent_active"])], darkcolor=[("active", p["accent_active"])],
        foreground=[("disabled", "#eef2f8")],
    )
    st.configure(
        "Danger.TButton",
        background=p["surface"], foreground=p["danger"],
        bordercolor="#e7b3b1", lightcolor=p["surface"], darkcolor=p["surface"],
        focuscolor=p["danger"], relief="flat", borderwidth=1, padding=(12, 6), font=(ui, BASE_SIZE),
    )
    st.map(
        "Danger.TButton",
        background=[("pressed", "#fbe9e8"), ("active", "#fbe9e8")],
        lightcolor=[("active", "#fbe9e8")], darkcolor=[("active", "#fbe9e8")],
    )

    # -- notebook ------------------------------------------------------------
    st.configure("TNotebook", background=p["window"], borderwidth=0, tabmargins=(2, 6, 2, 0))
    st.configure(
        "TNotebook.Tab",
        background=p["window"], foreground=p["muted"],
        bordercolor=p["window"], lightcolor=p["window"], darkcolor=p["window"],
        padding=(20, 10), font=(ui, BASE_SIZE),
    )
    st.map(
        "TNotebook.Tab",
        background=[("selected", p["accent_soft"]), ("active", p["hover"])],
        foreground=[("selected", p["accent"]), ("active", p["text"])],
        lightcolor=[("selected", p["accent_soft"])], darkcolor=[("selected", p["accent_soft"])],
        expand=[("selected", (0, 0, 0, 0))],
    )

    # -- entries -------------------------------------------------------------
    st.configure("TEntry", fieldbackground=p["surface"], bordercolor=p["border_strong"],
                 insertcolor=p["text"], padding=(8, 6), relief="flat", borderwidth=1)
    st.map("TEntry", bordercolor=[("focus", p["accent"])])
    st.configure("TCombobox", fieldbackground=p["surface"], bordercolor=p["border_strong"],
                 arrowcolor=p["muted"], padding=(8, 5), relief="flat", borderwidth=1)
    st.map("TCombobox",
           bordercolor=[("focus", p["accent"])],
           fieldbackground=[("readonly", p["surface"])],
           selectbackground=[("readonly", p["surface"])],
           selectforeground=[("readonly", p["text"])])

    # -- tables --------------------------------------------------------------
    st.configure("Treeview", background=p["surface"], fieldbackground=p["surface"], foreground=p["text"],
                 bordercolor=p["border"], rowheight=34, font=(ui, BASE_SIZE), borderwidth=1, relief="solid")
    st.configure("Treeview.Heading", background=p["surface_alt"], foreground=p["muted"],
                 font=(ui, SMALL_SIZE, "bold"), relief="flat", padding=(10, 8), borderwidth=0)
    st.map("Treeview",
           background=[("selected", p["select"])],
           foreground=[("selected", p["text"])])
    st.map("Treeview.Heading", background=[("active", p["hover"])])

    # -- misc ------------------------------------------------------------------
    st.configure("TLabelframe", background=p["window"], bordercolor=p["border"], relief="solid", borderwidth=1)
    st.configure("TLabelframe.Label", background=p["window"], foreground=p["muted"], font=(ui, SMALL_SIZE, "bold"))
    st.configure("TCheckbutton", background=p["window"], foreground=p["text"], font=(ui, BASE_SIZE), focuscolor=p["accent"])
    st.map("TCheckbutton", background=[("active", p["window"])], foreground=[("disabled", p["muted"])])
    st.configure("Card.TCheckbutton", background=p["surface"], foreground=p["text"], font=(ui, BASE_SIZE))
    st.map("Card.TCheckbutton", background=[("active", p["surface"])])
    st.configure("TSeparator", background=p["border"])
    st.configure("Accent.Horizontal.TProgressbar", background=p["accent"], troughcolor=p["surface_alt"],
                 bordercolor=p["surface_alt"], lightcolor=p["accent"], darkcolor=p["accent"], thickness=8)
    for orient, sname in (("Vertical", "Vertical.TScrollbar"), ("Horizontal", "Horizontal.TScrollbar")):
        st.configure(sname, background=p["surface_alt"], troughcolor=p["window"], bordercolor=p["window"],
                     arrowcolor=p["muted"], lightcolor=p["surface_alt"], darkcolor=p["surface_alt"], relief="flat")
        st.map(sname, background=[("active", p["border_strong"])], arrowcolor=[("active", p["text"])])


def make_card(parent: tk.Misc, padding=(16, 14), hover: bool = False) -> tk.Frame:
    """A white card with a 1px border. Returns the inner frame to put content in.

    Set ``inner._card_outer`` to the outer frame (for hover recolouring).
    """
    p = PALETTE
    outer = tk.Frame(parent, background=p["border"], highlightthickness=0, borderwidth=0)
    inner = ttk.Frame(outer, style="Card.TFrame", padding=padding)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    inner._card_outer = outer  # type: ignore[attr-defined]
    if hover:
        inner._set_hover = lambda on: outer.configure(  # type: ignore[attr-defined]
            background=p["accent"] if on else p["border"])
    return inner
