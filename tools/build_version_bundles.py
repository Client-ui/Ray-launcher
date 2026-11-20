#!/usr/bin/env python3
"""Builds the embedded Ray Client bundles (one .polymrpack per Minecraft version).

    python3 tools/build_version_bundles.py /path/to/jars

`/path/to/jars` holds files named `ray-client-mc<MC>-<VERSION>.jar` (any prefix before
`ray-client-` is ignored, so upload-hash prefixes are fine). For every jar it writes
`packages/rayclient_content/assets/ray-client-<MC>.polymrpack` containing the jar as an
override plus any companion mods listed in `tools/bundle_extras/<MC>.json`.

When Ray Client ships a new jar, drop it in the folder and re-run. Also add the Minecraft
version to `packages/rayclient_core/assets/versions.json` and to `EMBEDDED_VERSIONS` in
`packages/rayclient_content/src/bundles/manager.rs`.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "packages" / "rayclient_content" / "assets"
EXTRAS = ROOT / "tools" / "bundle_extras"
FABRIC_LOADER = "0.18.1"
JAR_NAME = re.compile(r"ray-client-mc(?P<mc>[0-9.]+)-(?P<ver>[0-9.]+)\.jar$")
STAMP = (2026, 1, 1, 0, 0, 0)  # fixed so identical input gives identical bytes


def add(zf: zipfile.ZipFile, name: str, data: bytes, deflate: bool) -> None:
    info = zipfile.ZipInfo(name, STAMP)
    info.compress_type = zipfile.ZIP_DEFLATED if deflate else zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def build(jar: Path, mc: str, version: str) -> Path:
    extras_file = EXTRAS / f"{mc}.json"
    files = json.loads(extras_file.read_text()) if extras_file.exists() else []
    manifest = {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": version,
        "name": "Ray Client",
        "category": "Ray Client",
        "enabled": True,
        "dependencies": {"minecraft": mc, "fabric-loader": FABRIC_LOADER},
        "files": files,
    }
    out = ASSETS / f"ray-client-{mc}.polymrpack"
    with zipfile.ZipFile(out, "w") as zf:
        add(zf, "modrinth.index.json", json.dumps(manifest, indent=2).encode(), True)
        add(zf, f"overrides/mods/ray-client-{version}.jar", jar.read_bytes(), False)
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    jars = {}
    for path in sorted(Path(sys.argv[1]).glob("*.jar")):
        match = JAR_NAME.search(path.name)
        if match:
            jars[match["mc"]] = (path, match["ver"])
    if not jars:
        print("no ray-client-mc*.jar files found")
        return 1
    ASSETS.mkdir(parents=True, exist_ok=True)
    for mc in sorted(jars, key=lambda v: [int(p) for p in v.split(".")]):
        path, version = jars[mc]
        out = build(path, mc, version)
        print(f"{mc:>7}  Ray {version}  ->  {out.relative_to(ROOT)}  ({out.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
