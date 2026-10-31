"""Ray Client – Minecraft Java launcher (Microsoft + offline accounts, instances, mod loaders)."""
import collections, queue, shlex, shutil, subprocess, sys, threading, webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, font as tkfont
from pathlib import Path

import requests

import ray_core as core
from ray_core import mcl, APP, APP_VERSION, AuthError
import ray_ui as U
from ray_ui import (RButton, RCheck, GridCanvas, ScrollFrame, card, label, entry, px, pfont, bfont, mfont,
                    message, ask_text, Dialog, tree_with_scroll)

NAV = [("play", "PLAY"), ("versions", "VERSIONS"), ("mods", "MODS"),
       ("accounts", "ACCOUNTS"), ("console", "CONSOLE"), ("settings", "SETTINGS")]
RAM_STEPS = 1


class RayClient:
    def __init__(self, root):
        self.root = root
        self.cfg = core.read_config()
        self.instances = core.load_instances(self.cfg)
        self.store = core.AccountStore()
        self._migrate_offline_name()
        self.q = queue.Queue()
        self.busy = False
        self.game_proc = None
        self.versions, self.installed, self.installed_order = [], set(), []
        self.log = collections.deque(maxlen=5000)
        self.console_text = None
        self.page_name = "play"

        # shared state (survives UI rebuilds)
        self.status = tk.StringVar(value="Ready.")
        self.progress = tk.DoubleVar(value=0)
        self.version_var = tk.StringVar(value=self.cfg.get("last_version", ""))
        self.inst_var = tk.StringVar(value=self.cfg["selected_profile"])
        self.acc_var = tk.StringVar()

        root.title(APP)
        root.configure(bg=U.BG)
        root.geometry("1120x740")
        root.minsize(960, 660)
        self._icon = U.bolt_photoimage(4)
        try: root.iconphoto(True, self._icon)
        except tk.TclError: pass
        U.dark_titlebar(root)
        self.build_shell()
        self.show("play")
        root.after(40, self.pump)
        root.bind("<Control-plus>", lambda e: self.step_scale(10))
        root.bind("<Control-equal>", lambda e: self.step_scale(10))
        root.bind("<Control-minus>", lambda e: self.step_scale(-10))
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_versions(first=True)

    # ───────────────────────── plumbing ─────────────────────────
    @property
    def mc_dir(self):
        return self.instances[self.cfg["selected_profile"]]

    def save(self):
        self.cfg["profiles"] = self.instances
        core.write_config(self.cfg)

    def _migrate_offline_name(self):
        name = self.cfg.get("offline_name")
        if name and not self.store.accounts and core.valid_username(name):
            self.store.add_offline(name)

    def post(self, fn, *a):
        """Thread-safe: run fn(*a) on the Tk main thread."""
        self.q.put((fn, a))

    def pump(self):
        self.root.after(40, self.pump)
        for _ in range(400):
            try: fn, a = self.q.get_nowait()
            except queue.Empty: break
            try: fn(*a)
            except Exception as e:  # never let one bad callback kill the loop
                print("UI callback error:", repr(e), file=sys.stderr)

    def set_progress(self, v):
        self.progress.set(max(0, min(100, v)))

    def callback(self):
        st = {"max": 1}
        return {"setStatus": lambda t: self.post(self.status.set, str(t)),
                "setMax": lambda m: st.update(max=max(1, m)),
                "setProgress": lambda p: self.post(self.set_progress, p * 100 / st["max"])}

    def background(self, title, work, done=None, quiet=False, err_title="Ray Client"):
        if self.busy:
            if not quiet: self.status.set("Another task is still running…")
            return False
        self.busy = True
        self.status.set(title); self.progress.set(0); self.update_play_state()

        def run():
            try:
                res = work()
                self.post(self._finish, done, res)
            except Exception as e:
                self.post(self._fail, e, err_title, quiet)
        threading.Thread(target=run, daemon=True).start()
        return True

    def _finish(self, done, res):
        self.busy = False; self.update_play_state()
        if done:
            done(res)
        else:
            self.status.set("Done.")
        self.progress.set(0)

    def _fail(self, e, title, quiet):
        self.busy = False; self.update_play_state(); self.progress.set(0)
        if isinstance(e, requests.exceptions.RequestException):
            text = "Network problem. Check your internet connection and try again."
        else:
            text = str(e) or e.__class__.__name__
        self.status.set("Failed: " + text.splitlines()[0][:120])
        if not quiet:
            message(self.root, "Auth problem" if isinstance(e, AuthError) else title, text, "error", width=520)

    def on_close(self):
        if self.game_proc and self.game_proc.poll() is None:
            if not message(self.root, "Minecraft is running",
                           "Closing the launcher will not close the game. Close anyway?", "warn",
                           [("CANCEL", False, "normal"), ("CLOSE", True, "primary")]):
                return
        self.root.destroy()

    # ───────────────────────── shell / navigation ─────────────────────────
    def build_shell(self):
        self.shell = tk.Frame(self.root, bg=U.BG)
        self.shell.pack(fill="both", expand=True)
        # bottom status bar
        bar = tk.Frame(self.shell, bg=U.PANEL, highlightbackground=U.BORDER, highlightthickness=1)
        bar.pack(side="bottom", fill="x")
        tk.Label(bar, textvariable=self.status, bg=U.PANEL, fg=U.MUTED, font=bfont(12), anchor="w"
                 ).pack(side="left", fill="x", expand=True, padx=px(16), pady=px(8))
        ttk.Progressbar(bar, variable=self.progress, maximum=100, length=px(260),
                        style="Ray.Horizontal.TProgressbar").pack(side="right", padx=px(16))
        # sidebar
        side = tk.Frame(self.shell, bg=U.PANEL, width=px(212), highlightbackground=U.BORDER, highlightthickness=1)
        side.pack(side="left", fill="y"); side.pack_propagate(False)
        logo = tk.Frame(side, bg=U.PANEL); logo.pack(fill="x", padx=px(18), pady=(px(22), px(24)))
        tk.Label(logo, image=self._icon, bg=U.PANEL).pack(side="left")
        t = tk.Frame(logo, bg=U.PANEL); t.pack(side="left", padx=px(10))
        tk.Label(t, text="RAY", bg=U.PANEL, fg="#ffffff", font=pfont(16, True)).pack(anchor="w")
        tk.Label(t, text="CLIENT", bg=U.PANEL, fg=U.BLUE, font=pfont(16, True)).pack(anchor="w")
        self.nav = {}
        for key, text in NAV:
            b = RButton(side, text, lambda k=key: self.show(k), "nav", height=42, size=12, anchor="w")
            b.pack(fill="x", padx=px(10), pady=px(2))
            self.nav[key] = b
        tk.Frame(side, bg=U.PANEL).pack(fill="both", expand=True)
        label(side, "ACCOUNT", "cap").pack(anchor="w", padx=px(18))
        self.chip = RButton(side, "", lambda: self.show("accounts"), "normal", height=44, size=11,
                            textvariable=self.acc_var)
        self.chip.pack(fill="x", padx=px(10), pady=(px(6), px(14)))
        label(side, f"v{APP_VERSION}", "dim").pack(anchor="w", padx=px(18), pady=(0, px(16)))
        self.view = tk.Frame(self.shell, bg=U.BG)
        self.view.pack(side="left", fill="both", expand=True)
        self.update_account_widgets()

    def show(self, name):
        self.page_name = name
        self.console_text = None
        for w in self.view.winfo_children(): w.destroy()
        for k, b in self.nav.items(): b.set_active(k == name)
        getattr(self, "page_" + name)()

    def header(self, parent, title, sub):
        f = tk.Frame(parent, bg=U.BG); f.pack(fill="x", padx=px(32), pady=(px(28), px(18)))
        label(f, title, "h1").pack(anchor="w")
        label(f, sub, "muted").pack(anchor="w", pady=(px(4), 0))
        return f

    def page_body(self, title, sub, scroll=False):
        self.header(self.view, title, sub)
        if scroll:
            sf = ScrollFrame(self.view); sf.pack(fill="both", expand=True, padx=(px(32), px(14)), pady=(0, px(14)))
            return sf.inner
        body = tk.Frame(self.view, bg=U.BG)
        body.pack(fill="both", expand=True, padx=px(32), pady=(0, px(20)))
        return body

    def update_account_widgets(self):
        acc = self.store.selected()
        if acc:
            self.acc_var.set(acc["name"].upper() + ("  MS" if acc["type"] == "microsoft" else ""))
        else:
            self.acc_var.set("ADD ACCOUNT")

    def update_play_state(self):
        b = getattr(self, "play_btn", None)
        try:
            if b is None or not b.winfo_exists(): return
        except tk.TclError:
            return
        running = self.game_proc is not None
        b.set_enabled(not self.busy and not running)
        b.set_text("RUNNING..." if running else "WORKING..." if self.busy else "PLAY")

    # ───────────────────────── PLAY ─────────────────────────
    def page_play(self):
        cv = GridCanvas(self.view); cv.pack(fill="both", expand=True)
        W = 460
        self.play_btn = RButton(cv, "PLAY", self.play, "primary", width=W, height=60, size=24, bg=U.BG)
        sel = tk.Frame(cv, bg=U.BG)
        left = tk.Frame(sel, bg=U.BG); left.grid(row=0, column=0, sticky="ew")
        right = tk.Frame(sel, bg=U.BG); right.grid(row=0, column=1, sticky="ew", padx=(px(14), 0))
        sel.columnconfigure(0, weight=1, uniform="s"); sel.columnconfigure(1, weight=1, uniform="s")
        label(left, "VERSION", "cap").pack(anchor="w", pady=(0, px(4)))
        self.version_box = ttk.Combobox(left, textvariable=self.version_var, state="readonly",
                                        style="Ray.TCombobox", height=14)
        self.version_box.pack(fill="x")
        self.version_box.bind("<<ComboboxSelected>>", lambda e: self.on_version_pick())
        label(right, "INSTANCE", "cap").pack(anchor="w", pady=(0, px(4)))
        row = tk.Frame(right, bg=U.BG); row.pack(fill="x")
        self.inst_box = ttk.Combobox(row, textvariable=self.inst_var, state="readonly",
                                     style="Ray.TCombobox", values=list(self.instances))
        self.inst_box.pack(side="left", fill="x", expand=True)
        self.inst_box.bind("<<ComboboxSelected>>", lambda e: self.pick_instance())
        RButton(row, "+", self.new_instance, "normal", width=38, height=34, size=16, bg=U.BG
                ).pack(side="left", padx=(px(6), 0))
        bottom = tk.Frame(cv, bg=U.BG)
        RButton(bottom, "", lambda: self.show("accounts"), "normal", width=223, height=46, size=11,
                textvariable=self.acc_var, bg=U.BG).grid(row=0, column=0)
        RButton(bottom, "OPEN FOLDER", lambda: self.safe_open(self.mc_dir), "normal", width=223, height=46,
                size=11, bg=U.BG).grid(row=0, column=1, padx=(px(14), 0))
        ids = {"play": cv.create_window(0, 0, window=self.play_btn, anchor="n"),
               "sel": cv.create_window(0, 0, window=sel, anchor="n", width=px(W)),
               "bot": cv.create_window(0, 0, window=bottom, anchor="n")}
        title_font = tkfont.Font(font=pfont(56, True))

        def layout(_e=None):
            cv.delete("deco")
            w, h = cv.winfo_width(), cv.winfo_height()
            if w < 50: return
            cx = w // 2
            bs = px(6) if h > 700 else px(4)
            total = (21 * bs) + px(4) + px(88) + px(34) + px(60) + px(18) + px(62) + px(14) + px(46)
            y = max(px(10), (h - total) // 2)
            _, bh = U.draw_bolt(cv, cx, y, bs, "deco")
            y += bh + px(4)
            wr, wc = title_font.measure("RAY "), title_font.measure("CLIENT")
            x0 = cx - (wr + wc) // 2
            for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-3, -3), (3, 3), (-3, 3), (3, -3)):
                for txt, off in (("RAY ", 0), ("CLIENT", wr)):
                    cv.create_text(x0 + off + px(dx), y + px(dy), text=txt, anchor="nw", fill=U.BLUE_DIM,
                                   font=pfont(56, True), tags="deco")
            cv.create_text(x0, y, text="RAY ", anchor="nw", fill="#ffffff", font=pfont(56, True), tags="deco")
            cv.create_text(x0 + wr, y, text="CLIENT", anchor="nw", fill=U.BLUE, font=pfont(56, True), tags="deco")
            y += px(88)
            v = self.version_var.get() or "JAVA EDITION"
            cv.create_text(cx, y, text=f"MINECRAFT LAUNCHER  -  {v.upper()}", fill=U.MUTED,
                           font=pfont(14), tags="deco")
            y += px(34)
            cv.coords(ids["play"], cx, y); y += px(60 + 18)
            cv.coords(ids["sel"], cx, y); y += px(62 + 14)
            cv.coords(ids["bot"], cx, y)
            cv.create_text(px(14), h - px(12), text=f"Ray Client v{APP_VERSION}", anchor="sw", fill=U.DIM,
                           font=pfont(10), tags="deco")
            cv.create_text(w - px(14), h - px(12), text="Not affiliated with Mojang AB", anchor="se",
                           fill=U.DIM, font=pfont(10), tags="deco")
        cv.bind("<Configure>", lambda e: (cv.after_idle(layout)), add="+")
        self._play_layout = layout
        self.fill_version_box()
        self.update_play_state()

    def on_version_pick(self):
        self.cfg["last_version"] = self.version_var.get(); self.save()
        if self.page_name == "play": self._play_layout()

    def fill_version_box(self):
        box = getattr(self, "version_box", None)
        try:
            if box is None or not box.winfo_exists(): return
        except tk.TclError:
            return
        releases = [v["id"] for v in self.versions if v.get("type") == "release"]
        inst = [i for i in self.installed_order if i in self.installed]
        values = list(dict.fromkeys(inst + releases))
        box["values"] = values
        if self.version_var.get() not in values and values:
            self.version_var.set(releases[0] if releases else values[0])
        if self.page_name == "play" and hasattr(self, "_play_layout"):
            self._play_layout()

    def pick_instance(self):
        name = self.inst_var.get()
        if name in self.instances:
            self.cfg["selected_profile"] = name; self.save()
            self.status.set(f"Instance: {name}")
            self.refresh_versions()

    def new_instance(self):
        name = ask_text(self.root, "New instance", "Give it a name, e.g. Fabric 1.21 or Survival.")
        if not name: return
        name = " ".join(name.split())[:40]
        if name.casefold() in {n.casefold() for n in self.instances}:
            message(self.root, "Instance exists", "An instance with that name already exists.", "warn"); return
        folder = core.CONFIG_DIR / "instances" / core.instance_slug(name)
        folder.mkdir(parents=True, exist_ok=True)
        self.instances[name] = str(folder)
        self.cfg["selected_profile"] = name
        self.inst_var.set(name)
        self.save()
        if hasattr(self, "inst_box") and self.inst_box.winfo_exists():
            self.inst_box["values"] = list(self.instances)
        self.status.set(f"Created instance '{name}'. It has its own mods, saves and versions.")
        self.refresh_versions()

    def safe_open(self, path):
        try: core.open_folder(path)
        except Exception as e: message(self.root, "Could not open folder", str(e), "error")

    # ───────────────────────── versions data ─────────────────────────
    def refresh_versions(self, first=False):
        def work():
            try: items = mcl.utils.get_version_list()
            except Exception: items = None
            try: inst = mcl.utils.get_installed_versions(self.mc_dir)
            except Exception: inst = []
            return items, inst

        def done(res):
            items, inst = res
            if items is not None: self.versions = items
            self.installed_order = [i["id"] for i in inst if i.get("id")]
            self.installed = set(self.installed_order)
            self.fill_version_box()
            if self.page_name == "versions": self.fill_versions_tree()
            if self.page_name == "mods": self.load_loader_versions()
            if items is None:
                self.status.set("Offline: showing installed versions only.")
            else:
                self.status.set(f"Loaded {len(self.versions)} Minecraft versions.")
        self.background("Fetching Minecraft versions…", work, done, quiet=True)

    # ───────────────────────── VERSIONS ─────────────────────────
    def page_versions(self):
        body = self.page_body("VERSIONS", "Releases, snapshots and your installed mod-loader profiles.")
        bar = tk.Frame(body, bg=U.BG); bar.pack(fill="x", pady=(0, px(12)))
        self.f_rel, self.f_snap, self.f_old = (tk.BooleanVar(value=True), tk.BooleanVar(value=False),
                                               tk.BooleanVar(value=False))
        self.f_search = tk.StringVar()
        for text, var in (("RELEASES", self.f_rel), ("SNAPSHOTS", self.f_snap), ("OLD", self.f_old)):
            c = RCheck(bar, text, var, bg=U.BG, command=self.fill_versions_tree); c.pack(side="left", padx=(0, px(16)))
        e = entry(bar, self.f_search, width=22); e.pack(side="right", ipady=px(5))
        label(bar, "SEARCH", "cap").pack(side="right", padx=(0, px(8)))
        self.f_search.trace_add("write", lambda *a: self.fill_versions_tree())
        fr, self.vtree = tree_with_scroll(body, [("id", "VERSION"), ("type", "TYPE"), ("date", "RELEASED"),
                                                 ("state", "STATUS")], [220, 130, 150, 120])
        fr.pack(fill="both", expand=True)
        row = tk.Frame(body, bg=U.BG); row.pack(fill="x", pady=(px(14), 0))
        RButton(row, "INSTALL", self.install_selected, "primary", width=140, height=42, size=13).pack(side="left")
        RButton(row, "USE VERSION", self.use_selected, "normal", width=150, height=42, size=13
                ).pack(side="left", padx=px(10))
        RButton(row, "DELETE", self.delete_selected, "danger", width=120, height=42, size=13).pack(side="left")
        RButton(row, "REFRESH", self.refresh_versions, "normal", width=120, height=42, size=13).pack(side="right")
        self.fill_versions_tree()

    def fill_versions_tree(self):
        tv = getattr(self, "vtree", None)
        try:
            if tv is None or not tv.winfo_exists(): return
        except tk.TclError:
            return
        tv.delete(*tv.get_children())
        q = self.f_search.get().strip().lower()
        known = set()
        rows = []
        for v in self.versions:
            known.add(v["id"])
            t = v.get("type", "")
            if t == "release" and not self.f_rel.get(): continue
            if t == "snapshot" and not self.f_snap.get(): continue
            if t.startswith("old") and not self.f_old.get(): continue
            d = v.get("releaseTime")
            rows.append((v["id"], t.replace("_", " "), d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]))
        custom = [(i, "modded/custom", "") for i in getattr(self, "installed_order", []) if i not in known]
        n = 0
        for vid, t, d in custom + rows:
            if q and q not in vid.lower(): continue
            ins = vid in self.installed
            tv.insert("", "end", iid=vid, values=(vid, t, d, "INSTALLED" if ins else "-"),
                      tags=("good",) if ins else (("odd",) if n % 2 else ()))
            n += 1

    def selected_version(self):
        sel = self.vtree.selection()
        if not sel:
            message(self.root, "Select a version", "Click a version in the list first.", "warn"); return None
        return sel[0]

    def install_selected(self):
        v = self.selected_version()
        if v: self.install_version(v)

    def install_version(self, v, then=None):
        def work():
            Path(self.mc_dir).mkdir(parents=True, exist_ok=True)
            mcl.install.install_minecraft_version(v, self.mc_dir, callback=self.callback())
            return v

        def done(v):
            self.status.set(f"Minecraft {v} installed.")
            self.refresh_versions()
            if then: then()
        self.background(f"Installing Minecraft {v}…", work, done)

    def use_selected(self):
        v = self.selected_version()
        if not v: return
        self.version_var.set(v); self.cfg["last_version"] = v; self.save()
        self.show("play")

    def delete_selected(self):
        v = self.selected_version()
        if not v: return
        if v not in self.installed:
            message(self.root, "Not installed", f"{v} is not installed in this instance.", "info"); return
        if not message(self.root, "Delete version", f"Delete {v} from instance '{self.cfg['selected_profile']}'?\n"
                       "Worlds and mods are not touched.", "warn",
                       [("CANCEL", False, "normal"), ("DELETE", True, "danger")]):
            return
        shutil.rmtree(Path(self.mc_dir) / "versions" / v, ignore_errors=True)
        self.refresh_versions()

    # ───────────────────────── MODS ─────────────────────────
    def page_mods(self):
        body = self.page_body("MODS", "Install Fabric, Forge, NeoForge or Quilt and manage this instance's mods.", scroll=True)
        c = card(body); c.pack(fill="x", pady=(0, px(16)))
        inner = tk.Frame(c, bg=U.PANEL); inner.pack(fill="x", padx=px(20), pady=px(18))
        label(inner, "MOD LOADER", "h2").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, px(12)))
        label(inner, "LOADER", "cap").grid(row=1, column=0, sticky="w")
        label(inner, "MINECRAFT VERSION", "cap").grid(row=1, column=1, sticky="w", padx=(px(14), 0))
        self.loader_var = tk.StringVar(value=self.cfg.get("last_loader", "fabric"))
        lb = ttk.Combobox(inner, textvariable=self.loader_var, state="readonly", style="Ray.TCombobox",
                          values=["fabric", "forge", "neoforge", "quilt"], width=14)
        lb.grid(row=2, column=0, sticky="ew", pady=(px(4), 0))
        self.mod_mc_var = tk.StringVar(value=self.version_var.get())
        self.mod_mc_box = ttk.Combobox(inner, textvariable=self.mod_mc_var, state="readonly",
                                       style="Ray.TCombobox", values=[v["id"] for v in self.versions if v.get("type") == "release"])
        self.mod_mc_box.grid(row=2, column=1, sticky="ew", padx=(px(14), 0), pady=(px(4), 0))
        RButton(inner, "INSTALL", self.install_loader, "primary", width=140, height=36, size=12
                ).grid(row=2, column=2, padx=(px(14), 0), pady=(px(4), 0))
        inner.columnconfigure(1, weight=1)
        lb.bind("<<ComboboxSelected>>", lambda e: self.load_loader_versions())
        label(inner, "After installing, pick the new profile on the PLAY page.", "dim").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(px(10), 0))
        self.load_loader_versions()

        c2 = card(body); c2.pack(fill="both", expand=True)
        in2 = tk.Frame(c2, bg=U.PANEL); in2.pack(fill="both", expand=True, padx=px(20), pady=px(18))
        top = tk.Frame(in2, bg=U.PANEL); top.pack(fill="x", pady=(0, px(10)))
        label(top, "INSTALLED MODS", "h2").pack(side="left")
        label(top, str(Path(self.mc_dir) / "mods"), "dim").pack(side="right")
        fr, self.mtree = tree_with_scroll(in2, [("name", "FILE"), ("state", "STATE"), ("size", "SIZE")],
                                          [380, 90, 90], height=8)
        fr.pack(fill="both", expand=True)
        row = tk.Frame(in2, bg=U.PANEL); row.pack(fill="x", pady=(px(14), 0))
        for text, fn, st, w in (("ADD MODS", self.add_mods, "primary", 130), ("ON / OFF", self.toggle_mod, "normal", 120),
                                ("REMOVE", self.remove_mod, "danger", 110), ("OPEN FOLDER", lambda: self.safe_open(Path(self.mc_dir) / "mods"), "normal", 150)):
            RButton(row, text, fn, st, width=w, height=38, size=11, bg=U.PANEL).pack(side="left", padx=(0, px(10)))
        self.fill_mods()

    def mods_dir(self):
        p = Path(self.mc_dir) / "mods"; p.mkdir(parents=True, exist_ok=True); return p

    def fill_mods(self):
        tv = self.mtree
        tv.delete(*tv.get_children())
        files = sorted([f for f in self.mods_dir().iterdir()
                        if f.is_file() and (f.suffix == ".jar" or f.name.endswith(".jar.disabled"))],
                       key=lambda f: f.name.lower())
        for i, f in enumerate(files):
            off = f.name.endswith(".disabled")
            tv.insert("", "end", iid=f.name, values=(f.name.replace(".disabled", ""), "OFF" if off else "ON",
                      f"{f.stat().st_size / 1024 / 1024:.1f} MB"), tags=("off",) if off else (("odd",) if i % 2 else ()))

    def add_mods(self):
        paths = filedialog.askopenfilenames(title="Choose mod .jar files", filetypes=[("Mods", "*.jar")])
        for p in paths:
            shutil.copy2(p, self.mods_dir() / Path(p).name)
        if paths: self.fill_mods(); self.status.set(f"Added {len(paths)} mod(s).")

    def _sel_mod(self):
        sel = self.mtree.selection()
        if not sel: message(self.root, "Select a mod", "Click a mod in the list first.", "warn"); return None
        return self.mods_dir() / sel[0]

    def toggle_mod(self):
        f = self._sel_mod()
        if f is None: return
        f.rename(f.with_name(f.name[:-9] if f.name.endswith(".disabled") else f.name + ".disabled"))
        self.fill_mods()

    def remove_mod(self):
        f = self._sel_mod()
        if f is None: return
        if message(self.root, "Remove mod", f"Delete {f.name.replace('.disabled', '')}?", "warn",
                   [("CANCEL", False, "normal"), ("DELETE", True, "danger")]):
            f.unlink(missing_ok=True); self.fill_mods()

    def load_loader_versions(self):
        lid = self.loader_var.get()
        self.cfg["last_loader"] = lid

        def work():
            return mcl.mod_loader.get_mod_loader(lid).get_minecraft_versions(True)

        def done(vs):
            try:
                if not self.mod_mc_box.winfo_exists(): return
            except tk.TclError:
                return
            self.mod_mc_box["values"] = vs
            if self.mod_mc_var.get() not in vs and vs: self.mod_mc_var.set(vs[0])
            self.status.set(f"{lid}: {len(vs)} supported Minecraft versions.")
        self.background(f"Loading {lid} versions…", work, done, quiet=True)

    def managed_java(self, mc_version):
        """Path to the Mojang-managed Java for a version (Forge/NeoForge installers need one)."""
        try:
            import json
            data = json.loads((Path(self.mc_dir) / "versions" / mc_version / f"{mc_version}.json").read_text("utf-8"))
            comp = data["javaVersion"]["component"]
            return mcl.runtime.get_executable_path(comp, self.mc_dir)
        except Exception:
            return None

    def install_loader(self):
        v, lid = self.mod_mc_var.get().strip(), self.loader_var.get()
        if not v:
            message(self.root, "Choose a version", "Pick a Minecraft version first.", "warn"); return

        def work():
            loader = mcl.mod_loader.get_mod_loader(lid)
            if not loader.is_minecraft_version_supported(v):
                raise RuntimeError(f"{loader.get_name()} does not support Minecraft {v}.")
            Path(self.mc_dir).mkdir(parents=True, exist_ok=True)
            java = self.cfg.get("java_path") or None
            if lid in ("forge", "neoforge") and not java:
                mcl.install.install_minecraft_version(v, self.mc_dir, callback=self.callback())
                java = self.managed_java(v)
            return loader.install(v, self.mc_dir, callback=self.callback(), java=java)

        def done(pid):
            self.version_var.set(str(pid)); self.cfg["last_version"] = str(pid); self.save()
            self.refresh_versions()
            message(self.root, "Loader installed", f"Installed profile:\n{pid}\n\nIt is selected on the PLAY page. "
                    "Put matching mods into this instance's mods folder.", "ok")
        self.background(f"Installing {lid} for Minecraft {v}…", work, done, err_title="Loader install failed")

    # ───────────────────────── ACCOUNTS ─────────────────────────
    def page_accounts(self):
        body = self.page_body("ACCOUNTS", "Play with a Microsoft account (premium) or an offline username (cracked).")
        c = card(body); c.pack(fill="both", expand=True)
        inner = tk.Frame(c, bg=U.PANEL); inner.pack(fill="both", expand=True, padx=px(20), pady=px(18))
        fr, self.atree = tree_with_scroll(inner, [("name", "NAME"), ("type", "TYPE"), ("uuid", "UUID"), ("act", "ACTIVE")],
                                          [190, 120, 300, 80], height=8)
        fr.pack(fill="both", expand=True)
        row = tk.Frame(inner, bg=U.PANEL); row.pack(fill="x", pady=(px(16), 0))
        for text, fn, st, w in (("ADD MICROSOFT", self.add_microsoft, "primary", 190), ("ADD OFFLINE", self.add_offline, "normal", 160),
                                ("SET ACTIVE", self.activate_account, "normal", 140), ("REMOVE", self.remove_account, "danger", 120)):
            RButton(row, text, fn, st, width=w, height=40, size=11, bg=U.PANEL).pack(side="left", padx=(0, px(10)))
        tk.Label(inner, text="Microsoft accounts are the real thing: skins, capes and online-mode servers. "
                 "Offline accounts only need a name and work in singleplayer and on servers that allow offline mode. "
                 "Your Microsoft password is never typed into Ray Client - sign-in happens on Microsoft's own page.",
                 bg=U.PANEL, fg=U.DIM, font=bfont(12), justify="left", wraplength=px(700)).pack(anchor="w", pady=(px(16), 0))
        self.fill_accounts()

    def fill_accounts(self):
        tv = self.atree
        tv.delete(*tv.get_children())
        sel = self.store.selected()
        for i, a in enumerate(self.store.accounts):
            ms = a["type"] == "microsoft"
            tv.insert("", "end", iid=a["id"], values=(a["name"], "MICROSOFT" if ms else "OFFLINE", a["uuid"],
                      "YES" if sel and sel["id"] == a["id"] else ""), tags=("good",) if ms else (("odd",) if i % 2 else ()))

    def after_accounts_change(self):
        self.update_account_widgets()
        if self.page_name == "accounts": self.fill_accounts()

    def _sel_acc(self):
        sel = self.atree.selection()
        if not sel: message(self.root, "Select an account", "Click an account in the list first.", "warn"); return None
        return self.store.get(sel[0])

    def activate_account(self):
        a = self._sel_acc()
        if a: self.store.select(a["id"]); self.after_accounts_change()

    def remove_account(self):
        a = self._sel_acc()
        if a and message(self.root, "Remove account", f"Remove {a['name']} from this launcher?", "warn",
                         [("CANCEL", False, "normal"), ("REMOVE", True, "danger")]):
            self.store.remove(a["id"]); self.after_accounts_change()

    def add_offline(self):
        initial = self.cfg.get("offline_name", "")
        while True:
            name = ask_text(self.root, "Offline account", "Choose a username: 3-16 letters, numbers or underscores.", initial)
            if not name: return
            if core.valid_username(name): break
            initial = name
            message(self.root, "Invalid name", "Use 3-16 characters: letters, numbers and _ only.", "warn")
        self.cfg["offline_name"] = name; self.save()
        self.store.add_offline(name)
        self.after_accounts_change()
        self.status.set(f"Offline account '{name}' is ready.")

    # --- Microsoft sign-in ---
    def add_microsoft(self):
        cid = (self.cfg.get("microsoft_client_id", "").strip() or core.DEFAULT_CLIENT_ID)
        if not cid: self.microsoft_setup()
        else: self.microsoft_device_login(cid)

    def microsoft_setup(self):
        d = Dialog(self.root, "Microsoft setup", 600)
        label(d.body, "MICROSOFT SETUP", "h2", fg=U.BLUE).pack(anchor="w")
        tk.Label(d.body, bg=U.BG, fg=U.MUTED, font=bfont(13), justify="left", wraplength=px(550), text=(
            "A launcher needs its own free Azure app to sign players in. One-time setup, about 5 minutes:\n\n"
            "1. Azure portal > App registrations > New registration. Account type: 'Personal Microsoft accounts "
            "only'. Leave the redirect URI empty.\n"
            "2. In the app: Authentication > turn ON 'Allow public client flows'.\n"
            "3. Copy the 'Application (client) ID' and paste it below.\n"
            "4. Mojang must approve the app: send the Client ID through their form. Until they approve it, sign-in "
            "ends with INVALID_REGISTRATION. Offline accounts keep working in the meantime.")).pack(anchor="w", pady=(px(10), px(14)))
        var = tk.StringVar(value=self.cfg.get("microsoft_client_id", ""))
        label(d.body, "APPLICATION (CLIENT) ID", "cap").pack(anchor="w", pady=(0, px(4)))
        e = entry(d.body, var); e.pack(fill="x", ipady=px(7))
        links = tk.Frame(d.body, bg=U.BG); links.pack(anchor="w", pady=(px(14), 0))
        RButton(links, "OPEN AZURE PORTAL", lambda: webbrowser.open(core.AZURE_PORTAL), width=210, height=36, size=10).pack(side="left")
        RButton(links, "MOJANG APPROVAL FORM", lambda: webbrowser.open(core.MOJANG_APP_FORM), width=240, height=36,
                size=10).pack(side="left", padx=px(10))
        row = tk.Frame(d.body, bg=U.BG); row.pack(anchor="e", pady=(px(18), 0))

        def go():
            cid = var.get().strip()
            if len(cid) < 30:
                message(self.root, "Client ID", "That does not look like a Client ID (it is a UUID like "
                        "12345678-abcd-....).", "warn"); return
            self.cfg["microsoft_client_id"] = cid; self.save(); d.close(True)
            self.microsoft_device_login(cid)
        RButton(row, "CANCEL", d.close, width=100, height=38, size=11).pack(side="left")
        RButton(row, "SAVE AND SIGN IN", go, "primary", width=190, height=38, size=11).pack(side="left", padx=(px(8), 0))
        d.show(); e.focus_set()

    def microsoft_device_login(self, cid):
        d = Dialog(self.root, "Sign in with Microsoft", 500)
        cancel = {"v": False}
        label(d.body, "MICROSOFT SIGN-IN", "h2", fg=U.BLUE).pack(anchor="w")
        info = tk.Label(d.body, text="Contacting Microsoft…", bg=U.BG, fg=U.MUTED, font=bfont(13), justify="left",
                        wraplength=px(450)); info.pack(anchor="w", pady=(px(10), px(8)))
        code_lbl = tk.Label(d.body, text="", bg=U.BG, fg="#ffffff", font=pfont(40, True)); code_lbl.pack(pady=px(8))
        state = tk.Label(d.body, text="", bg=U.BG, fg=U.DIM, font=bfont(12), wraplength=px(450), justify="left")
        state.pack(anchor="w", pady=(px(6), px(14)))
        row = tk.Frame(d.body, bg=U.BG); row.pack(anchor="e")
        open_btn = RButton(row, "OPEN BROWSER", None, "primary", width=190, height=38, size=11)
        RButton(row, "CANCEL", lambda: (cancel.update(v=True), d.close()), width=110, height=38, size=11).pack(side="left")
        open_btn.pack(side="left", padx=(px(8), 0)); open_btn.set_enabled(False)
        d.protocol("WM_DELETE_WINDOW", lambda: (cancel.update(v=True), d.close()))
        d.show()
        alive = lambda: not cancel["v"] and d.winfo_exists()

        def show_code(dev):
            if not alive(): return
            url = dev.get("verification_uri", "https://www.microsoft.com/link")
            info.configure(text=f"1. Open {url}\n2. Enter this code and sign in with your Microsoft account:")
            code_lbl.configure(text=dev["user_code"])
            state.configure(text="Waiting for you to finish in the browser… this window closes by itself.")

            def open_it():
                self.root.clipboard_clear(); self.root.clipboard_append(dev["user_code"])
                webbrowser.open(dev.get("verification_uri_complete") or url)
                state.configure(text="Code copied to the clipboard. Waiting for you to finish in the browser…")
            open_btn.command = open_it; open_btn.set_enabled(True)

        def work():
            try:
                dev = core.request_device_code(cid)
                self.post(show_code, dev)
                tok = core.poll_device_token(cid, dev, lambda: not alive_flag())
                self.post(lambda: alive() and state.configure(text="Signed in. Checking your Minecraft profile…"))
                prof = core.minecraft_login_from_ms_token(tok["access_token"])
                self.post(finish, prof, tok.get("refresh_token", ""))
            except Exception as e:
                self.post(fail, e)
        alive_flag = lambda: not cancel["v"]

        def finish(prof, refresh):
            if cancel["v"]: return
            self.store.add_microsoft(prof, refresh)
            d.close()
            self.after_accounts_change()
            self.status.set(f"Signed in as {prof['name']}.")

        def fail(e):
            if cancel["v"]: return
            d.close()
            if isinstance(e, AuthError): text = str(e)
            elif isinstance(e, requests.exceptions.RequestException): text = "Network problem. Check your internet connection."
            else: text = f"{e.__class__.__name__}: {e}"
            message(self.root, "Sign-in failed", text, "error", width=520)
        threading.Thread(target=work, daemon=True).start()

    # ───────────────────────── CONSOLE ─────────────────────────
    def page_console(self):
        body = self.page_body("CONSOLE", "Live game output. If Minecraft crashes, the reason is here.")
        c = card(body); c.pack(fill="both", expand=True)
        wrap = tk.Frame(c, bg=U.PANEL); wrap.pack(fill="both", expand=True, padx=px(2), pady=px(2))
        sb = ttk.Scrollbar(wrap, style="Ray.Vertical.TScrollbar")
        sb.pack(side="right", fill="y")
        t = tk.Text(wrap, bg="#070b16", fg=U.MUTED, relief="flat", font=mfont(12), wrap="none",
                    yscrollcommand=sb.set, padx=px(10), pady=px(8), highlightthickness=0,
                    selectbackground=U.SEL, insertbackground=U.TEXT)
        sb.configure(command=t.yview)
        t.pack(side="left", fill="both", expand=True)
        t.tag_configure("warn", foreground=U.GOLD); t.tag_configure("err", foreground=U.RED)
        t.tag_configure("sys", foreground=U.BLUE)
        t.insert("end", "\n".join(self.log) + ("\n" if self.log else ""))
        t.configure(state="disabled"); t.see("end")
        self.console_text = t
        row = tk.Frame(body, bg=U.BG); row.pack(fill="x", pady=(px(14), 0))
        RButton(row, "COPY LOG", self.copy_log, "normal", width=130, height=38, size=11).pack(side="left")
        RButton(row, "CLEAR", self.clear_log, "normal", width=110, height=38, size=11).pack(side="left", padx=px(10))
        RButton(row, "OPEN LOGS FOLDER", lambda: self.safe_open(Path(self.mc_dir) / "logs"), "normal",
                width=210, height=38, size=11).pack(side="left")

    def log_line(self, line):
        self.log.append(line)
        t = self.console_text
        try:
            if t is None or not t.winfo_exists(): return
        except tk.TclError:
            return
        low = line.lower()
        tag = "err" if ("exception" in low or "/error" in low or "fatal" in low) else \
              "warn" if "/warn" in low else "sys" if line.startswith("[Ray]") else ""
        at_end = t.yview()[1] > 0.98
        t.configure(state="normal"); t.insert("end", line + "\n", tag); t.configure(state="disabled")
        if at_end: t.see("end")

    def copy_log(self):
        self.root.clipboard_clear(); self.root.clipboard_append("\n".join(self.log))
        self.status.set("Log copied to clipboard.")

    def clear_log(self):
        self.log.clear()
        if self.console_text:
            self.console_text.configure(state="normal"); self.console_text.delete("1.0", "end")
            self.console_text.configure(state="disabled")

    # ───────────────────────── PLAY (launch) ─────────────────────────
    def play(self):
        if self.busy or self.game_proc: return
        acc = self.store.selected()
        if not acc:
            self.show("accounts")
            message(self.root, "Add an account first", "Add an offline name to play right away, or sign in with "
                    "Microsoft for online play.", "info"); return
        v = self.version_var.get().strip()
        if not v:
            message(self.root, "Choose a version", "Pick a Minecraft version first.", "warn"); return
        self.cfg["last_version"] = v; self.save()
        cid = self.cfg.get("microsoft_client_id", "").strip() or core.DEFAULT_CLIENT_ID

        def work():
            self.post(self.status.set, "Signing in…")
            name, uid, token = core.ensure_session(self.store, acc, cid)
            Path(self.mc_dir).mkdir(parents=True, exist_ok=True)
            mcl.install.install_minecraft_version(v, self.mc_dir, callback=self.callback())
            ram = int(self.cfg.get("ram_gb", 4))
            jvm = [f"-Xmx{ram}G", f"-Xms{min(ram, 2)}G"] + shlex.split(self.cfg.get("jvm_args", ""), posix=(sys.platform != "win32"))
            opts = {"username": name, "uuid": uid, "token": token, "launcherName": APP,
                    "launcherVersion": APP_VERSION, "gameDirectory": self.mc_dir, "jvmArguments": jvm}
            if self.cfg.get("java_path"): opts["executablePath"] = self.cfg["java_path"]
            w, h = str(self.cfg.get("res_w", "")).strip(), str(self.cfg.get("res_h", "")).strip()
            if w.isdigit() and h.isdigit():
                opts.update(customResolution=True, resolutionWidth=w, resolutionHeight=h)
            cmd = mcl.command.get_minecraft_command(v, self.mc_dir, opts)
            shown = " ".join(("***" if (token and token != "0" and c == token) else c) for c in cmd)
            self.post(self.log_line, f"[Ray] Launching {v} as {name} ({acc['type']})")
            self.post(self.log_line, f"[Ray] {shown[:600]}")
            kw = {"creationflags": 0x08000000} if sys.platform == "win32" else {}
            return subprocess.Popen(cmd, cwd=self.mc_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1, **kw)

        def done(proc):
            self.game_proc = proc
            self.status.set(f"Minecraft {v} is running.")
            self.update_play_state()
            if self.cfg.get("minimize_on_play", True): self.root.iconify()
            threading.Thread(target=self.read_game, args=(proc,), daemon=True).start()
        self.background(f"Preparing Minecraft {v}…", work, done, err_title="Could not launch")

    def read_game(self, proc):
        for line in proc.stdout:
            self.post(self.log_line, line.rstrip())
        self.post(self.game_exited, proc.wait())

    def game_exited(self, code):
        self.game_proc = None
        self.update_play_state()
        self.log_line(f"[Ray] Game exited with code {code}")
        try: self.root.deiconify()
        except tk.TclError: pass
        if code == 0:
            self.status.set("Minecraft closed.")
        else:
            self.status.set(f"Minecraft stopped with code {code}. See CONSOLE.")
            if message(self.root, "Minecraft crashed", f"The game exited with code {code}. The CONSOLE page shows why.",
                       "error", [("CLOSE", False, "normal"), ("OPEN CONSOLE", True, "primary")]):
                self.show("console")

    # ───────────────────────── SETTINGS ─────────────────────────
    def page_settings(self):
        body = self.page_body("SETTINGS", f"Instance: {self.cfg['selected_profile']}", scroll=True)

        def section(title):
            c = card(body); c.pack(fill="x", pady=(0, px(14)))
            f = tk.Frame(c, bg=U.PANEL); f.pack(fill="x", padx=px(20), pady=px(16))
            label(f, title, "h2").pack(anchor="w", pady=(0, px(10)))
            return f

        def field(parent, cap, var, browse=None, width=None):
            label(parent, cap, "cap").pack(anchor="w", pady=(px(6), px(4)))
            r = tk.Frame(parent, bg=U.PANEL); r.pack(fill="x")
            e = entry(r, var, width=width); e.pack(side="left", fill="x" if not width else None, expand=not width, ipady=px(6))
            if browse: RButton(r, "BROWSE", browse, width=100, height=34, size=10, bg=U.PANEL).pack(side="left", padx=(px(8), 0))
            return e

        s = section("GAME")
        self.dir_var = tk.StringVar(value=self.mc_dir)
        field(s, "GAME DIRECTORY", self.dir_var, lambda: self.dir_var.set(filedialog.askdirectory(initialdir=self.mc_dir) or self.dir_var.get()))
        row = tk.Frame(s, bg=U.PANEL); row.pack(fill="x", pady=(px(12), 0))
        RButton(row, "OPEN FOLDER", lambda: self.safe_open(self.mc_dir), width=150, height=36, size=10, bg=U.PANEL).pack(side="left")
        RButton(row, "REMOVE INSTANCE", self.remove_instance, "danger", width=190, height=36, size=10, bg=U.PANEL).pack(side="left", padx=px(10))
        self.min_var = tk.BooleanVar(value=self.cfg.get("minimize_on_play", True))
        RCheck(s, "Minimise the launcher while Minecraft is running", self.min_var).pack(anchor="w", pady=(px(14), 0))
        rr = tk.Frame(s, bg=U.PANEL); rr.pack(anchor="w", pady=(px(10), 0))
        self.rw_var, self.rh_var = tk.StringVar(value=str(self.cfg.get("res_w", ""))), tk.StringVar(value=str(self.cfg.get("res_h", "")))
        label(rr, "WINDOW SIZE (optional)", "cap").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, px(4)))
        entry(rr, self.rw_var, width=7).grid(row=1, column=0, ipady=px(6))
        label(rr, "x", "muted").grid(row=1, column=1, padx=px(8))
        entry(rr, self.rh_var, width=7).grid(row=1, column=2, ipady=px(6))

        s = section("MEMORY AND JAVA")
        cap = max(4, min(32, core.total_ram_gb()))
        self.ram_var = tk.IntVar(value=min(cap, int(self.cfg.get("ram_gb", 4))))
        top = tk.Frame(s, bg=U.PANEL); top.pack(fill="x")
        label(top, "MEMORY", "cap").pack(side="left")
        self.ram_lbl = label(top, f"{self.ram_var.get()} GB", "pix", fg=U.BLUE); self.ram_lbl.pack(side="right")
        sc = ttk.Scale(s, from_=1, to=cap, variable=self.ram_var, style="Ray.Horizontal.TScale",
                       command=lambda v: (self.ram_var.set(round(float(v))), self.ram_lbl.configure(text=f"{self.ram_var.get()} GB")))
        sc.pack(fill="x", pady=(px(8), px(4)))
        label(s, f"Your PC has about {core.total_ram_gb()} GB. 4-6 GB is plenty for vanilla; modpacks like 6-8 GB.", "dim").pack(anchor="w")
        self.java_var = tk.StringVar(value=self.cfg.get("java_path", ""))
        field(s, "JAVA EXECUTABLE (empty = automatic, recommended)", self.java_var,
              lambda: self.java_var.set(filedialog.askopenfilename(title="Select java / javaw") or self.java_var.get()))
        self.jvm_var = tk.StringVar(value=self.cfg.get("jvm_args", ""))
        field(s, "EXTRA JVM ARGUMENTS", self.jvm_var)
        RButton(s, "DOWNLOAD ALL JAVA RUNTIMES", self.install_runtimes, width=290, height=36, size=10, bg=U.PANEL
                ).pack(anchor="w", pady=(px(14), 0))

        s = section("MICROSOFT ACCOUNT")
        self.cid_var = tk.StringVar(value=self.cfg.get("microsoft_client_id", ""))
        field(s, "AZURE APPLICATION (CLIENT) ID", self.cid_var)
        r2 = tk.Frame(s, bg=U.PANEL); r2.pack(anchor="w", pady=(px(12), 0))
        RButton(r2, "SETUP GUIDE", self.microsoft_setup, width=160, height=36, size=10, bg=U.PANEL).pack(side="left")
        RButton(r2, "MOJANG APPROVAL FORM", lambda: webbrowser.open(core.MOJANG_APP_FORM), width=240, height=36,
                size=10, bg=U.PANEL).pack(side="left", padx=px(10))

        s = section("INTERFACE")
        self.scale_var = tk.StringVar(value=f"{int(self.cfg.get('ui_scale', 100))}%")
        label(s, "UI SCALE", "cap").pack(anchor="w", pady=(0, px(4)))
        ttk.Combobox(s, textvariable=self.scale_var, state="readonly", style="Ray.TCombobox", width=10,
                     values=["80%", "90%", "100%", "110%", "125%", "150%", "175%"]).pack(anchor="w")

        RButton(body, "SAVE SETTINGS", self.save_settings, "primary", width=240, height=46, size=14).pack(anchor="w", pady=(px(4), px(20)))

    def save_settings(self):
        name = self.cfg["selected_profile"]
        self.instances[name] = self.dir_var.get().strip() or str(core.CONFIG_DIR / "instances" / core.instance_slug(name))
        old_scale = int(self.cfg.get("ui_scale", 100))
        try: scale = int(self.scale_var.get().replace("%", ""))
        except ValueError: scale = 100
        self.cfg.update(ram_gb=int(self.ram_var.get()), java_path=self.java_var.get().strip(),
                        jvm_args=self.jvm_var.get().strip(), microsoft_client_id=self.cid_var.get().strip(),
                        minimize_on_play=bool(self.min_var.get()), res_w=self.rw_var.get().strip(),
                        res_h=self.rh_var.get().strip(), ui_scale=scale)
        self.save()
        self.status.set("Settings saved.")
        if scale != old_scale: self.rebuild()
        else: self.refresh_versions()

    def remove_instance(self):
        name = self.cfg["selected_profile"]
        if len(self.instances) <= 1:
            message(self.root, "Cannot remove", "You need at least one instance.", "warn"); return
        if not message(self.root, "Remove instance", f"Remove '{name}' from the launcher?\nIts files stay on disk.", "warn",
                       [("CANCEL", False, "normal"), ("REMOVE", True, "danger")]): return
        del self.instances[name]
        self.cfg["selected_profile"] = next(iter(self.instances))
        self.inst_var.set(self.cfg["selected_profile"]); self.save()
        self.refresh_versions(); self.show("settings")

    def install_runtimes(self):
        def work():
            rts = mcl.runtime.get_jvm_runtimes()
            for i, r in enumerate(rts):
                self.post(self.status.set, f"Java runtime {i + 1}/{len(rts)}: {r}")
                mcl.runtime.install_jvm_runtime(r, self.mc_dir, callback=self.callback())
            return len(rts)
        self.background("Downloading Java runtimes…", work, lambda n: self.status.set(f"{n} Java runtimes are ready."))

    # ───────────────────────── UI scale ─────────────────────────
    def step_scale(self, delta):
        cur = int(self.cfg.get("ui_scale", 100))
        new = min(175, max(80, cur + delta))
        if new != cur:
            self.cfg["ui_scale"] = new; self.save(); self.rebuild()

    def rebuild(self):
        U.Theme.sc = self.root.winfo_fpixels("1i") / 96 * int(self.cfg.get("ui_scale", 100)) / 100
        U.setup_ttk(self.root)
        self.shell.destroy()
        self._icon = U.bolt_photoimage(max(2, px(4)))
        self.build_shell(); self.show(self.page_name)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception: ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    root = tk.Tk()
    if mcl is None:
        root.withdraw()
        from tkinter import messagebox
        messagebox.showerror(APP, "Missing dependency. Run: python -m pip install -r requirements.txt")
        return
    U.load_fonts(root)
    cfg = core.read_config()
    U.Theme.sc = root.winfo_fpixels("1i") / 96 * int(cfg.get("ui_scale", 100)) / 100
    U.setup_ttk(root)
    RayClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()
