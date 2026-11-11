use tokio::sync::{Mutex, RwLock};

use crate::LauncherResult;
use crate::state::LauncherServices;
use crate::versions::arts::{ArtsManifest, VersionArts};
use crate::versions::manifest::{
    ReleaseTarget, RemoteMigration, VersionMetadata, VersionsManifest, added_release_targets,
};

/// The only release the launcher offers; there is no remote catalog to fetch
const EMBEDDED_VERSIONS: &str = include_str!("../../assets/versions.json");

fn embedded_manifest() -> VersionsManifest {
    serde_json::from_str(EMBEDDED_VERSIONS).expect("embedded versions.json is valid")
}

pub struct VersionsManager {
    manifest: RwLock<VersionsManifest>,
    arts: RwLock<ArtsManifest>,
    syncing: Mutex<()>,
    added: std::sync::Mutex<Vec<ReleaseTarget>>,
}

impl VersionsManager {
    #[must_use]
    pub fn new() -> Self {
        Self {
            manifest: RwLock::new(VersionsManifest::default()),
            arts: RwLock::new(ArtsManifest::default()),
            syncing: Mutex::new(()),
            added: std::sync::Mutex::new(Vec::new()),
        }
    }

    /// Seeds from the built-in catalog so the UI renders immediately with no request
    #[must_use]
    pub async fn from_cache() -> Self {
        Self {
            manifest: RwLock::new(embedded_manifest()),
            arts: RwLock::new(ArtsManifest::default()),
            syncing: Mutex::new(()),
            added: std::sync::Mutex::new(Vec::new()),
        }
    }

    #[tracing::instrument(level = "debug", skip(self, _services))]
    pub async fn sync(&self, _services: &LauncherServices) -> LauncherResult<bool> {
        let _guard = self.syncing.lock().await;

        let manifest = embedded_manifest();
        let mut current = self.manifest.write().await;
        if *current == manifest {
            return Ok(false);
        }
        let added = added_release_targets(&current, &manifest);
        *current = manifest;
        drop(current);

        if !added.is_empty() {
            let mut pending = self.added.lock().unwrap();
            for target in added {
                if !pending.contains(&target) {
                    pending.push(target);
                }
            }
        }
        Ok(true)
    }

    pub async fn metadata(&self, meta_url_base: &str) -> Vec<VersionMetadata> {
        self.manifest.read().await.metadata(meta_url_base)
    }

    pub async fn arts(&self, meta_url_base: &str) -> VersionArts {
        let arts = self.arts.read().await;
        VersionArts::new(&arts, meta_url_base)
    }

    pub async fn migrations(&self) -> Vec<RemoteMigration> {
        self.manifest.read().await.migrations.clone()
    }

    pub async fn shows_initial_migration(&self, target: &ReleaseTarget) -> bool {
        self.manifest.read().await.shows_initial_migration(target)
    }

    pub fn take_added_versions(&self) -> Vec<ReleaseTarget> {
        std::mem::take(&mut *self.added.lock().unwrap())
    }
}

impl Default for VersionsManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_catalog_is_only_1_21_11_fabric() {
        let metadata = embedded_manifest().metadata("");
        let versions: Vec<String> = metadata.iter().filter_map(|m| m.mc_version()).collect();
        assert_eq!(versions, ["1.21.11"]);
        assert!(
            metadata
                .iter()
                .filter(|m| m.minor_version.is_some())
                .all(|m| m.loader.as_deref() == Some("fabric"))
        );
    }
}
