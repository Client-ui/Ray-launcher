"""Ray Client – UI toolkit: theme, pixel font, custom widgets, bolt logo, dialogs."""
import os, sys
import tkinter as tk
from tkinter import ttk, font as tkfont

# ───────────── palette (sampled from the Ray Client main menu) ─────────────
BG, GRID = "#05070f", "#0b1226"
PANEL = "#090e1c"
BTN, BTN_HOVER = "#0d1226", "#141c38"
BORDER, BORDER_HI = "#1b2441", "#2e3d6b"
SEL, SEL_HOVER = "#1e3a6e", "#264a88"
BLUE, BLUE_DIM = "#3b82f6", "#10234a"
TEXT, MUTED, DIM = "#e8eeff", "#8f9bbd", "#566082"
GREEN, RED, GOLD = "#4ade80", "#f87171", "#fbbf24"
DANGER, DANGER_HOVER, DANGER_BORDER = "#2a0f16", "#3a1520", "#6b2230"


class Theme:
    sc = 1.0          # overall UI scale (DPI * user setting)
    pix = "Courier"   # pixel family (Silkscreen when it could be loaded)
    body = "Segoe UI"
    mono = "Consolas"


def px(n):
    return max(1, int(round(n * Theme.sc)))


def pfont(size=16, bold=False):
    return (Theme.pix, -px(size), "bold" if bold else "normal")


def bfont(size=13, bold=False):
    return (Theme.body, -px(size), "bold" if bold else "normal")


def mfont(size=12):
    return (Theme.mono, -px(size))


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def load_fonts(root):
    """Register the bundled Silkscreen pixel font for this process only, then pick families."""
    for name in ("Silkscreen-Regular.ttf", "Silkscreen-Bold.ttf"):
        path = resource_path(os.path.join("assets", "fonts", name))
        if not os.path.exists(path):
            continue
        try:
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.gdi32.AddFontResourceExW(path, 0x10, 0)  # FR_PRIVATE
            elif sys.platform.startswith("linux"):
                import ctypes
                fc = ctypes.CDLL("libfontconfig.so.1")
                fc.FcConfigAppFontAddFile(None, path.encode())
        except Exception:
            pass
    fams = {f.lower(): f for f in tkfont.families(root)}
    if "silkscreen" in fams:
        Theme.pix = fams["silkscreen"]
    else:
        Theme.pix = fams.get("consolas") or fams.get("courier new") or "Courier"
    for cand in ("segoe ui", "helvetica neue", "dejavu sans", "arial"):
        if cand in fams:
            Theme.body = fams[cand]; break
    else:
        Theme.body = tkfont.nametofont("TkDefaultFont").actual("family")
    for cand in ("consolas", "menlo", "dejavu sans mono", "courier new"):
        if cand in fams:
            Theme.mono = fams[cand]; break


