//! Skins for offline accounts. Minecraft takes a player's skin from Mojang's servers, which
//! know nothing about offline names, so the launcher stores a PNG per name and drops it where
//! the bundled CustomSkinLoader mod reads local skins from.

use std::io;
use std::path::{Path, PathBuf};

const PNG_SIGNATURE: [u8; 8] = [0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A];
const LOCAL_SKINS: [&str; 3] = ["CustomSkinLoader", "LocalSkin", "skins"];

fn store_dir() -> io::Result<PathBuf> {
    rayclient_common::paths::data_dir()
        .map(|dir| dir.join("skins"))
        .map_err(|err| io::Error::other(err.to_string()))
}

fn file_name(username: &str) -> io::Result<String> {
    if username.is_empty()
        || !username
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '_')
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid username",
        ));
    }
    Ok(format!("{username}.png"))
}

/// Skins are 64x64 (or the old 64x32); anything else is not a skin
fn validate_png(bytes: &[u8]) -> io::Result<()> {
    let invalid = || io::Error::new(io::ErrorKind::InvalidData, "not a valid Minecraft skin");
    if bytes.len() < 24 || bytes[..8] != PNG_SIGNATURE {
        return Err(invalid());
    }
    let width = u32::from_be_bytes([bytes[16], bytes[17], bytes[18], bytes[19]]);
    let height = u32::from_be_bytes([bytes[20], bytes[21], bytes[22], bytes[23]]);
    if width == 64 && (height == 64 || height == 32) {
        Ok(())
    } else {
        Err(invalid())
    }
}

pub fn has_skin(username: &str) -> bool {
    store_dir()
        .and_then(|dir| Ok(dir.join(file_name(username)?)))
        .is_ok_and(|path| path.is_file())
}

/// Validates and stores the PNG at `source` as the skin of the offline account `username`
pub fn import_skin(username: &str, source: &Path) -> io::Result<()> {
    let bytes = std::fs::read(source)?;
    validate_png(&bytes)?;
    let dir = store_dir()?;
    std::fs::create_dir_all(&dir)?;
    std::fs::write(dir.join(file_name(username)?), bytes)
}

pub fn remove_skin(username: &str) -> io::Result<()> {
    match std::fs::remove_file(store_dir()?.join(file_name(username)?)) {
        Err(err) if err.kind() != io::ErrorKind::NotFound => Err(err),
        _ => Ok(()),
    }
}

const MOD_PREFIX: &str = "CustomSkinLoader";
const PARKED_SUFFIX: &str = ".disabled";

/// Turns the bundled skin mod on or off for this launch. Off parks the jar under a name the
/// loader ignores so Microsoft accounts, and anyone who hit a mod conflict, run without it
pub fn set_mod_enabled(game_dir: &Path, enabled: bool) -> io::Result<()> {
    let mods = game_dir.join("mods");
    let Ok(entries) = std::fs::read_dir(&mods) else {
        return Ok(());
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
            continue;
        };
        if !name.starts_with(MOD_PREFIX) {
            continue;
        }
        if enabled {
            if let Some(active) = name.strip_suffix(PARKED_SUFFIX) {
                let active = mods.join(active);
                if active.exists() {
                    std::fs::remove_file(&path)?;
                } else {
                    std::fs::rename(&path, active)?;
                }
            }
        } else if name.ends_with(".jar") {
            let parked = mods.join(format!("{name}{PARKED_SUFFIX}"));
            if parked.exists() {
                std::fs::remove_file(&parked)?;
            }
            std::fs::rename(&path, parked)?;
        }
    }
    Ok(())
}

/// Puts the account's skin where CustomSkinLoader looks, or clears a stale copy
pub fn install_for_launch(game_dir: &Path, username: &str) -> io::Result<()> {
    let name = file_name(username)?;
    let target_dir = LOCAL_SKINS
        .iter()
        .fold(game_dir.to_path_buf(), |dir, part| dir.join(part));
    let target = target_dir.join(&name);
    let stored = store_dir()?.join(&name);

    if stored.is_file() {
        std::fs::create_dir_all(&target_dir)?;
        std::fs::copy(stored, target)?;
    } else if target.is_file() {
        std::fs::remove_file(target)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn png(width: u32, height: u32) -> Vec<u8> {
        let mut bytes = PNG_SIGNATURE.to_vec();
        bytes.extend([0, 0, 0, 13]);
        bytes.extend(b"IHDR");
        bytes.extend(width.to_be_bytes());
        bytes.extend(height.to_be_bytes());
        bytes
    }

    #[test]
    fn accepts_only_skin_sized_pngs() {
        assert!(validate_png(&png(64, 64)).is_ok());
        assert!(validate_png(&png(64, 32)).is_ok());
        assert!(validate_png(&png(128, 128)).is_err());
        assert!(validate_png(b"not a png at all, really not").is_err());
    }

    #[test]
    fn rejects_unsafe_names() {
        assert!(file_name("Steve_01").is_ok());
        assert!(file_name("../evil").is_err());
        assert!(file_name("").is_err());
    }
}
