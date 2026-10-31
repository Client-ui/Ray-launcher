# Ray Client Launcher 3.0

A dark, pixel-styled Minecraft Java launcher with **Microsoft (premium) accounts and offline (cracked) accounts**, isolated instances, a version library, mod-loader installer (Fabric, Forge, NeoForge, Quilt), a mod manager and a live game console.

## Features

- **Accounts page** - keep several accounts and switch between them with one click.
  - *Offline*: type a name and play. The UUID is generated the same way vanilla offline servers do it, so your worlds and inventories stay yours.
  - *Microsoft*: device-code sign-in (no URL pasting). You get a code, enter it on microsoft.com/link, done. The refresh token is saved, so you stay signed in after a restart.
- **Play page** modelled on the Ray Client main menu: one big PLAY button, version and instance pickers.
- **Versions**: releases, snapshots, old versions, installed modded profiles; install, delete, filter and search.
- **Mods**: install a loader (only the Minecraft versions it supports are offered), add / enable / disable / remove mod jars.
- **Console**: live Minecraft output, crash detection, copy log.
- **Instances**: separate game folders (mods, saves, versions) per instance.
- **Settings**: RAM slider, Java path, JVM arguments, window size, minimise-while-playing, UI scale (Ctrl +/-).

## Run from source

```bash
python -m pip install -r requirements.txt
python ray_client.py
```
Python 3.10+ with Tk (included in the python.org installer on Windows).

## Microsoft sign-in: one-time setup

Offline accounts work immediately. For real Microsoft accounts the launcher needs **its own Azure app** (free):

1. Azure portal -> *App registrations* -> *New registration*. Supported account types: **Personal Microsoft accounts only**. No redirect URI needed.
2. In the app: *Authentication* -> enable **Allow public client flows**.
3. Copy the *Application (client) ID* and paste it in **Accounts -> Add Microsoft** (or Settings). The in-app guide has buttons for the links.
4. **Mojang must approve the app.** Submit the client ID in Mojang's form (https://aka.ms/AppRegistrationForm). Until it is approved, sign-in ends with `INVALID_REGISTRATION`; this is Mojang's rule for every third-party launcher, not a bug. Offline accounts keep working meanwhile.

If you distribute the launcher, set `DEFAULT_CLIENT_ID` in `ray_core.py` to your approved client ID. Players then never see this setup - only the "enter this code" screen.

Passwords are never typed into Ray Client. Only refresh tokens are stored (`~/.ray-client/accounts.json`); short-lived game tokens stay in memory.

## Offline accounts

Offline mode does not verify ownership. It is meant for singleplayer and servers that run in offline mode. It does not work on online-mode servers.

## Build for Windows

`.github/workflows/build-windows.yml` builds `Ray Client.exe` (portable) and `Ray-Client-Setup.exe` (installer). Run the workflow from the Actions tab, or push a tag such as `v3.0.0` to publish both files on the Releases page.

Manual build:
```bash
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name "Ray Client" --icon assets/ray.ico --add-data "assets;assets" ray_client.py
```

## Files

| File | Purpose |
|---|---|
| `ray_client.py` | Application and all pages |
| `ray_ui.py` | Theme, pixel font loading, custom widgets, dialogs, bolt logo |
| `ray_core.py` | Config, accounts, Microsoft sign-in, helpers |
| `assets/` | Silkscreen pixel font (SIL OFL, see `assets/fonts/OFL.txt`), icon |

Ray Client is an unofficial launcher, not affiliated with Mojang AB or Microsoft. Minecraft is a trademark of Mojang Synergies AB.
