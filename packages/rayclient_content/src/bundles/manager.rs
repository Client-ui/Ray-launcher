use std::collections::HashMap;
use std::path::{Path, PathBuf};

use chrono::Utc;
use rayclient_db::dao::bundle as bundle_dao;
use rayclient_db::dao::package_metadata as meta_dao;
use rayclient_db::models::{BundleRow, NewBundle};
use tokio::sync::RwLock;

use crate::bundles::error::BundleError;
use crate::bundles::polymrpack;
use crate::bundles::types::{BundleArchive, BundleFileKind};
use crate::ctx::ContentCtx;
use crate::error::ContentResult;
use rayclient_common::domain::{GameLoader, ProviderId};
use rayclient_common::paths;

/// A Ray Client bundle compiled into the launcher
struct EmbeddedBundle {
    file: &'static str,
    id: &'static str,
    bytes: &'static [u8],
}

/// One entry per Minecraft version Ray Client ships for. The files are produced by
/// `tools/build_version_bundles.py`; keep this list in step with `versions.json`
macro_rules! embedded_bundles {
    ($($mc:literal),+ $(,)?) => {
        &[$(EmbeddedBundle {
            file: concat!("ray-client-", $mc, ".polymrpack"),
            id: concat!("local/ray-client-", $mc, ".polymrpack"),
            bytes: include_bytes!(concat!("../../assets/ray-client-", $mc, ".polymrpack")),
        }),+]
    };
}

const EMBEDDED_BUNDLES: &[EmbeddedBundle] = embedded_bundles!(
    "1.20", "1.20.1", "1.20.2", "1.20.3", "1.20.4", "1.20.6", "1.21", "1.21.1", "1.21.2", "1.21.3",
    "1.21.4", "1.21.5", "1.21.6", "1.21.7", "1.21.8", "1.21.9", "1.21.10", "1.21.11",
);

#[derive(Debug, Clone)]
pub struct Bundle {
    pub remote_path: String,
    pub mc_version: String,
    pub loader: GameLoader,
    pub file_name: String,
    pub name: String,
    pub version_id: String,
    pub category: String,
    pub loader_version: String,
    pub path: PathBuf,
    pub hidden: bool,
}

impl Bundle {
    fn try_from_row(row: BundleRow) -> ContentResult<Self> {
        let loader = GameLoader::from_repr(row.mc_loader as u8)
            .ok_or(BundleError::InvalidLoader(row.mc_loader))?;

        let launcher_dir = paths::data_dir()?;
        let path = launcher_dir.join(&row.disk_path);

        Ok(Self {
            remote_path: row.remote_path,
            mc_version: row.mc_version,
            loader,
            file_name: row.file_name,
            name: row.name.unwrap_or_default(),
            version_id: row.version_id.unwrap_or_default(),
            category: row.category.unwrap_or_default(),
            loader_version: row.loader_version.unwrap_or_default(),
            path,
            hidden: row.hidden != 0,
        })
    }
}

pub struct BundlesManager {
    pub(crate) archive_cache: RwLock<HashMap<PathBuf, crate::bundles::types::BundleManifest>>,
}

impl BundlesManager {
    pub fn new() -> Self {
        Self {
            archive_cache: RwLock::new(HashMap::new()),
        }
    }

    /// Installs the Ray Client bundles that ship inside the launcher
    /// There is no remote catalog: the launcher is the only source, so startup needs no
    /// network round trip and the bundles always match this build
    #[tracing::instrument(skip_all)]
    pub async fn sync(&self, ctx: &ContentCtx) -> ContentResult<bool> {
        let dir = paths::bundles_dir()?.join("bundles");
        polyio::create_dir_all(&dir).await?;

        let mut changed = false;
        let mut ids = Vec::with_capacity(EMBEDDED_BUNDLES.len());
        for embedded in EMBEDDED_BUNDLES {
            changed |= self.sync_embedded(embedded, &dir, ctx).await?;
            ids.push(embedded.id.to_string());
        }

        // Anything an older build fetched from a remote catalog stops being offered
        bundle_dao::hide_bundles_not_in(&ctx.db, &ids).await?;

        Ok(changed)
    }

