"""Ray Client – core logic (no GUI): config, accounts, Microsoft sign-in, helpers."""
import hashlib, json, os, sys, time, uuid
from pathlib import Path

import requests

try:
    import minecraft_launcher_lib as mcl
except ImportError:  # the GUI shows a friendly message
    mcl = None

APP = "Ray Client"
APP_VERSION = "3.0.0"
CONFIG_DIR = Path.home() / ".ray-client"
CONFIG_FILE = CONFIG_DIR / "settings.json"
ACCOUNTS_FILE = CONFIG_DIR / "accounts.json"

# Put your Mojang-approved Azure Client ID here and players never have to configure anything.
DEFAULT_CLIENT_ID = ""

MS_SCOPE = "XboxLive.signin offline_access"
MS_DEVICE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
MS_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
MOJANG_APP_FORM = "https://aka.ms/AppRegistrationForm"
AZURE_PORTAL = "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"


# ───────────────────────── files / config ─────────────────────────
def _atomic_write(path: Path, data: dict, private=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if private:
        try: os.chmod(tmp, 0o600)
        except OSError: pass
    os.replace(tmp, path)


def read_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_config(cfg):
    _atomic_write(CONFIG_FILE, cfg)


def default_mc_dir():
    if sys.platform == "win32":
        return os.path.join(os.getenv("APPDATA", str(Path.home())), ".minecraft")
    if sys.platform == "darwin":
        return str(Path.home() / "Library/Application Support/minecraft")
    return str(Path.home() / ".minecraft")


def open_folder(path):
    import subprocess
    Path(path).mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32": os.startfile(str(path))
    elif sys.platform == "darwin": subprocess.Popen(["open", str(path)])
    else: subprocess.Popen(["xdg-open", str(path)])


def total_ram_gb():
    """Best-effort installed RAM in GB (used to cap the memory slider)."""
    try:
        if sys.platform == "win32":
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("m", ctypes.c_ulong)] + \
                           [(f"p{i}", ctypes.c_ulonglong) for i in range(7)]
            ms = MS(); ms.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return max(2, int(ms.p0 / 1024**3))
        if sys.platform == "darwin":
            import subprocess
            return max(2, int(int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) / 1024**3))
        with open("/proc/meminfo") as f:
            return max(2, int(int(f.readline().split()[1]) / 1024 / 1024))
    except Exception:
        return 16


# ───────────────────────── instances ─────────────────────────
def load_instances(cfg):
    """Instances = isolated game directories. Keeps the old 'profiles' config format."""
    inst = cfg.setdefault("profiles", {})
    if not inst:
        inst["Default"] = cfg.get("game_dir") or str(CONFIG_DIR / "instances" / "Default")
    if cfg.get("selected_profile") not in inst:
        cfg["selected_profile"] = next(iter(inst))
    return inst


def instance_slug(name):
    s = "".join(c if c.isalnum() or c in "-_ " else "-" for c in name).strip().replace(" ", "-")
    return s or "instance"


# ───────────────────────── accounts ─────────────────────────
def offline_uuid(name: str) -> str:
    """Same UUID a vanilla offline-mode server gives this name (Java nameUUIDFromBytes),
    so worlds, inventories and server data stay attached to the name."""
    b = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    b[6] = (b[6] & 0x0F) | 0x30
    b[8] = (b[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(b)))


def valid_username(name: str) -> bool:
    return 3 <= len(name) <= 16 and name.isascii() and all(c.isalnum() or c == "_" for c in name)


