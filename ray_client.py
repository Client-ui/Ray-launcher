import os, sys, json, threading, subprocess, webbrowser, tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from pathlib import Path

try:
    import minecraft_launcher_lib as mcl
except ImportError:
    mcl = None

APP = "Ray Client"
APP_VERSION = "2.0.0"
BG, SIDEBAR, PANEL, PANEL2 = "#080f20", "#0c1730", "#101e39", "#17294a"
BLUE, BLUE2, TEXT, MUTED = "#3b82f6", "#2563eb", "#eef5ff", "#9cb0d2"
GREEN, RED = "#55e6ad", "#ff7788"
CONFIG_DIR = Path.home() / ".ray-client"
CONFIG_FILE = CONFIG_DIR / "settings.json"

def default_mc_dir():
    if sys.platform == "win32":
        return os.path.join(os.getenv("APPDATA", str(Path.home())), ".minecraft")
    if sys.platform == "darwin":
        return str(Path.home() / "Library/Application Support/minecraft")
    return str(Path.home() / ".minecraft")

def read_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def write_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")

class RayClient:
    def __init__(self, root):
        self.root = root
        self.cfg = read_config()
        self.mc_dir = self.cfg.get("game_dir", default_mc_dir())
        self.client_id = self.cfg.get("microsoft_client_id", "")
        self.account = None  # Access tokens stay in memory only; sign in again after restarting.
        self.versions = []
        self.busy = False
        self.root.title("Ray Client")
        self.root.geometry("1040x700")
        self.root.minsize(900, 620)
        self.root.configure(bg=BG)
        self.setup_style()
        self.build_ui()
        self.refresh_versions()

    def setup_style(self):
        s = ttk.Style()
        try: s.theme_use("clam")
        except tk.TclError: pass
        s.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2, foreground=TEXT,
                    arrowcolor=TEXT, bordercolor=PANEL2, padding=7)
        s.map("TCombobox", fieldbackground=[("readonly", PANEL2)], foreground=[("readonly", TEXT)])
        s.configure("Ray.Horizontal.TProgressbar", troughcolor=PANEL2, background=BLUE,
                    bordercolor=PANEL2, lightcolor=BLUE, darkcolor=BLUE)

    def build_ui(self):
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True)
        side = tk.Frame(shell, bg=SIDEBAR, width=205)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        logo = tk.Canvas(side, width=46, height=46, bg=SIDEBAR, highlightthickness=0)
        logo.pack(anchor="w", padx=22, pady=(25, 5))
        logo.create_rectangle(3, 3, 43, 43, fill=BLUE, outline="")
        logo.create_text(23, 23, text="R", fill="white", font=("Segoe UI", 24, "bold"))
        tk.Label(side, text="RAY CLIENT", bg=SIDEBAR, fg=TEXT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=22)
        tk.Label(side, text="MINECRAFT JAVA", bg=SIDEBAR, fg="#7393c8",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=22, pady=(2, 26))
        for label, fn in [("⌂   Home", self.show_home), ("▦   Version library", self.show_library),
                          ("⚒   Mod loaders", self.show_mods), ("⚙   Settings", self.show_settings)]:
            tk.Button(side, text=label, command=fn, anchor="w", bg=SIDEBAR, fg=TEXT,
                      activebackground=PANEL2, activeforeground=TEXT, relief="flat", bd=0,
                      padx=22, pady=13, cursor="hand2", font=("Segoe UI", 10)).pack(fill="x", padx=8, pady=2)
        tk.Frame(side, bg="#1b2b49", height=1).pack(fill="x", padx=18, pady=(20, 12))
        self.account_label = tk.Label(side, text="", bg=SIDEBAR, fg=MUTED,
                                      font=("Segoe UI", 9), wraplength=165, justify="left")
        self.account_label.pack(anchor="w", padx=22, pady=4)
        tk.Button(side, text="＋  Microsoft sign in", command=self.microsoft_login, bg=BLUE,
                  fg="white", activebackground=BLUE2, activeforeground="white", relief="flat",
                  padx=10, pady=10, cursor="hand2", font=("Segoe UI", 9, "bold")).pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(side, text="v" + APP_VERSION, bg=SIDEBAR, fg="#536989",
                 font=("Segoe UI", 8)).pack(side="bottom", anchor="w", padx=22, pady=18)

        self.main = tk.Frame(shell, bg=BG)
        self.main.pack(side="left", fill="both", expand=True, padx=28, pady=25)
        self.status = tk.StringVar(value="Starting Ray Client…")
        statusbar = tk.Frame(self.root, bg="#0b1630")
        statusbar.pack(fill="x", side="bottom")
        self.progress = ttk.Progressbar(statusbar, style="Ray.Horizontal.TProgressbar",
                                        mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        tk.Label(statusbar, textvariable=self.status, bg="#0b1630", fg=MUTED,
                 anchor="w", padx=16, pady=8, font=("Segoe UI", 9)).pack(fill="x")
        self.show_home()
        self.update_account_label()

    def clear(self):
        for child in self.main.winfo_children(): child.destroy()

    def heading(self, title, subtitle):
        tk.Label(self.main, text=title, bg=BG, fg=TEXT, font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(self.main, text=subtitle, bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 20))

    def card(self, parent=None):
        f = tk.Frame(parent or self.main, bg=PANEL, highlightbackground="#203657", highlightthickness=1)
        return f

    def btn(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=BLUE if primary else PANEL2,
                         fg="white" if primary else TEXT, activebackground=BLUE2 if primary else "#20375d",
                         activeforeground="white", relief="flat", bd=0, padx=16, pady=11,
                         cursor="hand2", font=("Segoe UI", 10, "bold"))

    def show_home(self):
        self.clear()
        self.heading("Welcome back.", "Your Minecraft, your rules.")
        hero = self.card()
        hero.pack(fill="x", pady=(0, 18))
        art = tk.Canvas(hero, height=140, bg="#10274d", highlightthickness=0)
        art.pack(fill="x")
        art.create_rectangle(0, 100, 1000, 140, fill="#123761", outline="")
        art.create_rectangle(0, 119, 1000, 140, fill="#17466c", outline="")
        art.create_text(26, 28, text="RAY CLIENT", fill="#a8ccff", anchor="nw",
                        font=("Segoe UI", 10, "bold"))
        art.create_text(26, 54, text="Ready when you are.", fill="white", anchor="nw",
                        font=("Segoe UI", 22, "bold"))
        art.create_text(28, 91, text="JAVA EDITION  •  VERSION CONTROL  •  MODS",
                        fill="#b3c9ed", anchor="nw", font=("Segoe UI", 9, "bold"))
        grid = tk.Frame(self.main, bg=BG)
        grid.pack(fill="x")
        version_card = self.card(grid)
        version_card.pack(side="left", fill="both", expand=True, padx=(0, 9))
        tk.Label(version_card, text="GAME VERSION", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(17, 8))
        self.version_var = tk.StringVar(value=self.cfg.get("last_version", ""))
        self.version_box = ttk.Combobox(version_card, textvariable=self.version_var, state="readonly")
        self.version_box.pack(fill="x", padx=18, pady=(0, 12))
        self.btn(version_card, "Refresh versions", self.refresh_versions).pack(anchor="w", padx=18, pady=(0, 18))
        play_card = self.card(grid)
        play_card.pack(side="left", fill="both", expand=True, padx=(9, 0))
        tk.Label(play_card, text="PLAYER PROFILE", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(17, 8))
        default_name = self.account.get("name") if self.account else self.cfg.get("offline_name", "RayPlayer")
        self.player_var = tk.StringVar(value=default_name or "RayPlayer")
        tk.Entry(play_card, textvariable=self.player_var, bg=PANEL2, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Segoe UI", 11)).pack(fill="x", padx=18, ipady=9)
        self.btn(play_card, "▶   PLAY NOW", self.launch_game, True).pack(fill="x", padx=18, pady=13)
        self.btn(play_card, "↓   Install selected version", self.install_version).pack(fill="x", padx=18, pady=(0, 18))
        bottom = self.card()
        bottom.pack(fill="x", pady=18)
        tk.Label(bottom, text="QUICK NOTES", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(14, 5))
        tk.Label(bottom, text="• First-time downloads need internet. Installed versions can be played offline.\n"
                 "• Microsoft sign-in requires a configured app client ID (see Settings).\n"
                 "• Mod loaders are installed per Minecraft version; mods must match the loader and game version.",
                 bg=PANEL, fg=MUTED, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 15))

    def show_library(self):
        self.clear()
        self.heading("Version library", "Browse Minecraft releases, snapshots and legacy versions.")
        card = self.card(); card.pack(fill="x")
        self.library_list = tk.Listbox(card, bg=PANEL, fg=TEXT, selectbackground=BLUE,
                                       relief="flat", borderwidth=0, font=("Consolas", 10),
                                       height=18, activestyle="none")
        self.library_list.pack(fill="both", expand=True, padx=14, pady=14)
        row = tk.Frame(self.main, bg=BG); row.pack(fill="x", pady=12)
        self.btn(row, "Refresh", self.refresh_versions).pack(side="left")
        self.btn(row, "Install selected", self.install_from_library, True).pack(side="left", padx=10)
        self.status.set("Version library. Select a version and install it.")

    def show_mods(self):
        self.clear()
        self.heading("Mod loaders", "Install a loader for a Minecraft version.")
        card = self.card(); card.pack(fill="x")
        inner = tk.Frame(card, bg=PANEL); inner.pack(fill="x", padx=20, pady=20)
        tk.Label(inner, text="MINECRAFT VERSION", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 7))
        tk.Label(inner, text="MOD LOADER", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=12, pady=(0, 7))
        self.mod_mc_var = tk.StringVar(value=self.cfg.get("last_version", ""))
        self.mod_mc_box = ttk.Combobox(inner, textvariable=self.mod_mc_var, state="readonly")
        self.mod_mc_box.grid(row=1, column=0, sticky="ew")
        self.loader_var = tk.StringVar(value="fabric")
        self.loader_box = ttk.Combobox(inner, textvariable=self.loader_var, state="readonly",
                                       values=["fabric", "forge", "neoforge", "quilt"])
        self.loader_box.grid(row=1, column=1, sticky="ew", padx=12)
        inner.columnconfigure(0, weight=1); inner.columnconfigure(1, weight=1)
        self.btn(inner, "Install mod loader", self.install_loader, True).grid(row=2, column=0, sticky="w", pady=(18, 0))
        note = self.card(); note.pack(fill="x", pady=18)
        tk.Label(note, text="MODS FOLDER", bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(15, 4))
        tk.Label(note, text=os.path.join(self.mc_dir, "mods"), bg=PANEL, fg=MUTED,
                 wraplength=700, justify="left").pack(anchor="w", padx=18, pady=(0, 10))
        self.btn(note, "Open mods folder", self.open_mods_folder).pack(anchor="w", padx=18, pady=(0, 15))
        tk.Label(self.main, text="Install mods only from sources you trust. A mod must match the Minecraft version and loader.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")

    def show_settings(self):
        self.clear()
        self.heading("Settings", "Configure the game directory, memory and Microsoft sign-in.")
        card = self.card(); card.pack(fill="x")
        form = tk.Frame(card, bg=PANEL); form.pack(fill="x", padx=20, pady=20)
        tk.Label(form, text="MINECRAFT DIRECTORY", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        self.dir_var = tk.StringVar(value=self.mc_dir)
        tk.Entry(form, textvariable=self.dir_var, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                 relief="flat").grid(row=1, column=0, sticky="ew", ipady=8, pady=(6, 10))
        self.btn(form, "Browse…", self.browse_dir).grid(row=1, column=1, padx=(10, 0), pady=(6, 10))
        tk.Label(form, text="MICROSOFT APP CLIENT ID", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.client_var = tk.StringVar(value=self.client_id)
        tk.Entry(form, textvariable=self.client_var, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                 relief="flat").grid(row=3, column=0, columnspan=2, sticky="ew", ipady=8, pady=(6, 6))
        tk.Label(form, text="You must register a Microsoft/Azure app and configure the redirect URL. See README.",
                 bg=PANEL, fg=MUTED, wraplength=680, justify="left").grid(row=4, column=0, columnspan=2, sticky="w")
        tk.Label(form, text="MEMORY ALLOCATION (GB)", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=5, column=0, sticky="w", pady=(18, 0))
        self.ram_var = tk.StringVar(value=str(self.cfg.get("ram_gb", 4)))
        ttk.Combobox(form, textvariable=self.ram_var, values=["2", "3", "4", "5", "6", "8", "10", "12"],
                     state="readonly").grid(row=6, column=0, sticky="w", pady=(6, 12))
        form.columnconfigure(0, weight=1)
        self.btn(form, "Save settings", self.save_settings, True).grid(row=7, column=0, sticky="w", pady=(8, 0))
        java = self.card(); java.pack(fill="x", pady=18)
        tk.Label(java, text="JAVA RUNTIMES", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(14, 4))
        tk.Label(java, text="Ray Client can download Mojang-managed runtimes used by Minecraft versions.",
                 bg=PANEL, fg=MUTED).pack(anchor="w", padx=18, pady=(0, 10))
        self.btn(java, "Install managed Java runtimes", self.install_runtimes).pack(anchor="w", padx=18, pady=(0, 15))

    def save_settings(self):
        self.mc_dir = self.dir_var.get().strip() or default_mc_dir()
        self.client_id = self.client_var.get().strip()
        try: ram = max(2, min(12, int(self.ram_var.get())))
        except Exception: ram = 4
        self.cfg.update({"game_dir": self.mc_dir, "microsoft_client_id": self.client_id, "ram_gb": ram})
        write_config(self.cfg)
        self.status.set("Settings saved.")
        messagebox.showinfo("Settings saved", "Your settings have been saved.")

    def browse_dir(self):
        path = filedialog.askdirectory(initialdir=self.mc_dir)
        if path: self.dir_var.set(path)

    def callback(self):
        return {"setStatus": lambda s: self.set_status(str(s)),
                "setProgress": lambda p: self.root.after(0, lambda: self.progress.configure(value=max(0, min(100, p)))),
                "setMax": lambda m: None}

    def set_status(self, text):
        self.root.after(0, lambda: self.status.set(text))

    def set_busy(self, busy):
        self.busy = busy

    def background(self, title, work, done=None):
        if self.busy: return
        self.set_busy(True); self.set_status(title); self.progress.configure(value=0)
        def run():
            try:
                result = work()
                if done: self.root.after(0, lambda: done(result))
                else: self.set_status("Finished.")
            except Exception as e:
                self.set_status("Operation failed.")
                self.root.after(0, lambda err=str(e): messagebox.showerror("Ray Client", err))
            finally:
                self.root.after(0, lambda: self.set_busy(False))
        threading.Thread(target=run, daemon=True).start()

    def refresh_versions(self):
        if mcl is None:
            messagebox.showerror("Missing dependency", "Install requirements with: python -m pip install -r requirements.txt")
            return
        def work():
            return mcl.utils.get_version_list()
        def done(items):
            # Include installed loader profiles as well as Mojang's public version list.
            try:
                installed = mcl.utils.get_installed_versions(self.mc_dir)
            except Exception:
                installed = []
            self.versions = items
            ids = [x["id"] for x in items]
            for item in installed:
                installed_id = item.get("id")
                if installed_id and installed_id not in ids:
                    ids.append(installed_id)
            latest = self.cfg.get("last_version", "")
            if not latest or latest not in ids:
                latest = next((x["id"] for x in items if x.get("type") == "release"), ids[0] if ids else "")
            if hasattr(self, "version_box"):
                self.version_box["values"] = ids
                self.version_var.set(latest)
            if hasattr(self, "mod_mc_box"):
                self.mod_mc_box["values"] = ids
                self.mod_mc_var.set(latest)
            if hasattr(self, "library_list"):
                self.library_list.delete(0, "end")
                types = {x["id"]: x.get("type", "release/snapshot") for x in items}
                for version_id in ids:
                    self.library_list.insert("end", f'{version_id:<28} {types.get(version_id, "installed profile")}')
            self.status.set(f"Loaded {len(ids)} Minecraft versions.")
        self.background("Fetching Minecraft versions…", work, done)

    def chosen_version(self):
        v = getattr(self, "version_var", tk.StringVar(value="")).get().strip()
        if not v:
            messagebox.showwarning("Choose a version", "Refresh the version list and choose a version.")
            return None
        self.cfg["last_version"] = v
        write_config(self.cfg)
        return v

    def install_version(self):
        v = self.chosen_version()
        if not v: return
        def work():
            Path(self.mc_dir).mkdir(parents=True, exist_ok=True)
            mcl.install.install_minecraft_version(v, self.mc_dir, callback=self.callback())
            return v
        self.background(f"Installing Minecraft {v}…", work,
                        lambda v: (self.status.set(f"Minecraft {v} installed."), messagebox.showinfo("Installed", f"Minecraft {v} is ready.")))

    def install_from_library(self):
        sel = self.library_list.curselection()
        if not sel: return messagebox.showwarning("Select a version", "Choose a version from the list.")
        self.version_var.set(self.library_list.get(sel[0]).split()[0])
        self.install_version()

    def install_loader(self):
        if mcl is None: return
        v = self.mod_mc_var.get().strip()
        loader_id = self.loader_var.get().strip()
        if not v: return messagebox.showwarning("Choose a version", "Select a Minecraft version.")
        def work():
            loader = mcl.mod_loader.get_mod_loader(loader_id)
            if not loader.is_minecraft_version_supported(v):
                raise RuntimeError(f"{loader.get_name()} does not support Minecraft {v}. Choose a compatible version.")
            return loader.install(v, self.mc_dir, callback=self.callback())
        self.background(f"Installing {loader_id} for Minecraft {v}…", work,
                        lambda installed: (self.status.set(f"Installed modded profile: {installed}"),
                                           messagebox.showinfo("Loader installed", f"Installed profile:\n{installed}\n\nSelect it from Home to launch.")))

    def install_runtimes(self):
        if mcl is None: return
        def work():
            runtimes = mcl.runtime.get_jvm_runtimes()
            if not runtimes: raise RuntimeError("No managed Java runtimes were returned.")
            for i, runtime in enumerate(runtimes):
                self.set_status(f"Installing managed Java runtime {i+1}/{len(runtimes)}: {runtime}")
                mcl.runtime.install_jvm_runtime(runtime, self.mc_dir, callback=self.callback())
            return runtimes
        self.background("Installing managed Java runtimes…", work,
                        lambda r: messagebox.showinfo("Java runtimes", f"Installed/checked {len(r)} managed runtimes."))

    def microsoft_login(self):
        if not self.client_id:
            messagebox.showinfo("Microsoft sign-in setup",
                "First open Settings and enter your Microsoft/Azure app Client ID. Follow the Microsoft sign-in setup in README.")
            self.show_settings()
            return
        redirect = self.cfg.get("redirect_url", "http://localhost")
        try:
            login_url, state, verifier = mcl.microsoft_account.get_secure_login_data(self.client_id, redirect)
        except Exception as e:
            messagebox.showerror("Sign-in setup error", str(e)); return
        win = tk.Toplevel(self.root); win.title("Microsoft sign in"); win.configure(bg=BG); win.geometry("600x300")
        tk.Label(win, text="Sign in with Microsoft", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(22, 8))
        tk.Label(win, text="Open the Microsoft sign-in page. After signing in, copy the full redirected URL from your browser and paste it below.",
                 bg=BG, fg=MUTED, wraplength=540, justify="left").pack(anchor="w", padx=22)
        self.btn(win, "Open Microsoft sign-in", lambda: webbrowser.open(login_url), True).pack(anchor="w", padx=22, pady=15)
        url_var = tk.StringVar()
        tk.Entry(win, textvariable=url_var, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                 relief="flat").pack(fill="x", padx=22, ipady=9)
        def finish():
            url = url_var.get().strip()
            try:
                code = mcl.microsoft_account.parse_auth_code_url(url, state)
            except Exception as e:
                messagebox.showerror("Invalid redirect URL", str(e), parent=win); return
            win.destroy()
            def work():
                data = mcl.microsoft_account.complete_login(self.client_id, None, redirect, code, verifier)
                return data
            def done(data):
                # Keep access tokens in memory only; never write them to the settings file.
                self.account = {"name": data["name"], "id": data["id"], "access_token": data["access_token"]}
                self.update_account_label(); self.show_home()
                self.status.set(f"Signed in as {data['name']}.")
            self.background("Completing Microsoft sign-in…", work, done)
        self.btn(win, "Complete sign in", finish, True).pack(anchor="e", padx=22, pady=15)

    def update_account_label(self):
        if hasattr(self, "account_label"):
            if self.account:
                self.account_label.configure(text=f"SIGNED IN\n{self.account.get('name', 'Minecraft player')}", fg=GREEN)
            else:
                self.account_label.configure(text="OFFLINE PROFILE\nNo Microsoft account", fg=MUTED)

    def launch_game(self):
        v = self.chosen_version()
        if not v: return
        name = self.player_var.get().strip()
        if self.account:
            opts = {"username": self.account["name"], "uuid": self.account["id"],
                    "token": self.account["access_token"]}
        else:
            if not name or len(name) > 16 or not name.replace("_", "").isalnum():
                return messagebox.showwarning("Invalid player name", "Use 1–16 letters, numbers, or underscores.")
            opts = {"username": name, "uuid": "0"*32, "token": ""}
            self.cfg["offline_name"] = name
            write_config(self.cfg)
        opts["launcherName"] = APP
        opts["launcherVersion"] = APP_VERSION
        opts["gameDirectory"] = self.mc_dir
        opts["jvmArguments"] = [f"-Xmx{self.cfg.get('ram_gb', 4)}G", "-Xms1G"]
        def work():
            # This also downloads any missing files and Mojang-managed runtime required by this version.
            mcl.install.install_minecraft_version(v, self.mc_dir, callback=self.callback())
            command = mcl.command.get_minecraft_command(v, self.mc_dir, opts)
            subprocess.Popen(command, cwd=self.mc_dir)
            return v
        self.background(f"Preparing and launching Minecraft {v}…", work,
                        lambda v: self.status.set(f"Started Minecraft {v}."))

    def open_mods_folder(self):
        path = Path(self.mc_dir) / "mods"; path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32": os.startfile(str(path))
            elif sys.platform == "darwin": subprocess.Popen(["open", str(path)])
            else: subprocess.Popen(["xdg-open", str(path)])
        except Exception as e: messagebox.showerror("Could not open folder", str(e))

def main():
    if mcl is None:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Setup required", "Run: python -m pip install -r requirements.txt")
        return
    root = tk.Tk()
    RayClient(root)
    root.mainloop()

if __name__ == "__main__":
    main()
