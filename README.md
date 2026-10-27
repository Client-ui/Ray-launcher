# Ray Client 2.0

A dark-blue Minecraft Java launcher project with a version library, managed Java runtime installation, mod-loader installation, Microsoft sign-in integration, offline profiles, configurable memory, and a GitHub Actions Windows build.

## Features

- Browse Mojang's published Java Edition versions and install them.
- Launch installed versions; first launch downloads missing game files and required Mojang-managed Java runtimes.
- Request installation/checking of Mojang-managed Java runtimes from Settings.
- Install supported Forge, NeoForge, Fabric, and Quilt loader profiles using `minecraft-launcher-lib`.
- Microsoft sign-in flow using `minecraft-launcher-lib`.
- Offline profile for single-player and servers that explicitly permit offline-mode connections.
- Choose game directory and RAM allocation.
- GitHub Actions workflow builds a Windows executable.

## Requirements

- Python 3.10+ to run from source.
- Internet access for sign-in, version lists, game downloads, runtime downloads and mod-loader installation.
- A Minecraft Java Edition entitlement for authenticated gameplay.
- A Microsoft application Client ID configured by the project owner. See below.

## Run from source

```bash
python -m pip install -r requirements.txt
python ray_client.py
```

## Microsoft sign-in configuration (required for sign-in)

Microsoft authentication is not a magic switch: each launcher needs a registered app Client ID and correct redirect configuration, and Microsoft's/Minecraft's service permissions can affect whether a new app is allowed to authenticate Minecraft users.

1. Register an application in the Microsoft/Azure app portal that supports personal Microsoft accounts.
2. Configure a redirect URI supported by the application type and the `minecraft-launcher-lib` authentication flow. The current default is `http://localhost`; make the redirect URI match exactly in the app configuration and in Ray Client.
3. In Ray Client, open **Settings** and enter the app's Client ID.
4. If Minecraft Services rejects the app, follow the current `minecraft-launcher-lib` Microsoft Login tutorial and Microsoft's/Minecraft's permission requirements. Do not ask users for Microsoft passwords; the launcher opens Microsoft's own sign-in page.
5. For production distribution, review current Microsoft identity platform policies and Minecraft API permission requirements before publishing.

The sign-in flow asks the user to paste the URL they are redirected to. This avoids running a local callback server, but is less seamless than a polished native callback flow. This starter does not persist refresh tokens, so a signed-in session may need to be re-established later. Account tokens are saved in the local Ray Client settings file to support launching; protect the user's computer and never commit settings files to GitHub.

## Offline profile

Offline mode does not authenticate a Microsoft account. It is intended for single-player and servers configured to allow offline-mode connections. It will not authenticate on most online-mode servers or bypass account ownership checks. Do not use offline mode to impersonate another player.

## Java runtimes

Minecraft version metadata may cause `minecraft-launcher-lib` to install the matching Mojang-managed runtime as part of installation. The Settings page also offers to install/check the managed runtimes known to the library. Some older mod loaders or unusual versions can still require additional Java troubleshooting.

## Mod loaders

The launcher uses `minecraft-launcher-lib`'s mod-loader support for Forge, NeoForge, Fabric and Quilt. Availability varies by Minecraft version. Mods are not bundled; install trusted mods that match the Minecraft version and loader.

## Build Windows downloads (portable EXE + installer)

The workflow `.github/workflows/build-windows.yml` creates both:
- `Ray-Client-Setup.exe` — a normal Windows installer with Start Menu shortcut, optional desktop shortcut, and uninstall support.
- `Ray Client.exe` — a portable executable that does not need to be installed.

### Build and download from GitHub Actions
1. Commit and push the project files to GitHub.
2. Open the repository's **Actions** tab.
3. Select **Build Ray Client (Windows Installer)**.
4. Click **Run workflow** and wait for the green check mark.
5. Open that workflow run and download **Ray-Client-Windows-Downloads** under Artifacts.
6. Extract the downloaded artifact ZIP. Run `Ray-Client-Setup.exe` to install, or run `Ray Client.exe` as the portable version.

### Publish easy public downloads
Push a version tag such as `v2.0.0` after committing the workflow:
```bash
git tag v2.0.0
git push origin v2.0.0
```
The workflow builds both files and attaches them to a GitHub Release automatically. People can then open your repository's **Releases** page and download `Ray-Client-Setup.exe` directly.

The project ZIP itself does not contain a built Windows installer. GitHub Actions builds the Windows files on a Windows runner.

## Legal and branding notes

Ray Client is an unofficial third-party launcher and is not endorsed by Mojang or Microsoft. Minecraft is a trademark of its respective owner. The project does not bundle or redistribute Minecraft game files. Follow the Minecraft EULA, applicable terms, and third-party loader licenses. Review dependencies and generated builds before distributing them.

## Troubleshooting

- **Microsoft sign-in fails:** Check Client ID, app type, exact redirect URI and current Minecraft API permission requirements.
- **Game does not start:** Check the launcher status, selected version, Java/runtime compatibility, and the game's `logs/latest.log`.
- **Mod loader install fails:** That loader may not support the selected version.
- **Windows SmartScreen warning:** Unsigned community-built executables can trigger warnings. Do not tell users to ignore warnings without verifying the build's source and integrity.