def dark_titlebar(win):
    """Windows 10/11: dark native title bar."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        v = ctypes.c_int(1)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass


# ───────────── pixel-art lightning bolt ─────────────
BOLT = """
.........XXX.
........XXXX.
.......XXXXX.
......XXXXX..
.....XXXXXX..
....XXXXXXX..
...XXXXXXXXXX
..XXXXXXXXXXX
.....XXXXXX..
.....XXXXX...
....XXXXX....
....XXXX.....
...XXXX......
...XXX.......
..XXX........
..XX.........
..X..........
""".strip().split("\n")


def _lerp(a, b, t):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def bolt_pixels():
    """-> dict {(x, y): colour} including a 2-px dark-blue outline/glow."""
    h, w = len(BOLT), len(BOLT[0])
    fill = {(x, y) for y in range(h) for x in range(w) if BOLT[y][x] == "X"}
    out = {}
    for ring, col in ((2, "#0a1736"), (1, BLUE_DIM)):
        for (x, y) in fill:
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    p = (x + dx, y + dy)
                    if p not in fill:
                        out[p] = col if ring == 1 or p not in out else out[p]
    for (x, y) in fill:
        t = y / (h - 1)
        c = _lerp("#fff0a8", "#f59e0b", t)
        if x == min(xx for (xx, yy) in fill if yy == y):  # bright left edge highlight
            c = _lerp("#ffffff", c, 0.35)
        out[(x, y)] = c
    return out


def draw_bolt(cv, cx, top, size, tag="bolt"):
    """Draw the bolt centred on cx. Returns (width, height) used in px."""
    pts = bolt_pixels()
    h, w = len(BOLT), len(BOLT[0])
    x0 = cx - (w * size) // 2
    y0 = top + 2 * size
    for (x, y), col in pts.items():
        cv.create_rectangle(x0 + x * size, y0 + y * size, x0 + (x + 1) * size, y0 + (y + 1) * size,
                            fill=col, outline="", tags=tag)
    return w * size, (h + 4) * size


def bolt_photoimage(size=4):
    pts = bolt_pixels()
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    minx, miny = min(xs), min(ys)
    w, h = (max(xs) - minx + 1), (max(ys) - miny + 1)
    side = max(w, h)
    img = tk.PhotoImage(width=side * size, height=side * size)
    ox, oy = (side - w) // 2, (side - h) // 2
    for (x, y), col in pts.items():
        X, Y = (x - minx + ox) * size, (y - miny + oy) * size
        img.put(col, to=(X, Y, X + size, Y + size))
    return img


# ───────────── canvas helpers ─────────────
def chamfer(x1, y1, x2, y2, c):
    return [x1 + c, y1, x2 - c, y1, x2, y1 + c, x2, y2 - c, x2 - c, y2, x1 + c, y2, x1, y2 - c, x1, y1 + c]


class GridCanvas(tk.Canvas):
    """Canvas with the faint blueprint grid from the main menu."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, highlightthickness=0, **kw)
        self._grid_job = None
        self.bind("<Configure>", self._schedule_grid, add="+")

    def _schedule_grid(self, _e=None):
        if self._grid_job: self.after_cancel(self._grid_job)
        self._grid_job = self.after(30, self.draw_grid)

    def draw_grid(self):
        self._grid_job = None
        self.delete("grid")
        w, h, step = self.winfo_width(), self.winfo_height(), px(48)
        for x in range(0, w, step):
            self.create_line(x, 0, x, h, fill=GRID, tags="grid")
        for y in range(0, h, step):
            self.create_line(0, y, w, y, fill=GRID, tags="grid")
        self.tag_lower("grid")


