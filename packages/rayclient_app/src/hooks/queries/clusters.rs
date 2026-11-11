use std::path::PathBuf;

use freya::query::{Query, QueryCapability, UseQuery, use_query};
use rayclient_common::domain::GraphicsBackend;
use rayclient_core::LauncherError;
use rayclient_core::clusters::{Cluster, ClusterKind};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct ListClustersQuery;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct ListClustersKeys;

impl QueryCapability for ListClustersQuery {
    type Ok = Vec<Cluster>;
    type Err = LauncherError;
    type Keys = ListClustersKeys;

    async fn run(&self, _keys: &Self::Keys) -> Result<Self::Ok, Self::Err> {
        let state = crate::launcher::state()?;
        let mut catalog = state.versions.metadata("").await;
        if catalog.is_empty() {
            state.versions.sync(&state.services).await?;
            catalog = state.versions.metadata("").await;
        }
        let offered: std::collections::HashSet<(String, String)> = catalog
            .iter()
            .filter_map(|m| Some((m.mc_version()?, m.loader.as_ref()?.to_lowercase())))
            .collect();

        let mut clusters = state.clusters.list().await?;
        // Ray Client only offers the releases in the built-in catalog. Instances an older
        // build provisioned for other versions are hidden, not deleted, so no worlds are lost
        clusters.retain(|cluster| {
            cluster.user_created
                || cluster.kind != ClusterKind::RayClient
                || offered.contains(&(
                    cluster.mc_version.clone(),
                    cluster.mc_loader.to_string().to_lowercase(),
                ))
        });
        Ok(clusters)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct SharedGroupsQuery;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct SharedGroupsKeys;

impl QueryCapability for SharedGroupsQuery {
    type Ok = Vec<String>;
    type Err = LauncherError;
    type Keys = SharedGroupsKeys;

    async fn run(&self, _keys: &Self::Keys) -> Result<Self::Ok, Self::Err> {
        let state = crate::launcher::state()?;
        Ok(state.clusters.list_shared_groups().await?)
    }
}

pub fn use_shared_groups() -> UseQuery<SharedGroupsQuery> {
    use_query(Query::new(SharedGroupsKeys, SharedGroupsQuery))
}

pub fn use_clusters() -> UseQuery<ListClustersQuery> {
    use_query(Query::new(ListClustersKeys, ListClustersQuery))
}

/// A lookup not a fetch there is no per-cluster query the list is always
/// loaded and small A hook because it subscribes to the list
pub fn use_cluster(cluster_id: i64) -> Option<Cluster> {
    let clusters = super::state::settled_or_loading(&use_clusters()).unwrap_or_default();
    clusters.into_iter().find(|c| c.id == cluster_id)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct GraphicsBackendQuery;

impl QueryCapability for GraphicsBackendQuery {
    type Ok = Option<GraphicsBackend>;
    type Err = LauncherError;
    type Keys = PathBuf;

    async fn run(&self, game_dir: &Self::Keys) -> Result<Self::Ok, Self::Err> {
        Ok(rayclient_core::game::read_graphics_backend(game_dir).await)
    }
}

pub fn use_graphics_backend(game_dir: PathBuf) -> Option<GraphicsBackend> {
    let query = use_query(Query::new(game_dir, GraphicsBackendQuery));
    super::state::settled_or_loading(&query).flatten()
}
