//! User-supplied wallpapers: imported once, downscaled and stored next to the settings

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{LazyLock, Mutex};

use bytes::Bytes;

use crate::AppAssets;

const MAX_EDGE: u32 = 1920;
const FOLDER: &str = "wallpapers";

static CUSTOM: LazyLock<Mutex<HashMap<String, Bytes>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

/// Marker stored in the settings for "a different bundled wallpaper every launch"
pub const SHUFFLE: &str = "shuffle";

/// Chosen wallpapers are either a bundled asset path or an absolute path of an import
pub fn is_custom(chosen: &str) -> bool {
    Path::new(chosen).is_absolute()
}

/// Bytes of whichever wallpaper `chosen` names, cached after the first read
pub fn bytes_for(chosen: &str) -> Option<Bytes> {
    if chosen == SHUFFLE {
        return AppAssets::get_bytes(crate::components::shuffled_path());
    }
    if !is_custom(chosen) {
        return AppAssets::get_bytes(chosen);
    }
    let mut cache = CUSTOM.lock().ok()?;
    if let Some(bytes) = cache.get(chosen) {
        return Some(bytes.clone());
    }
    let bytes = Bytes::from(std::fs::read(chosen).ok()?);
    cache.insert(chosen.to_string(), bytes.clone());
    Some(bytes)
}

/// Copies `source` into the launcher's folder as a downscaled JPEG and returns its path
pub async fn import(source: PathBuf) -> Option<String> {
    tokio::task::spawn_blocking(move || import_blocking(&source))
        .await
        .ok()
        .flatten()
}

fn import_blocking(source: &Path) -> Option<String> {
    let image = image::open(source)
        .ok()?
        .thumbnail(MAX_EDGE, MAX_EDGE)
        .to_rgb8();
    let dir = rayclient_common::paths::data_dir().ok()?.join(FOLDER);
    std::fs::create_dir_all(&dir).ok()?;

    // Drop earlier imports so only the current one takes disk space
    if let Ok(entries) = std::fs::read_dir(&dir) {
        for entry in entries.flatten() {
            let _ = std::fs::remove_file(entry.path());
        }
    }

    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_millis());
    let target = dir.join(format!("custom-{stamp}.jpg"));
    image
        .save_with_format(&target, image::ImageFormat::Jpeg)
        .ok()?;
    Some(target.to_string_lossy().into_owned())
}