# ───────────── widgets ─────────────
class RButton(tk.Canvas):
    """Flat pixel-style button. styles: normal | primary | danger | nav"""
    STYLES = {
        "normal": (BTN, BORDER, BTN_HOVER, BORDER_HI, TEXT),
        "primary": (SEL, BLUE, SEL_HOVER, BLUE, "#ffffff"),
        "danger": (DANGER, DANGER_BORDER, DANGER_HOVER, RED, "#ffd5da"),
        "nav": (PANEL, PANEL, BTN, BORDER, MUTED),
    }

    def __init__(self, parent, text, command=None, style="normal", width=None, height=44,
                 size=14, anchor="center", bg=None, textvariable=None):
        self.style, self.command, self.size, self.anchor_ = style, command, size, anchor
        self.hover = self.pressed = self.active = False
        self.enabled = True
        self._text = text
        self._var = textvariable
        super().__init__(parent, width=px(width) if width else px(120), height=px(height),
                         bg=bg or parent.cget("bg"), highlightthickness=0, cursor="hand2")
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, pressed=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(pressed=True))
        self.bind("<ButtonRelease-1>", self._release)
        if textvariable is not None:
            tid = textvariable.trace_add("write", lambda *a: self.redraw())
            self.bind("<Destroy>", lambda e: self._untrace(textvariable, tid) if e.widget is self else None, add="+")

    def _untrace(self, var, tid):
        try: var.trace_remove("write", tid)
        except Exception: pass

    def _set(self, **kw):
        for k, v in kw.items(): setattr(self, k, v)
        self.redraw()

    def _release(self, e):
        was = self.pressed
        self._set(pressed=False)
        if was and self.enabled and 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height():
            if self.command: self.command()

    def set_text(self, t):
        self._text = t; self.redraw()

    def set_enabled(self, on):
        self.enabled = on
        self.configure(cursor="hand2" if on else "arrow")
        self.redraw()

    def set_active(self, on):
        self.active = on; self.redraw()

    def redraw(self):
        try:
            if not self.winfo_exists(): return
            self.delete("all")
        except tk.TclError:
            return
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4: return
        fill, bd, fill_h, bd_h, fg = self.STYLES["primary" if self.active else self.style]
        if self.active and self.style == "nav": fg = "#ffffff"
        if self.enabled and self.hover:
            fill, bd = fill_h, bd_h
            if self.style == "nav" and not self.active: fg = TEXT
        if not self.enabled: fg, fill, bd = DIM, PANEL if self.style == "nav" else BTN, PANEL if self.style == "nav" else BORDER
        if self.pressed and self.enabled: fill = BLUE_DIM
        c = px(3)
        self.create_polygon(chamfer(0, 0, w - 1, h - 1, c), fill=fill, outline=bd, width=1)
        text = self._var.get() if self._var is not None else self._text
        if self.anchor_ == "w":
            self.create_text(px(16), h // 2, text=text, fill=fg, font=pfont(self.size), anchor="w")
        else:
            self.create_text(w // 2, h // 2, text=text, fill=fg, font=pfont(self.size))


class RCheck(tk.Frame):
    def __init__(self, parent, text, variable, bg=PANEL, command=None):
        super().__init__(parent, bg=bg, cursor="hand2")
        self.var, self.command = variable, command
        s = px(18)
        self.box = tk.Canvas(self, width=s, height=s, bg=bg, highlightthickness=0)
        self.box.pack(side="left")
        self.lbl = tk.Label(self, text=text, bg=bg, fg=TEXT, font=bfont(13))
        self.lbl.pack(side="left", padx=(px(8), 0))
        for w in (self, self.box, self.lbl): w.bind("<Button-1>", self.toggle)
        tid = variable.trace_add("write", lambda *a: self.draw())
        self.bind("<Destroy>", lambda e: self._untrace(tid) if e.widget is self else None, add="+")
        self.draw()

    def _untrace(self, tid):
        try: self.var.trace_remove("write", tid)
        except Exception: pass

    def toggle(self, _e=None):
        self.var.set(not self.var.get())
        if self.command: self.command()

    def draw(self):
        s = px(18)
        self.box.delete("all")
        on = bool(self.var.get())
        self.box.create_polygon(chamfer(0, 0, s - 1, s - 1, px(2)), fill=SEL if on else BTN,
                                outline=BLUE if on else BORDER_HI)
        if on:
            u = s / 9
            pts = [(2, 4.5), (3.5, 6), (7, 2.5)]
            self.box.create_line(*[v * u for p in pts for v in p], fill="#ffffff", width=max(2, px(2)))


def card(parent, **kw):
    return tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, **kw)


def label(parent, text, kind="body", bg=None, **kw):
    bg = bg or parent.cget("bg")
    styles = {
        "body": (TEXT, bfont(13)), "muted": (MUTED, bfont(12)), "dim": (DIM, bfont(11)),
        "cap": (MUTED, pfont(8)), "h2": (TEXT, pfont(16, True)), "h1": (TEXT, pfont(32, True)),
        "pix": (TEXT, pfont(12)), "pixm": (MUTED, pfont(8)),
    }
    fg, fnt = styles[kind]
    return tk.Label(parent, text=text, bg=bg, fg=kw.pop("fg", fg), font=kw.pop("font", fnt), **kw)


def entry(parent, var, width=None, show=None, bg=BTN):
    e = tk.Entry(parent, textvariable=var, bg=bg, fg=TEXT, insertbackground=TEXT, relief="flat",
                 font=bfont(13), highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=BLUE, disabledbackground=BTN, selectbackground=SEL,
                 selectforeground="#ffffff", show=show or "")
    if width: e.configure(width=width)
    return e


def setup_ttk(root):
    s = ttk.Style(root)
    try: s.theme_use("clam")
    except tk.TclError: pass
    s.configure("Ray.TCombobox", fieldbackground=BTN, background=BORDER_HI, foreground=TEXT,
                arrowcolor=TEXT, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                selectbackground=BTN, selectforeground=TEXT, padding=px(7), arrowsize=px(14))
    s.map("Ray.TCombobox", fieldbackground=[("readonly", BTN), ("focus", BTN)],
          foreground=[("readonly", TEXT)], bordercolor=[("focus", BLUE)],
          selectbackground=[("readonly", BTN)], selectforeground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", BTN)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", SEL)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", bfont(13))
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    s.configure("Ray.Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                rowheight=px(32), borderwidth=0, font=bfont(13), relief="flat")
    s.configure("Ray.Treeview.Heading", background=BTN, foreground=MUTED, relief="flat",
                font=pfont(8), padding=px(8), borderwidth=0)
    s.map("Ray.Treeview", background=[("selected", SEL)], foreground=[("selected", "#ffffff")])
    s.map("Ray.Treeview.Heading", background=[("active", BTN_HOVER)])
    s.layout("Ray.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    for o in ("Vertical", "Horizontal"):
        s.configure(f"Ray.{o}.TScrollbar", troughcolor=PANEL, background=BORDER_HI, bordercolor=PANEL,
                    arrowcolor=MUTED, lightcolor=BORDER_HI, darkcolor=BORDER_HI, relief="flat",
                    gripcount=0, arrowsize=px(12))
        s.map(f"Ray.{o}.TScrollbar", background=[("active", BLUE_DIM), ("pressed", BLUE)])
    s.configure("Ray.Horizontal.TProgressbar", troughcolor=BTN, background=BLUE, bordercolor=BORDER,
                lightcolor=BLUE, darkcolor=BLUE, thickness=px(8))
    s.configure("Ray.Horizontal.TScale", troughcolor=BTN, background=BLUE, bordercolor=BORDER,
                lightcolor=BLUE, darkcolor=BLUE)
    s.map("Ray.Horizontal.TScale", background=[("active", SEL_HOVER)])


class ScrollFrame(tk.Frame):
    """Vertically scrollable container; put content in `.inner`."""

    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview, style="Ray.Vertical.TScrollbar")
        self.cv.configure(yscrollcommand=self.sb.set)
        self.sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bg=bg)
        self._win = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._win, width=e.width))
        self.bind("<Enter>", self._bind_wheel)
        self.bind("<Leave>", self._unbind_wheel)
        self.bind("<Destroy>", self._unbind_wheel)

    def _bind_wheel(self, _e=None):
        self.bind_all("<MouseWheel>", self._wheel)
        self.bind_all("<Button-4>", lambda e: self._scroll(-3))
        self.bind_all("<Button-5>", lambda e: self._scroll(3))

    def _unbind_wheel(self, _e=None):
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            try: self.unbind_all(ev)
            except tk.TclError: pass

    def _scroll(self, n):
        if self.inner.winfo_height() > self.cv.winfo_height():
            self.cv.yview_scroll(n, "units")

    def _wheel(self, e):
        if e.delta: self._scroll(-1 * int(e.delta / 120 * 3) if abs(e.delta) >= 120 else (-3 if e.delta > 0 else 3))