class AccountStore:
    """Saved accounts. Only the long-lived refresh token is written to disk;
    short-lived Minecraft access tokens stay in memory."""

    def __init__(self):
        self.data = {"accounts": [], "selected": None}
        self.session = {}  # account id -> {"access_token", "expires"}
        try:
            self.data.update(json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass

    def save(self):
        _atomic_write(ACCOUNTS_FILE, self.data, private=True)

    @property
    def accounts(self):
        return self.data["accounts"]

    def get(self, acc_id):
        return next((a for a in self.accounts if a["id"] == acc_id), None)

    def selected(self):
        return self.get(self.data.get("selected")) or (self.accounts[0] if self.accounts else None)

    def select(self, acc_id):
        self.data["selected"] = acc_id
        self.save()

    def add_offline(self, name):
        for a in self.accounts:
            if a["type"] == "offline" and a["name"].lower() == name.lower():
                self.data["selected"] = a["id"]; self.save()
                return a
        acc = {"id": uuid.uuid4().hex, "type": "offline", "name": name, "uuid": offline_uuid(name)}
        self.accounts.append(acc)
        self.data["selected"] = acc["id"]
        self.save()
        return acc

    def add_microsoft(self, profile, refresh_token):
        acc = next((a for a in self.accounts
                    if a["type"] == "microsoft" and a["uuid"] == profile["uuid"]), None)
        if acc is None:
            acc = {"id": uuid.uuid4().hex, "type": "microsoft"}
            self.accounts.append(acc)
        acc.update(name=profile["name"], uuid=profile["uuid"], refresh_token=refresh_token)
        self.session[acc["id"]] = {"access_token": profile["access_token"], "expires": time.time() + 3000}
        self.data["selected"] = acc["id"]
        self.save()
        return acc

    def remove(self, acc_id):
        self.data["accounts"] = [a for a in self.accounts if a["id"] != acc_id]
        self.session.pop(acc_id, None)
        if self.data.get("selected") == acc_id:
            self.data["selected"] = self.accounts[0]["id"] if self.accounts else None
        self.save()


# ───────────────────────── Microsoft sign-in (device code) ─────────────────────────
class AuthError(Exception):
    """Message is safe to show to the user."""


def request_device_code(client_id):
    r = requests.post(MS_DEVICE_URL, data={"client_id": client_id, "scope": MS_SCOPE}, timeout=20)
    d = r.json()
    if "device_code" not in d:
        raise AuthError(_azure_error(d))
    return d  # user_code, device_code, verification_uri, expires_in, interval


def poll_device_token(client_id, device, cancelled):
    """Blocks until the user finishes in the browser. `cancelled()` -> True aborts."""
    interval = int(device.get("interval", 5))
    deadline = time.time() + int(device.get("expires_in", 900))
    while time.time() < deadline:
        for _ in range(interval * 4):
            if cancelled(): raise AuthError("Sign-in cancelled.")
            time.sleep(0.25)
        r = requests.post(MS_TOKEN_URL, timeout=20, data={
            "client_id": client_id, "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device["device_code"]})
        d = r.json()
        if "access_token" in d:
            return d
        err = d.get("error")
        if err == "authorization_pending": continue
        if err == "slow_down": interval += 5; continue
        if err == "authorization_declined": raise AuthError("Sign-in was declined in the browser.")
        if err == "expired_token": break
        raise AuthError(_azure_error(d))
    raise AuthError("The sign-in code expired. Try again.")


def refresh_ms_token(client_id, refresh_token):
    r = requests.post(MS_TOKEN_URL, timeout=20, data={
        "client_id": client_id, "grant_type": "refresh_token",
        "refresh_token": refresh_token, "scope": MS_SCOPE})
    d = r.json()
    if "access_token" not in d:
        raise AuthError("Your Microsoft session expired. Remove the account and sign in again.")
    return d


def _azure_error(d):
    desc = d.get("error_description", "") or d.get("error", "unknown error")
    if "AADSTS700016" in desc or "AADSTS700025" in desc or d.get("error") == "invalid_client":
        return ("Microsoft rejected this Client ID. Check that it is correct and that the app has "
                "'Allow public client flows' set to Yes.")
    return desc.splitlines()[0]


def minecraft_login_from_ms_token(ms_access_token):
    """Xbox Live -> XSTS -> Minecraft services. Returns {name, uuid, access_token}."""
    ma = mcl.microsoft_account
    xbl = ma.authenticate_with_xbl(ms_access_token)
    if "Token" not in xbl:
        raise AuthError("Xbox Live sign-in failed. Try again in a few minutes.")
    uhs = xbl["DisplayClaims"]["xui"][0]["uhs"]
    xsts = ma.authenticate_with_xsts(xbl["Token"])
    if "Token" not in xsts:
        xerr = xsts.get("XErr")
        msgs = {
            2148916233: "This Microsoft account has no Xbox profile. Sign in once at xbox.com to create one.",
            2148916235: "Xbox Live is not available in your country/region.",
            2148916238: "This is a child account. An adult must add it to a Microsoft Family first.",
        }
        raise AuthError(msgs.get(xerr, f"Xbox authorisation failed (code {xerr})."))
    mc = ma.authenticate_with_minecraft(uhs, xsts["Token"])
    if "access_token" not in mc:
        raise AuthError(
            "Minecraft services refused this app (INVALID_REGISTRATION).\n\n"
            "Mojang only accepts Azure apps that they have approved. Submit your app's Client ID "
            "in Mojang's form and wait for approval. Until then you can play with an offline account.")
    profile = ma.get_profile(mc["access_token"])
    if profile.get("error") == "NOT_FOUND":
        raise AuthError("This Microsoft account does not own Minecraft: Java Edition.")
    if "id" not in profile:
        raise AuthError("Could not read the Minecraft profile for this account.")
    return {"name": profile["name"], "uuid": str(uuid.UUID(profile["id"])),
            "access_token": mc["access_token"]}


def ensure_session(store: AccountStore, acc, client_id):
    """Return (username, uuid, access_token) ready for launching; refreshes MS tokens."""
    if acc["type"] == "offline":
        return acc["name"], acc["uuid"], "0"
    s = store.session.get(acc["id"])
    if s and s["expires"] > time.time():
        return acc["name"], acc["uuid"], s["access_token"]
    if not client_id:
        raise AuthError("Set your Microsoft Client ID in Settings to use this account.")
    tok = refresh_ms_token(client_id, acc["refresh_token"])
    prof = minecraft_login_from_ms_token(tok["access_token"])
    acc["name"] = prof["name"]
    if tok.get("refresh_token"):
        acc["refresh_token"] = tok["refresh_token"]
    store.session[acc["id"]] = {"access_token": prof["access_token"], "expires": time.time() + 3000}
    store.save()
    return prof["name"], prof["uuid"], prof["access_token"]