    async fn sync_embedded(
        &self,
        embedded: &EmbeddedBundle,
        dir: &Path,
        ctx: &ContentCtx,
    ) -> ContentResult<bool> {
        let disk_path = dir.join(embedded.file);
        let sha1 = polyio::sha1_bytes(embedded.bytes);
        let up_to_date = rayclient_net::matches_on_disk(&disk_path, &sha1).await;
        if !up_to_date {
            polyio::write_atomic(&disk_path, embedded.bytes).await?;
            self.archive_cache.write().await.clear();
        }

        let meta = polymrpack::read_meta_from_archive(&disk_path).await?;
        let relative_disk_path = disk_path
            .strip_prefix(paths::data_dir()?)
            .map(|p| p.to_string_lossy().into_owned())
            .unwrap_or_else(|_| disk_path.to_string_lossy().into_owned());
        let synced_at = Utc::now().to_rfc3339();

        bundle_dao::upsert_bundle(
            &ctx.db,
            NewBundle {
                remote_path: embedded.id,
                mc_version: &meta.mc_version,
                mc_loader: meta.loader as i64,
                file_name: embedded.file,
                name: Some(&meta.name),
                version_id: Some(&meta.version_id),
                category: Some(&meta.category),
                loader_version: Some(&meta.loader_version),
                disk_path: &relative_disk_path,
                hidden: false,
                etag: Some(&sha1),
                synced_at: Some(&synced_at),
            },
        )
        .await?;

        Ok(!up_to_date)
    }

    pub async fn cache_archive_manifest(
        &self,
        path: std::path::PathBuf,
        manifest: crate::bundles::types::BundleManifest,
    ) {
        self.archive_cache.write().await.insert(path, manifest);
    }

    #[tracing::instrument(level = "debug", skip(self, ctx))]
    pub async fn archives_for(
        &self,
        ctx: &ContentCtx,
        mc_version: &str,
        loader: GameLoader,
    ) -> ContentResult<Vec<BundleArchive>> {
        let mut archives = Vec::new();
        for bundle in self.list_for(ctx, mc_version, loader).await? {
            let manifest = self.manifest_for_archive(ctx, &bundle.path).await?;
            archives.push(BundleArchive { bundle, manifest });
        }
        Ok(archives)
    }

    #[tracing::instrument(level = "debug", skip(self, ctx))]
    async fn manifest_for_archive(
        &self,
        ctx: &ContentCtx,
        path: &Path,
    ) -> ContentResult<crate::bundles::types::BundleManifest> {
        if let Some(manifest) = self.archive_cache.read().await.get(path) {
            return Ok(manifest.clone());
        }
        let manifest = polymrpack::read_manifest_from_archive(path).await?;
        record_external_metadata(&manifest, ctx).await;
        self.archive_cache
            .write()
            .await
            .insert(path.to_path_buf(), manifest.clone());
        Ok(manifest)
    }

    #[tracing::instrument(level = "debug", skip(self, ctx))]
    pub async fn list_for(
        &self,
        ctx: &ContentCtx,
        mc_version: &str,
        loader: GameLoader,
    ) -> ContentResult<Vec<Bundle>> {
        let rows =
            bundle_dao::list_visible_for_version_loader(&ctx.db, mc_version, loader as i64).await?;

        rows.into_iter()
            .map(Bundle::try_from_row)
            .collect::<Result<Vec<_>, _>>()
    }
}

impl Default for BundlesManager {
    fn default() -> Self {
        Self::new()
    }
}

#[tracing::instrument(level = "debug", skip_all, fields(bundle = %manifest.name))]
async fn record_external_metadata(
    manifest: &crate::bundles::types::BundleManifest,
    ctx: &ContentCtx,
) {
    for bundle_file in &manifest.files {
        let BundleFileKind::External {
            file,
            meta: Some(meta),
            ..
        } = &bundle_file.kind
        else {
            continue;
        };

        if let Err(err) = meta_dao::upsert_package_metadata(
            &ctx.db,
            ProviderId::Local as i64,
            &file.sha1,
            meta.name.as_deref().unwrap_or(&file.name),
            meta.description.as_deref().unwrap_or_default(),
            &meta.authors.join(", "),
            meta.icon_url.as_deref(),
        )
        .await
        {
            tracing::warn!(file = %file.name, error = %err, "failed to record bundle file metadata");
        }
    }
}