def tree_with_scroll(parent, columns, widths, height=10):
    """-> (frame, Treeview). columns: [(id, heading)]"""
    fr = tk.Frame(parent, bg=PANEL)
    tv = ttk.Treeview(fr, columns=[c[0] for c in columns], show="headings", style="Ray.Treeview",
                      selectmode="browse", height=height)
    for (cid, head), w in zip(columns, widths):
        tv.heading(cid, text=head, anchor="w")
        tv.column(cid, width=px(w), anchor="w", stretch=(w >= 140))
    sb = ttk.Scrollbar(fr, orient="vertical", command=tv.yview, style="Ray.Vertical.TScrollbar")
    tv.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    tv.pack(side="left", fill="both", expand=True)
    tv.tag_configure("odd", background="#0b1122")
    tv.tag_configure("good", foreground=GREEN)
    tv.tag_configure("off", foreground=DIM)
    return fr, tv


# ───────────── dialogs ─────────────
class Dialog(tk.Toplevel):
    def __init__(self, root, title, width=460, height=None):
        super().__init__(root)
        self.root_ = root
        self.title(title)
        self.configure(bg=BG, highlightbackground=BORDER_HI, highlightthickness=1)
        self.transient(root)
        self.resizable(False, False)
        self.result = None
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True, padx=px(24), pady=px(22))
        self.dw, self.dh = px(width), (px(height) if height else None)
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)

    def show(self):
        self.update_idletasks()
        w = self.dw
        h = self.dh or self.winfo_reqheight()
        r = self.root_
        x = r.winfo_rootx() + (r.winfo_width() - w) // 2
        y = r.winfo_rooty() + (r.winfo_height() - h) // 3
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        dark_titlebar(self)
        try: self.grab_set()
        except tk.TclError: pass
        self.focus_set()
        return self

    def close(self, result=None):
        if result is not None: self.result = result
        try: self.grab_release()
        except tk.TclError: pass
        self.destroy()


