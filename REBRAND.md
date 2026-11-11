# Ray Launcher: rebrand notes

This tree is OneLauncher (OneClient) rebranded to **Ray Launcher**. These notes record what changed, what was
deliberately left alone, and what you need to do before shipping.

> **Not compiled yet.** The rebrand was produced without a Rust toolchain. Run `cargo check --workspace` and
> `cargo test --workspace` first; see "Verify" below.

## What changed

| Area | Change |
|------|--------|
| Names | `OneLauncher` → `RayLauncher`, `OneClient` → `RayClient`. Crates are `rayclient_*`, enum variants `RayClient`. |
| UI text | App-level strings say **Ray Launcher**. Strings about the instance type / curated mod set say **Ray Client**. |
| Identity | App id `dev.ray.RayLauncher`, URL scheme `rayclient://`, data folder `Ray/RayLauncher`, env vars `RAY_*`. |
| Themes | Four built-ins in Ray Client's navy palette: Ray Craft Dark (default), Ray Craft Light, Ray Dark, Ray Light. |
| Minecraft feel | Pixel font, square corners, pixel icons, and a bevelled button style in the Craft themes. |
| Art | New logo, wordmark, icons, onboarding illustrations, home background, banner, DMG art. All original. |
| Generator | `python3 tools/make_brand_assets.py` regenerates all of it (needs Pillow). |

## Deliberately NOT changed

- **Polyfrost server URLs** (`data-v2.polyfrost.org/oneclient/...`, `meta.polyfrost.org`, `translations.r2.polyfrost.org/oneclient/v1`).
  The launcher's bundles, version metadata, terms and translations come from there. Renaming the path segments
  would 404. To stop depending on Polyfrost, host your own copies and change the URLs in
  `rayclient_common/src/constants.rs`.
- **`oneclient.*` translation keys.** They are the contract with the remote translation files. Only the English
  *values* were rebranded.
- **`rayclient_core/src/migration/`.** It detects installs of the *original* OneClient so users can import them.
- **Microsoft sign-in app id, CurseForge API key, Poly+ endpoints** in `rayclient_common/src/constants.rs`.
  They still belong to Polyfrost. See the to-do list.
- **`crowdin.yml` / Crowdin workflow.** Gated to Polyfrost's repository; inert in a fork.

## Off by default (opt in at build time)

A stock build makes no calls to Ray-owned services, and never to Polyfrost's Sentry or update feed.

| Variable | Enables |
|----------|---------|
| `RAY_UPDATER_ENDPOINT` + `RAY_UPDATER_PUBKEY` | Auto-update (minisign key + signed `latest.json`) |
| `RAY_RELEASES_URL` | Release page for manual updates |
| `RAY_SENTRY_DSN` | Crash reporting |
| `RAY_DISCORD_CLIENT_ID` | Discord rich presence |
| `RAY_SUPPORT_URL` | "Get help" links |

## To do before you ship

1. Replace `your-org` in URLs, workflows and packaging with your GitHub account.
2. Register **your own** Microsoft Azure app (`MICROSOFT_CLIENT_ID`) and CurseForge API key. Until then,
   sign-in screens show Polyfrost's app name and your traffic uses their quotas.
3. Replace the `maintainer@example.com` placeholders in `distribution/`.
4. Add a contact method to `CODE_OF_CONDUCT.md`.
5. Create your own signing key if you want auto-update (`cargo packager signer generate`).

## Licence

OneLauncher is GPL-3.0-only, so Ray Launcher must stay GPL-3.0-only and keep Polyfrost's copyright notices
(see `LICENSE` and `ATTRIBUTION.md`). Polyfrost's *branding* is not GPL-licensed; none of it is in this tree.

## Verify

```sh
cargo check --workspace
cargo test --workspace --lib          # unit tests; some integration tests need network
cargo run -p rayclient_app
```

## Orange rebrand update

- Dark and orange theme (`assets/themes/dark.json`, `light.json`); Minecraft themes removed, old settings fall back to Ray Dark.
- Default UI font is Inter (readable, no pixel font).
- Offline accounts no longer require a Microsoft account first (also offered in first-run setup).
- Only Minecraft 1.21.11 (Fabric) is offered. The catalog is `rayclient_core/assets/versions.json`; the Ray Client bundle (Ray Client 1.0.5 jar + Fabric API) is `rayclient_content/assets/ray-client-1.21.11.polymrpack`. Both are built in, so startup makes no catalog requests.
- Eight bundled orange wallpapers, picked per instance; wallpapers fade in.
- App icons regenerated from the new R logo.
- Fabric API in the bundle is pinned by Modrinth version id (0.141.3+1.21.11); its sha1 field is a placeholder because install resolves it by id.