def message(root, title, text, kind="info", buttons=None, width=460):
    """Themed message box. buttons: list of (label, value, style). Returns clicked value."""
    d = Dialog(root, title, width)
    color = {"info": BLUE, "error": RED, "warn": GOLD, "ok": GREEN}[kind]
    label(d.body, title.upper(), "h2", fg=color).pack(anchor="w")
    tk.Label(d.body, text=text, bg=BG, fg=MUTED, font=bfont(13), justify="left",
             wraplength=px(width - 50)).pack(anchor="w", pady=(px(10), px(18)))
    row = tk.Frame(d.body, bg=BG); row.pack(anchor="e")
    for lab, val, style in (buttons or [("OK", True, "primary")]):
        RButton(row, lab, lambda v=val: d.close(v if v is not None else False), style, width=max(90, 14 * len(lab) + 30),
                height=38, size=11).pack(side="left", padx=(px(8), 0))
    d.show(); root.wait_window(d)
    return d.result


def ask_text(root, title, prompt, initial="", width=420):
    d = Dialog(root, title, width)
    label(d.body, title.upper(), "h2").pack(anchor="w")
    label(d.body, prompt, "muted", wraplength=px(width - 50), justify="left").pack(anchor="w", pady=(px(8), px(12)))
    var = tk.StringVar(value=initial)
    e = entry(d.body, var); e.pack(fill="x", ipady=px(7))
    row = tk.Frame(d.body, bg=BG); row.pack(anchor="e", pady=(px(18), 0))
    RButton(row, "CANCEL", lambda: d.close(False), width=100, height=38, size=11).pack(side="left")
    RButton(row, "OK", lambda: d.close(var.get().strip()), "primary", width=90, height=38,
            size=11).pack(side="left", padx=(px(8), 0))
    e.bind("<Return>", lambda ev: d.close(var.get().strip()))
    d.show(); e.focus_set(); root.wait_window(d)
    return d.result if d.result else None
